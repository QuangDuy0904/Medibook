import csv

from django.http import HttpResponse
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


def _safe(value):
    """Chống chèn công thức khi mở bằng Excel: ô văn bản bắt đầu bằng = + - @ bị vô hiệu hóa."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _rate(value):
    return "" if value is None else f"{value}%"


@admin_required
def export_csv(request):
    """Xuất đúng báo cáo đang xem (cùng bộ lọc) ra file CSV."""
    f = parse_filters(request.GET)
    report = build_report(f)
    s = report["summary"]

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="thong-ke_{f["start"]}_{f["end"]}.csv"')
    response.write("\ufeff")  # BOM để Excel nhận đúng tiếng Việt
    w = csv.writer(response)

    w.writerow(["BÁO CÁO THỐNG KÊ MEDIBOOK"])
    w.writerow(["Từ ngày", f["start"].strftime("%d/%m/%Y"),
                "Đến ngày", f["end"].strftime("%d/%m/%Y")])
    w.writerow([])
    w.writerow(["TỔNG QUAN"])
    for label, key in (("Tổng số cuộc hẹn", "total"), ("Hoàn thành", "completed"),
                       ("Đã hủy", "cancelled"), ("Vắng mặt", "no_show"),
                       ("Đã đến khám", "showed"), ("Đặt trực tuyến", "online"),
                       ("Đặt tại quầy", "reception")):
        w.writerow([label, s[key]])
    w.writerow(["Tỷ lệ vắng mặt", _rate(s["rate"])])

    for title, first, rows in (("THEO THỜI GIAN", "Kỳ", report["by_period"]),
                               ("THEO CHUYÊN KHOA", "Chuyên khoa", report["by_specialty"]),
                               ("THEO BÁC SĨ", "Bác sĩ", report["by_doctor"])):
        w.writerow([])
        w.writerow([title])
        w.writerow([first, "Số cuộc hẹn", "Hoàn thành", "Đã hủy",
                    "Vắng mặt", "Đã đến", "Tỷ lệ vắng"])
        for r in rows:
            w.writerow([_safe(r["label"]), r["total"], r["completed"], r["cancelled"],
                        r["no_show"], r["showed"], _rate(r["rate"])])
    return response