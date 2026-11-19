from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from accounts.permissions import reception_required
from clinics.models import DoctorProfile, TimeSlot, WorkSchedule
from clinics.services import available_slots_qs, open_slots

from .forms import WalkinForm
from .models import Appointment
from .services import (BookingError, cancel_appointment, check_in,
                       checkin_problem, staff_book_appointment)

STATUS_GROUP = {
    Appointment.Status.CHECKED_IN: "waiting",
    Appointment.Status.IN_CONSULTATION: "consulting",
    Appointment.Status.CONFIRMED: "upcoming",
    Appointment.Status.COMPLETED: "done",
    Appointment.Status.NO_SHOW: "done",
}


def _day(value):
    try:
        return parse_date(value or "") or timezone.localdate()
    except ValueError:
        return timezone.localdate()


@reception_required
def dashboard(request):
    """Hàng đợi trong ngày, nhóm theo bác sĩ (4.3). Không hiển thị lý do khám."""
    day = _day(request.GET.get("date"))
    doctor_id = request.GET.get("doctor", "")
    shift = request.GET.get("shift", "")

    qs = (Appointment.objects.filter(slot__start_at__date=day)
          .exclude(status=Appointment.Status.CANCELLED)
          .select_related("slot__doctor__user", "slot__doctor__specialty",
                          "slot__schedule", "profile"))
    if doctor_id.isdigit():
        qs = qs.filter(slot__doctor_id=int(doctor_id))
    if shift in [c[0] for c in WorkSchedule.Shift.choices]:
        qs = qs.filter(slot__schedule__shift=shift)

    groups = {}
    for a in qs.order_by("slot__doctor_id", "slot__start_at"):
        g = groups.setdefault(a.slot.doctor_id, {
            "doctor": a.slot.doctor, "waiting": [], "consulting": [],
            "upcoming": [], "done": []})
        g[STATUS_GROUP[a.status]].append(a)
    for g in groups.values():
        g["waiting"].sort(key=lambda a: a.queue_number or 0)

    return render(request, "reception/dashboard.html", {
        "groups": list(groups.values()), "day": day,
        "doctors": DoctorProfile.objects.filter(is_active=True).select_related("user"),
        "shift_choices": WorkSchedule.Shift.choices,
        "doctor_id": doctor_id, "shift": shift,
    })


@reception_required
@require_POST
def checkin_lookup(request):
    code = request.POST.get("code", "").strip().upper()
    appt = Appointment.objects.filter(code=code).first()
    if appt is None:
        messages.error(request, "Không tìm thấy lịch hẹn với mã này.")
        return redirect("reception:dashboard")
    return redirect("reception:checkin_confirm", pk=appt.pk)


@reception_required
def checkin_confirm(request, pk):
    """Bước xác thực thông tin trước khi check-in (FR-13)."""
    appt = get_object_or_404(
        Appointment.objects.select_related(
            "slot__doctor__user", "slot__doctor__specialty", "profile"), pk=pk)
    if request.method == "POST":
        try:
            appt = check_in(appt.pk)
        except BookingError as e:
            messages.error(request, str(e))
        else:
            messages.success(
                request, f"Đã check-in {appt.profile.full_name}. "
                         f"Số thứ tự: {appt.queue_number}.")
            return redirect("reception:dashboard")
    return render(request, "reception/checkin_confirm.html",
                  {"appt": appt, "problem": checkin_problem(appt)})


@reception_required
@require_POST
def staff_cancel(request, pk):
    try:
        cancel_appointment(user=request.user, appointment_id=pk, by_staff=True)
        messages.success(request, "Đã hủy lịch hẹn, khung giờ đã mở lại.")
    except BookingError as e:
        messages.error(request, str(e))
    return redirect("reception:dashboard")


@reception_required
def walkin_pick(request):
    """Chọn bác sĩ và ngày để xem khung giờ trống (FR-14)."""
    day = _day(request.GET.get("date"))
    doctors = DoctorProfile.objects.filter(is_active=True).select_related("user", "specialty")
    doctor_id = request.GET.get("doctor", "")
    doctor = doctors.filter(pk=int(doctor_id)).first() if doctor_id.isdigit() else None
    slots = open_slots(doctor, day) if doctor else []
    return render(request, "reception/walkin_pick.html", {
        "doctors": doctors, "doctor": doctor, "doctor_id": doctor_id,
        "day": day, "slots": slots})


@reception_required
def walkin_book(request, slot_id):
    slot = get_object_or_404(
        TimeSlot.objects.select_related("doctor__user", "doctor__specialty"), pk=slot_id)
    if not available_slots_qs().filter(pk=slot.pk).exists():
        messages.error(request, "Khung giờ này không còn trống.")
        return redirect("reception:walkin_pick")

    form = WalkinForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            appt = staff_book_appointment(slot_id=slot.pk, **form.cleaned_data)
        except BookingError as e:
            messages.error(request, str(e))
        else:
            msg = (f"Đã đặt lịch cho {appt.profile.full_name} lúc "
                   f"{timezone.localtime(appt.slot.start_at):%H:%M}. Mã hẹn: {appt.code}.")
            if appt.queue_number:
                msg += f" Số thứ tự: {appt.queue_number}."
            messages.success(request, msg)
            return redirect("reception:dashboard")
    return render(request, "reception/walkin_book.html", {"slot": slot, "form": form})