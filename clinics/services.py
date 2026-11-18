from datetime import datetime, timedelta

from django.utils import timezone

from .models import DayOff, TimeSlot


def generate_slots(schedule):
    """Chia một ca làm việc thành các khung giờ. Chạy lại nhiều lần không bị trùng."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(schedule.date, schedule.start_time), tz)
    end = timezone.make_aware(datetime.combine(schedule.date, schedule.end_time), tz)
    step = timedelta(minutes=schedule.slot_minutes)

    slots, cur = [], start
    while cur + step <= end:
        slots.append(TimeSlot(doctor=schedule.doctor, schedule=schedule,
                              start_at=cur, end_at=cur + step))
        cur += step
    TimeSlot.objects.bulk_create(slots, ignore_conflicts=True)
    return len(slots)


def open_slots(doctor, day):
    """Khung giờ của bác sĩ trong một ngày, đã bỏ giờ quá khứ và ca nghỉ (FR-08).
    Giai đoạn 3 sẽ loại thêm các slot đã có lịch hẹn."""
    qs = TimeSlot.objects.filter(doctor=doctor, start_at__date=day,
                                 start_at__gt=timezone.now())
    for off in DayOff.objects.filter(doctor=doctor, date=day):
        if not off.shift:
            return qs.none()
        qs = qs.exclude(schedule__shift=off.shift)
    return qs