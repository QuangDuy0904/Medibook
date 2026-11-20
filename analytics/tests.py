from datetime import timedelta
import csv, io

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment
from appointments.test_reception import ReceptionBase
from clinics.models import DoctorProfile, Specialty

from .services import build_report, no_show_rate, parse_filters

S = Appointment.Status


class RateTests(TestCase):
    def test_rate(self):
        self.assertEqual(no_show_rate(1, 3), 25.0)

    def test_all_no_show(self):
        self.assertEqual(no_show_rate(2, 0), 100.0)

    def test_none_when_nobody_due(self):
        self.assertIsNone(no_show_rate(0, 0))


class ReportBase(ReceptionBase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            username="adm", password="x12345!", role=User.Role.ADMIN)
        today = timezone.localdate()
        self.params = {"from": (today - timedelta(days=1)).isoformat(),
                       "to": (today + timedelta(days=1)).isoformat()}

    def appt(self, minutes, status, doctor=None):
        return Appointment.objects.create(
            slot=self.slot_in(minutes, doctor=doctor), profile=self.p1,
            booked_by=self.u1, status=status)

    def report(self, **extra):
        return build_report(parse_filters({**self.params, **extra}))

    def second_doctor(self, specialty_name="Nhi"):
        user = User.objects.create_user(
            username="doc2", password="x", role=User.Role.DOCTOR, first_name="Bình")
        return DoctorProfile.objects.create(
            user=user, specialty=Specialty.objects.create(name=specialty_name))


class ReportTests(ReportBase):
    def test_summary_counts_and_rate(self):
        self.appt(-10, S.COMPLETED)
        self.appt(-20, S.COMPLETED)
        self.appt(-30, S.NO_SHOW)
        self.appt(-40, S.CANCELLED)
        self.appt(60, S.CONFIRMED)
        s = self.report()["summary"]
        self.assertEqual((s["total"], s["completed"], s["no_show"], s["cancelled"]),
                         (5, 2, 1, 1))
        self.assertEqual(s["rate"], 33.3)  # 1 vắng / (2 đã đến + 1 vắng)

    def test_rate_none_when_nobody_due(self):
        self.appt(60, S.CONFIRMED)
        self.appt(-40, S.CANCELLED)
        self.assertIsNone(self.report()["summary"]["rate"])

    def test_group_by_doctor_and_filter(self):
        other = self.second_doctor()
        self.appt(-10, S.COMPLETED)
        self.appt(-20, S.COMPLETED)
        self.appt(-30, S.COMPLETED, doctor=other)
        rows = self.report()["by_doctor"]
        self.assertEqual(sorted(r["total"] for r in rows), [1, 2])
        only = self.report(doctor=other.pk)
        self.assertEqual(only["summary"]["total"], 1)
        self.assertEqual(len(only["by_doctor"]), 1)

    def test_group_by_specialty(self):
        other = self.second_doctor("Tim mạch")
        self.appt(-10, S.COMPLETED)
        self.appt(-20, S.COMPLETED, doctor=other)
        labels = {r["label"] for r in self.report()["by_specialty"]}
        self.assertEqual(labels, {"Nội tổng quát", "Tim mạch"})
        by_spec = self.report(specialty=other.specialty_id)
        self.assertEqual(by_spec["summary"]["total"], 1)

    def test_group_by_month_merges_same_month(self):
        self.appt(-10, S.COMPLETED)
        self.appt(-20, S.COMPLETED)
        rows = self.report(period="month")["by_period"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total"], 2)

    def test_date_range_excludes_old_appointments(self):
        self.appt(-60 * 24 * 10, S.COMPLETED)  # 10 ngày trước, ngoài khoảng lọc
        self.assertEqual(self.report()["summary"]["total"], 0)

    def test_swapped_dates_are_fixed(self):
        f = parse_filters({"from": "2026-12-31", "to": "2026-01-01"})
        self.assertLessEqual(f["start"], f["end"])

    def test_range_is_capped(self):
        today = timezone.localdate().isoformat()
        f = parse_filters({"from": "2000-01-01", "to": today})
        self.assertLessEqual((f["end"] - f["start"]).days, 366)

    def test_invalid_input_falls_back(self):
        f = parse_filters({"from": "abc", "to": "2026-13-45",
                           "period": "hour", "specialty": "x"})
        self.assertEqual(f["period"], "day")
        self.assertIsNone(f["specialty"])


class DashboardViewTests(ReportBase):
    def test_admin_sees_dashboard(self):
        self.appt(-10, S.COMPLETED)
        self.client.force_login(self.admin)
        r = self.client.get(reverse("analytics:dashboard"), self.params)
        self.assertContains(r, "Tỷ lệ vắng mặt")

    def test_bad_params_do_not_crash(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("analytics:dashboard"),
                            {"from": "abc", "to": "2026-13-45", "period": "x", "doctor": "y"})
        self.assertEqual(r.status_code, 200)

    def test_patient_forbidden(self):
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("analytics:dashboard")).status_code, 403)

class ExportTests(ReportBase):
    def rows(self, **extra):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("analytics:export"), {**self.params, **extra})
        self.assertEqual(r.status_code, 200)
        text = r.content.decode("utf-8-sig")
        return r, list(csv.reader(io.StringIO(text)))

    def test_admin_downloads_csv(self):
        self.appt(-10, S.COMPLETED)
        self.appt(-20, S.NO_SHOW)
        r, rows = self.rows()
        self.assertTrue(r["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertTrue(r.content.startswith(b"\xef\xbb\xbf"))  # có BOM cho Excel
        self.assertIn(["Tổng số cuộc hẹn", "2"], rows)
        self.assertIn(["Vắng mặt", "1"], rows)

    def test_export_respects_filters(self):
        other = self.second_doctor()
        self.appt(-10, S.COMPLETED)
        self.appt(-20, S.COMPLETED, doctor=other)
        _r, rows = self.rows(doctor=other.pk)
        self.assertIn(["Tổng số cuộc hẹn", "1"], rows)

    def test_formula_in_label_is_neutralised(self):
        other = self.second_doctor("=HYPERLINK(\"http://x\")")
        self.appt(-10, S.COMPLETED, doctor=other)
        _r, rows = self.rows()
        cells = [c for row in rows for c in row]
        self.assertFalse(any(c.startswith("=") for c in cells))
        self.assertTrue(any(c.startswith("'=") for c in cells))

    def test_patient_forbidden(self):
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("analytics:export")).status_code, 403)