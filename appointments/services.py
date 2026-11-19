from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from accounts.models import PatientProfile, User, phone_validator
from clinics.models import DoctorProfile, TimeSlot
from clinics.services import available_slots_qs

from .models import Appointment


class BookingError(Exception):
    """Lỗi nghiệp vụ. Nội dung có thể hiển thị trực tiếp cho người dùng."""


@transaction.atomic
def book_appointment(*, user, slot_id, profile_id, symptoms=""):
    rules = settings.BOOKING_RULES

    # Khóa dòng user: các request đồng thời của cùng một tài khoản phải xếp hàng (BR-02)
    user = User.objects.select_for_update().get(pk=user.pk)

    if user.is_booking_locked():
        until = timezone.localtime(user.booking_locked_until)
        raise BookingError(f"Tài khoản bị tạm khóa đặt lịch đến {until:%d/%m/%Y}.")

    profile = PatientProfile.objects.filter(pk=profile_id, owner=user).first()
    if profile is None:
        raise BookingError("Hồ sơ khám không hợp lệ.")

    active = Appointment.objects.filter(
        booked_by=user, status=Appointment.Status.CONFIRMED,
        slot__start_at__gt=timezone.now(),
    ).count()
    if active >= rules["MAX_ACTIVE_APPOINTMENTS"]:
        raise BookingError(
            f"Bạn đang có {active} lịch hẹn chưa diễn ra, "
            f"tối đa được {rules['MAX_ACTIVE_APPOINTMENTS']}. Hãy hủy bớt hoặc chờ khám xong."
        )

    # Khóa dòng slot rồi mới kiểm tra: người đến sau phải chờ người đến trước xong (BR-01)
    slot = TimeSlot.objects.select_for_update().filter(pk=slot_id).first()
    if slot is None:
        raise BookingError("Khung giờ không tồn tại.")
    if not available_slots_qs().filter(pk=slot.pk).exists():
        raise BookingError("Khung giờ này không còn trống.")

    try:
        with transaction.atomic():  # savepoint, để bắt IntegrityError mà không hỏng cả transaction
            return Appointment.objects.create(
                slot=slot, profile=profile, booked_by=user, symptoms=symptoms.strip(),
            )
    except IntegrityError:
        # Lớp bảo vệ cuối: database chặn đặt trùng slot
        raise BookingError("Khung giờ này vừa có người khác đặt.")


@transaction.atomic
def cancel_appointment(*, user, appointment_id, by_staff=False):
    appt = (Appointment.objects.select_for_update(of=("self",))
            .select_related("slot").filter(pk=appointment_id).first())
    if appt is None or (not by_staff and appt.booked_by_id != user.pk):
        raise BookingError("Không tìm thấy lịch hẹn.")
    if not appt.can_transition_to(Appointment.Status.CANCELLED):
        raise BookingError("Chỉ hủy được lịch ở trạng thái Đã xác nhận.")

    if not by_staff:  # BR-03
        hours = settings.BOOKING_RULES["CANCEL_MIN_HOURS"]
        if appt.slot.start_at - timezone.now() < timedelta(hours=hours):
            raise BookingError(
                f"Chỉ được hủy trực tuyến trước giờ khám tối thiểu {hours} tiếng. "
                "Vui lòng gọi tổng đài phòng khám để hủy."
            )

    appt.status = Appointment.Status.CANCELLED
    appt.cancelled_at = timezone.now()
    appt.save(update_fields=["status", "cancelled_at"])
    return appt


@transaction.atomic
def reschedule_appointment(*, user, appointment_id, new_slot_id):
    """Đổi lịch (FR-11) = hủy lịch cũ rồi đặt lịch mới.
    Cả hai nằm trong một transaction: đặt mới lỗi thì lịch cũ được giữ nguyên."""
    old = (Appointment.objects.filter(pk=appointment_id, booked_by=user)
           .select_related("slot").first())
    if old is None:
        raise BookingError("Không tìm thấy lịch hẹn.")
    if old.slot_id == int(new_slot_id):
        raise BookingError("Vui lòng chọn khung giờ khác với lịch hiện tại.")

    profile_id, symptoms = old.profile_id, old.symptoms
    cancel_appointment(user=user, appointment_id=old.pk)
    return book_appointment(user=user, slot_id=new_slot_id,
                            profile_id=profile_id, symptoms=symptoms)


@transaction.atomic
def change_status(appointment_id, new_status):
    """Chuyển trạng thái theo máy trạng thái FR-12.
    Dùng cho lễ tân, bác sĩ và tác vụ tự động ở các giai đoạn sau."""
    appt = (Appointment.objects.select_for_update(of=("self",))
            .filter(pk=appointment_id).first())
    if appt is None:
        raise BookingError("Không tìm thấy lịch hẹn.")
    if not appt.can_transition_to(new_status):
        raise BookingError(
            f"Không thể chuyển từ '{appt.get_status_display()}' sang "
            f"'{Appointment.Status(new_status).label}'."
        )
    appt.status = new_status
    fields = ["status"]
    if new_status == Appointment.Status.CHECKED_IN:
        appt.checked_in_at = timezone.now()
        fields.append("checked_in_at")
    if new_status == Appointment.Status.CANCELLED:
        appt.cancelled_at = timezone.now()
        fields.append("cancelled_at")
    appt.save(update_fields=fields)
    return appt

