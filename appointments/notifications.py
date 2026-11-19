import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Appointment

log = logging.getLogger(__name__)


def _rule(name, default):
    return settings.BOOKING_RULES.get(name, default)


def _describe(appt):
    start = timezone.localtime(appt.slot.start_at)
    doctor = appt.slot.doctor
    return (f"Bác sĩ: {doctor}\n"
            f"Chuyên khoa: {doctor.specialty}\n"
            f"Thời gian: {start:%H:%M} ngày {start:%d/%m/%Y}\n"
            f"Người khám: {appt.profile.full_name}\n"
            f"Mã hẹn: {appt.code}")


def _send(to, subject, body):
    """Gửi email; lỗi chỉ ghi log và trả về False, không làm hỏng nghiệp vụ."""
    try:
        send_mail(subject, body, None, [to])
    except Exception:
        log.exception("Không gửi được email tới %s", to)
        return False
    return True


def send_reminder_email(appt):
    to = appt.booked_by.email
    if not to:
        return False
    body = (
        f"Xin chào {appt.booked_by},\n\n"
        f"Bạn có lịch khám sắp tới:\n\n{_describe(appt)}\n\n"
        f"Vui lòng có mặt tại quầy tiếp tân trước giờ hẹn tối thiểu "
        f"{_rule('ARRIVE_EARLY_MINUTES', 10)} phút và mang theo mã hẹn hoặc mã QR. "
        f"Quá giờ hẹn {_rule('NO_SHOW_GRACE_MINUTES', 15)} phút chưa check-in, "
        f"lịch sẽ bị tính là vắng mặt.\n\n"
        f"Nếu cần hủy, hãy hủy trực tuyến trước giờ khám tối thiểu "
        f"{_rule('CANCEL_MIN_HOURS', 2)} tiếng.\n\nMedibook")
    return _send(to, "Nhắc lịch khám sắp tới", body)


def notify_cancelled_by_clinic(appointment_ids, reason=""):
    """Báo cho bệnh nhân khi lịch bị hủy do bác sĩ báo nghỉ."""
    appts = (Appointment.objects.filter(pk__in=appointment_ids)
             .select_related("booked_by", "profile",
                             "slot__doctor__user", "slot__doctor__specialty"))
    for appt in appts:
        to = appt.booked_by.email
        if not to:
            continue
        why = f" Lý do: {reason}." if reason else ""
        body = (
            f"Xin chào {appt.booked_by},\n\n"
            f"Rất tiếc, lịch khám sau đã bị hủy do bác sĩ có việc đột xuất.{why}\n\n"
            f"{_describe(appt)}\n\n"
            f"Bạn có thể đặt lại một khung giờ khác trên website. "
            f"Xin lỗi vì sự bất tiện.\n\nMedibook")
        _send(to, "Lịch khám của bạn đã bị hủy", body)