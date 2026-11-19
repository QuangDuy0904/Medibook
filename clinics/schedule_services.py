from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from appointments.models import Appointment
from appointments.services import change_status

from .models import DayOff, WorkSchedule
from .services import generate_slots


class ScheduleError(Exception):
    """Lỗi nghiệp vụ, nội dung hiển thị được cho bác sĩ."""


def _minutes(t):
    return t.hour * 60 + t.minute


@transaction.atomic
def create_schedule(*, doctor, date, shift, start_time, end_time, slot_minutes):
    """FR-07: tạo ca làm việc và tự sinh khung giờ."""
    if date < timezone.localdate():
        raise ScheduleError("Không thể tạo lịch cho ngày đã qua.")
    if start_time >= end_time:
        raise ScheduleError("Giờ kết thúc phải sau giờ bắt đầu.")
    if _minutes(end_time) - _minutes(start_time) < slot_minutes:
        raise ScheduleError("Ca làm việc quá ngắn so với độ dài một khung giờ.")

    same_day = WorkSchedule.objects.filter(doctor=doctor, date=date)
    if same_day.filter(shift=shift).exists():
        raise ScheduleError("Bạn đã có lịch ca này trong ngày đó.")
    if same_day.filter(start_time__lt=end_time, end_time__gt=start_time).exists():
        raise ScheduleError("Giờ làm việc bị trùng với ca khác trong ngày.")

    try:
        with transaction.atomic():
            sched = WorkSchedule.objects.create(
                doctor=doctor, date=date, shift=shift, start_time=start_time,
                end_time=end_time, slot_minutes=slot_minutes)
    except IntegrityError:
        raise ScheduleError("Bạn đã có lịch ca này trong ngày đó.")
    return sched, generate_slots(sched)


@transaction.atomic
def delete_schedule(*, doctor, schedule_id):
    sched = (WorkSchedule.objects.select_for_update()
             .filter(pk=schedule_id, doctor=doctor).first())
    if sched is None:
        raise ScheduleError("Không tìm thấy lịch làm việc.")
    if Appointment.objects.filter(slot__schedule=sched).exists():
        raise ScheduleError(
            "Ca này đã có lịch hẹn nên không xóa được. "
            "Hãy dùng \"Báo nghỉ\" để ẩn các khung giờ còn lại.")
    sched.delete()


@transaction.atomic
def add_day_off(*, doctor, date, shift="", reason=""):
    """FR-08: báo nghỉ. Khung giờ ẩn ngay; lịch Đã xác nhận trong thời gian nghỉ bị hủy.
    Trả về (ngày nghỉ, danh sách mã hẹn đã hủy)."""
    if date < timezone.localdate():
        raise ScheduleError("Không thể báo nghỉ cho ngày đã qua.")
    if DayOff.objects.filter(doctor=doctor, date=date).filter(
            Q(shift="") | Q(shift=shift)).exists():
        raise ScheduleError("Bạn đã báo nghỉ cho thời gian này rồi.")

    off = DayOff.objects.create(doctor=doctor, date=date, shift=shift, reason=reason)

    affected = Appointment.objects.filter(
        slot__doctor=doctor, slot__schedule__date=date,
        status=Appointment.Status.CONFIRMED, slot__start_at__gt=timezone.now())
    if shift:
        affected = affected.filter(slot__schedule__shift=shift)
    rows = list(affected.values_list("pk", "code"))
    for pk, _code in rows:
        change_status(pk, Appointment.Status.CANCELLED)
    return off, [code for _pk, code in rows]


@transaction.atomic
def remove_day_off(*, doctor, dayoff_id):
    off = DayOff.objects.filter(pk=dayoff_id, doctor=doctor).first()
    if off is None:
        raise ScheduleError("Không tìm thấy ngày nghỉ.")
    off.delete()