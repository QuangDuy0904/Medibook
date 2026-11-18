from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import DoctorProfile, Specialty, WorkSchedule
from .services import available_slots_qs


def doctor_list(request):
    """FR-05: tìm theo tên, chuyên khoa, ngày khám, ca (sáng/chiều)."""
    q = request.GET.get("q", "").strip()
    specialty = request.GET.get("specialty", "")
    date_str = request.GET.get("date", "")
    shift = request.GET.get("shift", "")
    day = parse_date(date_str) if date_str else None

    doctors = (DoctorProfile.objects.filter(is_active=True)
               .select_related("user", "specialty"))
    if q:
        doctors = doctors.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
            | Q(user__username__icontains=q))
    if specialty.isdigit():
        doctors = doctors.filter(specialty_id=int(specialty))

    valid_shifts = [c[0] for c in WorkSchedule.Shift.choices]
    if day or shift in valid_shifts:
        slots = available_slots_qs().filter(doctor=OuterRef("pk"))
        if day:
            slots = slots.filter(schedule__date=day)
        if shift in valid_shifts:
            slots = slots.filter(schedule__shift=shift)
        doctors = doctors.filter(Exists(slots))

    return render(request, "clinics/doctor_list.html", {
        "doctors": doctors,
        "specialties": Specialty.objects.all(),
        "shift_choices": WorkSchedule.Shift.choices,
        "q": q, "specialty": specialty, "date": date_str, "shift": shift,
    })


def doctor_detail(request, pk):
    """FR-04, FR-06: hồ sơ bác sĩ và lịch trống 14 ngày tới."""
    doctor = get_object_or_404(
        DoctorProfile.objects.select_related("user", "specialty"),
        pk=pk, is_active=True)

    today = timezone.localdate()
    first, last = today, today + timedelta(days=13)
    counts = dict(
        available_slots_qs()
        .filter(doctor=doctor, schedule__date__range=(first, last))
        .order_by().values_list("schedule__date").annotate(n=Count("id")))
    days = [{"date": first + timedelta(days=i),
             "n": counts.get(first + timedelta(days=i), 0)} for i in range(14)]

    selected = parse_date(request.GET.get("date", "") or "")
    if not selected:
        selected = next((d["date"] for d in days if d["n"]), today)
    slots = (available_slots_qs()
             .filter(doctor=doctor, schedule__date=selected)
             .select_related("schedule"))

    return render(request, "clinics/doctor_detail.html", {
        "doctor": doctor, "days": days, "selected": selected, "slots": slots,
    })