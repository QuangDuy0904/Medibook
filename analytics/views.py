from django.shortcuts import render

from accounts.permissions import admin_required
from clinics.models import DoctorProfile, Specialty

from .services import PERIODS, build_report, parse_filters


@admin_required
def dashboard(request):
    f = parse_filters(request.GET)
    return render(request, "analytics/dashboard.html", {
        "f": f, "report": build_report(f), "periods": PERIODS,
        "specialties": Specialty.objects.all(),
        "doctors": DoctorProfile.objects.select_related("user")
                   .order_by("user__last_name", "user__first_name"),
    })