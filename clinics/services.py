from datetime import datetime, timedelta

from django.utils import timezone

from django.db.models import Exists, OuterRef, Q
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


def available_slots_qs():
    off = DayOff.objects.filter(
        doctor=OuterRef("doctor"), date=OuterRef("schedule__date")
    ).filter(Q(shift="") | Q(shift=OuterRef("schedule__shift")))
    return (TimeSlot.objects.filter(start_at__gt=timezone.now())
            .annotate(is_off=Exists(off)).filter(is_off=False))


def open_slots(doctor, day):
    return available_slots_qs().filter(doctor=doctor, schedule__date=day)