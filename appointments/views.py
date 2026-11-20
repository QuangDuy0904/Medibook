import io
from datetime import timedelta

import qrcode
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from accounts.permissions import patient_required

from clinics.models import TimeSlot
from clinics.services import available_slots_qs

from .forms import BookingForm
from .models import Appointment
from .services import (BookingError, book_appointment, cancel_appointment,
                       reschedule_appointment)

LIVE = [Appointment.Status.CONFIRMED, Appointment.Status.CHECKED_IN,
        Appointment.Status.IN_CONSULTATION]


def _my_appointment(request, pk):
    """Chỉ lấy lịch của chính mình, người khác gõ URL sẽ ra 404."""
    return get_object_or_404(
        Appointment.objects.select_related(
            "slot__doctor__user", "slot__doctor__specialty", "profile"),
        pk=pk, booked_by=request.user)


@patient_required
def book(request, slot_id):
    slot = get_object_or_404(
        TimeSlot.objects.select_related("doctor__user", "doctor__specialty"), pk=slot_id)
    if not available_slots_qs().filter(pk=slot.pk).exists():
        messages.error(request, "Khung giờ này không còn trống, vui lòng chọn giờ khác.")
        return redirect("clinics:doctor_detail", pk=slot.doctor_id)

    form = BookingForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            appt = book_appointment(
                user=request.user, slot_id=slot.pk,
                profile_id=form.cleaned_data["profile"].pk,
                symptoms=form.cleaned_data["symptoms"])
        except BookingError as e:
            messages.error(request, str(e))
            if not available_slots_qs().filter(pk=slot.pk).exists():
                return redirect("clinics:doctor_detail", pk=slot.doctor_id)
        else:
            messages.success(request, "Đặt lịch thành công! Hãy lưu mã hẹn hoặc mã QR bên dưới.")
            return redirect("appointments:detail", pk=appt.pk)

    return render(request, "appointments/book.html", {
        "slot": slot, "form": form, "rules": settings.BOOKING_RULES,
        "has_profiles": request.user.profiles.exists(),
    })


@patient_required
def mine(request):
    qs = (Appointment.objects.filter(booked_by=request.user)
          .select_related("slot__doctor__user", "slot__doctor__specialty", "profile"))
    return render(request, "appointments/mine.html", {
        "current": qs.filter(status__in=LIVE).order_by("slot__start_at"),
        "past": qs.exclude(status__in=LIVE),
    })


@patient_required
def detail(request, pk):
    return render(request, "appointments/detail.html", {
        "appt": _my_appointment(request, pk), "rules": settings.BOOKING_RULES})


@patient_required
@require_POST
def cancel(request, pk):
    try:
        cancel_appointment(user=request.user, appointment_id=pk)
        messages.success(request, "Đã hủy lịch hẹn. Khung giờ đã được mở lại cho người khác.")
    except BookingError as e:
        messages.error(request, str(e))
    return redirect("appointments:mine")


@patient_required
def reschedule(request, pk):
    appt = _my_appointment(request, pk)
    if not appt.can_change_online():
        messages.error(request, "Lịch hẹn này không thể đổi trực tuyến.")
        return redirect("appointments:detail", pk=pk)

    if request.method == "POST":
        new_id = request.POST.get("slot", "")
        if not new_id.isdigit():
            messages.error(request, "Vui lòng chọn một khung giờ.")
        else:
            try:
                new = reschedule_appointment(
                    user=request.user, appointment_id=pk, new_slot_id=int(new_id))
            except BookingError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, "Đã đổi lịch hẹn.")
                return redirect("appointments:detail", pk=new.pk)

    today = timezone.localdate()
    slots = (available_slots_qs()
             .filter(doctor=appt.slot.doctor,
                     schedule__date__range=(today, today + timedelta(days=13)))
             .select_related("schedule"))
    return render(request, "appointments/reschedule.html", {"appt": appt, "slots": slots})


@patient_required
def qr_png(request, pk):
    """Ảnh QR chứa mã hẹn (FR-10), sinh tức thời, không lưu file."""
    appt = _my_appointment(request, pk)
    buf = io.BytesIO()
    qrcode.make(appt.code, box_size=8, border=2).save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")