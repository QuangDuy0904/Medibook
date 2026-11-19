from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.permissions import doctor_required

from .forms import DayOffForm, ScheduleForm
from .models import DoctorProfile, WorkSchedule
from .schedule_services import (ScheduleError, add_day_off, create_schedule,
                                delete_schedule, remove_day_off)

ACTIVE = ["CONFIRMED", "CHECKED_IN", "IN_CONSULTATION", "COMPLETED"]


def _doctor(request):
    doctor = (DoctorProfile.objects.filter(user=request.user)
              .select_related("user", "specialty").first())
    if doctor is None:
        raise PermissionDenied
    return doctor


@doctor_required
def home(request):
    doctor = _doctor(request)
    today = timezone.localdate()
    schedules = (doctor.schedules.filter(date__gte=today)
                 .annotate(
                     n_slots=Count("slots", distinct=True),
                     n_booked=Count("slots__appointments", distinct=True,
                                    filter=Q(slots__appointments__status__in=ACTIVE)))
                 .order_by("date", "start_time"))
    return render(request, "doctor/schedule.html", {
        "doctor": doctor, "schedules": schedules,
        "days_off": doctor.days_off.filter(date__gte=today).order_by("date"),
        "schedule_form": ScheduleForm(initial={"slot_minutes": doctor.slot_minutes}),
        "off_form": DayOffForm(),
    })


@doctor_required
@require_POST
def add(request):
    doctor = _doctor(request)
    form = ScheduleForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Thông tin chưa hợp lệ, vui lòng kiểm tra lại ngày và giờ.")
        return redirect("doctor_schedule:home")
    try:
        sched, n = create_schedule(doctor=doctor, **form.cleaned_data)
    except ScheduleError as e:
        messages.error(request, str(e))
    else:
        messages.success(
            request, f"Đã tạo ca {sched.get_shift_display().lower()} ngày "
                     f"{sched.date:%d/%m/%Y}, sinh {n} khung giờ.")
    return redirect("doctor_schedule:home")


@doctor_required
@require_POST
def delete(request, pk):
    try:
        delete_schedule(doctor=_doctor(request), schedule_id=pk)
    except ScheduleError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Đã xóa ca làm việc.")
    return redirect("doctor_schedule:home")


@doctor_required
@require_POST
def off_add(request):
    doctor = _doctor(request)
    form = DayOffForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Thông tin chưa hợp lệ, vui lòng kiểm tra lại.")
        return redirect("doctor_schedule:home")
    try:
        off, codes = add_day_off(doctor=doctor, **form.cleaned_data)
    except ScheduleError as e:
        messages.error(request, str(e))
    else:
        msg = f"Đã báo nghỉ ngày {off.date:%d/%m/%Y}. Các khung giờ đã được ẩn."
        if codes:
            msg += (f" Đã hủy {len(codes)} lịch hẹn: {', '.join(codes)}. "
                    "Hãy báo bệnh nhân qua quầy tiếp tân.")
        messages.warning(request, msg)
    return redirect("doctor_schedule:home")


@doctor_required
@require_POST
def off_delete(request, pk):
    try:
        remove_day_off(doctor=_doctor(request), dayoff_id=pk)
    except ScheduleError as e:
        messages.error(request, str(e))
    else:
        messages.success(
            request, "Đã bỏ báo nghỉ, khung giờ mở lại. "
                     "Lịch hẹn đã bị hủy trước đó không tự khôi phục.")
    return redirect("doctor_schedule:home")