def checkin_problem(appt, now=None):
    """Lý do chưa check-in được (chuỗi), hoặc None nếu được (FR-13, BR-04)."""
    now = now or timezone.now()
    rules = settings.BOOKING_RULES
    if appt.status == Appointment.Status.CHECKED_IN:
        return "Lịch hẹn này đã check-in rồi."
    if appt.status != Appointment.Status.CONFIRMED:
        return f"Không thể check-in lịch ở trạng thái '{appt.get_status_display()}'."

    start = appt.slot.start_at
    opens = start - timedelta(minutes=rules.get("CHECKIN_OPEN_MINUTES", 30))
    late = start + timedelta(minutes=rules["NO_SHOW_GRACE_MINUTES"])
    if now < opens:
        return f"Chưa đến giờ check-in. Quầy mở check-in từ {timezone.localtime(opens):%H:%M}."
    if now > late:
        return (f"Đã quá giờ hẹn {rules['NO_SHOW_GRACE_MINUTES']} phút, lịch này bị tính là "
                "vắng mặt. Vui lòng đặt lịch mới cho bệnh nhân.")
    return None


@transaction.atomic
def check_in(appointment_id):
    """Check-in và cấp số thứ tự theo từng bác sĩ, từng ngày (FR-13)."""
    appt = (Appointment.objects.select_for_update(of=("self",))
            .select_related("slot").filter(pk=appointment_id).first())
    if appt is None:
        raise BookingError("Không tìm thấy lịch hẹn.")
    problem = checkin_problem(appt)
    if problem:
        raise BookingError(problem)

    # Khóa dòng bác sĩ: hai lễ tân check-in cùng lúc không thể nhận trùng số
    DoctorProfile.objects.select_for_update().get(pk=appt.slot.doctor_id)
    day = timezone.localdate(appt.slot.start_at)
    last = (Appointment.objects
            .filter(slot__doctor_id=appt.slot.doctor_id, slot__start_at__date=day,
                    queue_number__isnull=False)
            .aggregate(m=Max("queue_number"))["m"] or 0)

    appt.queue_number = last + 1
    appt.status = Appointment.Status.CHECKED_IN
    appt.checked_in_at = timezone.now()
    appt.save(update_fields=["queue_number", "status", "checked_in_at"])
    return appt


@transaction.atomic
def staff_book_appointment(*, slot_id, phone, full_name, symptoms="", check_in_now=False):
    """Lễ tân đặt lịch cho khách vãng lai (FR-14).
    Không áp BR-02 và khóa BR-05 vì hai luật đó chỉ áp cho đặt lịch trực tuyến."""
    phone = (phone or "").replace(" ", "")
    full_name = (full_name or "").strip()
    if not full_name:
        raise BookingError("Vui lòng nhập họ tên bệnh nhân.")
    try:
        phone_validator(phone)
    except ValidationError:
        raise BookingError("Số điện thoại không hợp lệ (ví dụ 0912345678).")

    slot = TimeSlot.objects.select_for_update().filter(pk=slot_id).first()
    if slot is None:
        raise BookingError("Khung giờ không tồn tại.")
    if not available_slots_qs().filter(pk=slot.pk).exists():
        raise BookingError("Khung giờ này không còn trống.")

    # Tìm tài khoản theo SĐT; chưa có thì tạo tài khoản vãng lai (không đăng nhập được)
    user = User.objects.select_for_update().filter(phone=phone).first()
    if user is None:
        user = User.objects.create_user(
            username=f"walkin-{phone}", phone=phone,
            first_name=full_name, role=User.Role.PATIENT)
    profile = user.profiles.filter(full_name__iexact=full_name).first()
    if profile is None:
        has_self = user.profiles.filter(
            relationship=PatientProfile.Relationship.SELF).exists()
        profile = PatientProfile.objects.create(
            owner=user, full_name=full_name,
            relationship=(PatientProfile.Relationship.OTHER if has_self
                          else PatientProfile.Relationship.SELF))

    try:
        with transaction.atomic():
            appt = Appointment.objects.create(
                slot=slot, profile=profile, booked_by=user,
                symptoms=(symptoms or "").strip(),
                source=Appointment.Source.RECEPTION)
    except IntegrityError:
        raise BookingError("Khung giờ này vừa có người khác đặt.")

    if check_in_now:
        # Nếu chưa check-in được (ví dụ còn xa giờ hẹn) thì cả lần đặt bị hủy (rollback)
        appt = check_in(appt.pk)
    return appt