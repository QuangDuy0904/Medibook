from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment
from appointments.services import BookingError, change_status
from clinics.models import DoctorProfile

from .models import ConsultationNote

S = Appointment.Status


@transaction.atomic
def call_next_patient(doctor):
    """Gọi người check-in có số thứ tự nhỏ nhất vào khám (FR-12)."""
    # Khóa dòng bác sĩ: hai thao tác gọi cùng lúc không thể gọi trùng người
    DoctorProfile.objects.select_for_update().get(pk=doctor.pk)
    base = Appointment.objects.filter(
        slot__doctor=doctor, slot__start_at__date=timezone.localdate())

    if base.filter(status=S.IN_CONSULTATION).exists():
        raise BookingError(
            "Bạn đang khám một bệnh nhân. Hãy kết thúc ca khám đó trước khi gọi người kế tiếp.")
    nxt = (base.filter(status=S.CHECKED_IN)
           .order_by("queue_number", "slot__start_at").first())
    if nxt is None:
        raise BookingError("Chưa có bệnh nhân nào đang chờ khám.")
    return change_status(nxt.pk, S.IN_CONSULTATION)


@transaction.atomic
def save_consultation_note(*, doctor, appointment_id, diagnosis, advice=""):
    """Đang khám: lưu ghi chú và chuyển sang Hoàn thành. Đã hoàn thành: sửa ghi chú (FR-15)."""
    appt = (Appointment.objects.select_for_update(of=("self",))
            .filter(pk=appointment_id, slot__doctor=doctor).first())
    if appt is None:
        raise BookingError("Không tìm thấy lịch hẹn.")
    diagnosis = (diagnosis or "").strip()
    if not diagnosis:
        raise BookingError("Vui lòng nhập chẩn đoán sơ bộ.")
    if appt.status not in (S.IN_CONSULTATION, S.COMPLETED):
        raise BookingError("Chỉ ghi kết quả được khi bệnh nhân đang khám hoặc đã khám xong.")

    ConsultationNote.objects.update_or_create(
        appointment=appt,
        defaults={"diagnosis": diagnosis, "advice": (advice or "").strip()})
    if appt.status == S.IN_CONSULTATION:
        appt = change_status(appt.pk, S.COMPLETED)
    return appt