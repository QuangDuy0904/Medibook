from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from accounts.permissions import doctor_required, patient_required
from appointments.models import Appointment
from appointments.services import BookingError
from clinics.models import DoctorProfile, WorkSchedule

from .forms import NoteForm
from .models import ConsultationNote
from .services import call_next_patient, save_consultation_note

S = Appointment.Status
GROUP = {S.CHECKED_IN: "waiting", S.IN_CONSULTATION: "consulting",
         S.CONFIRMED: "upcoming", S.COMPLETED: "done", S.NO_SHOW: "done"}


def _day(value):
    try:
        return parse_date(value or "") or timezone.localdate()
    except ValueError:
        return timezone.localdate()


def _my_doctor(request):
    doctor = (DoctorProfile.objects.filter(user=request.user)
              .select_related("user", "specialty").first())
    if doctor is None:
        raise PermissionDenied
    return doctor


@doctor_required
def dashboard(request):
    """5.1: bệnh nhân của chính bác sĩ này, theo ngày và ca."""
    doctor = (DoctorProfile.objects.filter(user=request.user)
              .select_related("user", "specialty").first())
    if doctor is None:
        return render(request, "doctor/dashboard.html", {"doctor": None})

    day = _day(request.GET.get("date"))
    shift = request.GET.get("shift", "")
    qs = (Appointment.objects.filter(slot__doctor=doctor, slot__start_at__date=day)
          .exclude(status=S.CANCELLED)
          .select_related("slot__schedule", "profile"))
    if shift in [c[0] for c in WorkSchedule.Shift.choices]:
        qs = qs.filter(slot__schedule__shift=shift)

    groups = {"consulting": [], "waiting": [], "upcoming": [], "done": []}
    for a in qs.order_by("slot__start_at"):
        groups[GROUP[a.status]].append(a)
    groups["waiting"].sort(key=lambda a: a.queue_number or 0)

    return render(request, "doctor/dashboard.html", {
        "doctor": doctor, "groups": groups, "day": day, "shift": shift,
        "shift_choices": WorkSchedule.Shift.choices,
        "is_today": day == timezone.localdate(),
    })


@doctor_required
@require_POST
def call_next(request):
    doctor = _my_doctor(request)
    try:
        appt = call_next_patient(doctor)
    except BookingError as e:
        messages.error(request, str(e))
        return redirect("doctor:dashboard")
    return redirect("doctor:consult", pk=appt.pk)


@doctor_required
def consult(request, pk):
    """5.2: xem thông tin bệnh nhân và ghi chẩn đoán, lời dặn."""
    doctor = _my_doctor(request)
    appt = get_object_or_404(
        Appointment.objects.select_related("slot__schedule", "profile"),
        pk=pk, slot__doctor=doctor)  # lịch của bác sĩ khác: 404

    note = ConsultationNote.objects.filter(appointment=appt).first()
    can_write = appt.status in (S.IN_CONSULTATION, S.COMPLETED)
    initial = {"diagnosis": note.diagnosis, "advice": note.advice} if note else None
    form = NoteForm(request.POST or None, initial=initial)

    if request.method == "POST" and can_write and form.is_valid():
        try:
            save_consultation_note(
                doctor=doctor, appointment_id=appt.pk,
                diagnosis=form.cleaned_data["diagnosis"],
                advice=form.cleaned_data["advice"])
        except BookingError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, "Đã lưu kết quả khám.")
            return redirect("doctor:dashboard")

    # Chỉ hiện các lần khám trước với CHÍNH bác sĩ này (bảo mật)
    previous = (Appointment.objects
                .filter(profile=appt.profile, slot__doctor=doctor, status=S.COMPLETED)
                .exclude(pk=appt.pk).select_related("slot", "note")
                .order_by("-slot__start_at")[:5])

    return render(request, "doctor/consult.html", {
        "appt": appt, "form": form, "can_write": can_write, "previous": previous})

@patient_required
def history(request):
    """5.3: bệnh nhân xem lại các lần khám kèm kết luận (FR-16)."""
    visits = (Appointment.objects.filter(booked_by=request.user, status=S.COMPLETED)
              .select_related("slot__doctor__user", "slot__doctor__specialty",
                              "profile", "note"))
    return render(request, "records/history.html", {"visits": visits})