from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import PatientProfile, User
from clinics.models import TimeSlot
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