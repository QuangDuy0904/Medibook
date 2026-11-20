from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from django.utils.dateparse import parse_date

from appointments.models import Appointment
from clinics.models import DoctorProfile

S = Appointment.Status
SHOWED = [S.CHECKED_IN, S.IN_CONSULTATION, S.COMPLETED]  # bệnh nhân đã đến
TRUNC = {"day": TruncDate, "week": TruncWeek, "month": TruncMonth}
PERIODS = [("day", "Theo ngày"), ("week", "Theo tuần"), ("month", "Theo tháng")]
MAX_RANGE_DAYS = 366


def no_show_rate(no_show, showed):
    """FR-18: vắng ÷ (đã đến + vắng), tính theo %. None nếu chưa có ai để tính."""
    due = no_show + showed
    return round(no_show * 100 / due, 1) if due else None


def _counts():
    return {
        "total": Count("id"),
        "completed": Count("id", filter=Q(status=S.COMPLETED)),
        "cancelled": Count("id", filter=Q(status=S.CANCELLED)),
        "no_show": Count("id", filter=Q(status=S.NO_SHOW)),
        "showed": Count("id", filter=Q(status__in=SHOWED)),
    }


def _date(value):
    try:
        return parse_date(value or "")
    except ValueError:
        return None


def _int(value):
    return int(value) if value and str(value).isdigit() else None


def _as_date(value):
    return timezone.localtime(value).date() if isinstance(value, datetime) else value


def parse_filters(params):
    today = timezone.localdate()
    end = _date(params.get("to")) or today
    start = _date(params.get("from")) or end - timedelta(days=29)
    if start > end:
        start, end = end, start
    if (end - start).days > MAX_RANGE_DAYS:
        start = end - timedelta(days=MAX_RANGE_DAYS)
    period = params.get("period")
    return {
        "start": start, "end": end,
        "period": period if period in TRUNC else "day",
        "specialty": _int(params.get("specialty")),
        "doctor": _int(params.get("doctor")),
    }


def _finish(rows, label):
    rows = list(rows)
    top = max((r["total"] for r in rows), default=0)
    return [{
        "label": label(r),
        **{k: r[k] for k in ("total", "completed", "cancelled", "no_show", "showed")},
        "rate": no_show_rate(r["no_show"], r["showed"]),
        "bar": round(r["total"] * 100 / top) if top else 0,
    } for r in rows]


def build_report(f):
    qs = Appointment.objects.filter(
        slot__start_at__date__gte=f["start"], slot__start_at__date__lte=f["end"])
    if f["specialty"]:
        qs = qs.filter(slot__doctor__specialty_id=f["specialty"])
    if f["doctor"]:
        qs = qs.filter(slot__doctor_id=f["doctor"])

    totals = qs.order_by().aggregate(**_counts())
    by_source = dict(qs.order_by().values_list("source").annotate(n=Count("id")))
    summary = {
        **totals, "rate": no_show_rate(totals["no_show"], totals["showed"]),
        "online": by_source.get("ONLINE", 0), "reception": by_source.get("RECEPTION", 0),
    }

    fmt = {"day": "%d/%m/%Y", "week": "Tuần %d/%m/%Y", "month": "%m/%Y"}[f["period"]]
    by_period = _finish(
        qs.annotate(p=TRUNC[f["period"]]("slot__start_at"))
        .values("p").annotate(**_counts()).order_by("p"),
        lambda r: _as_date(r["p"]).strftime(fmt))

    by_specialty = _finish(
        qs.order_by().values("slot__doctor__specialty__name")
        .annotate(**_counts()).order_by("-total"),
        lambda r: r["slot__doctor__specialty__name"])

    doctor_rows = list(
        qs.order_by().values("slot__doctor_id").annotate(**_counts()).order_by("-total"))
    names = {d.pk: str(d) for d in DoctorProfile.objects.select_related("user").filter(
        pk__in=[r["slot__doctor_id"] for r in doctor_rows])}
    by_doctor = _finish(doctor_rows, lambda r: names.get(r["slot__doctor_id"], "?"))

    return {"summary": summary, "by_period": by_period,
            "by_specialty": by_specialty, "by_doctor": by_doctor}