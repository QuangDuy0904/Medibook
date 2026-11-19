from datetime import time, timedelta

from django.test import TestCase  # noqa: F401  (dùng gián tiếp qua BookingBase)
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from clinics.models import DoctorProfile, TimeSlot, WorkSchedule

from .models import Appointment
from .services import (BookingError, cancel_appointment, check_in,
                       staff_book_appointment)
from .tests import BookingBase


class ReceptionBase(BookingBase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(
            username="rec", password="x12345!", role=User.Role.RECEPTIONIST)

    def slot_in(self, minutes, doctor=None):
        """Khung giờ bắt đầu sau `minutes` phút (âm = đã bắt đầu)."""
        doctor = doctor or self.doctor
        start = timezone.now() + timedelta(minutes=minutes)
        schedule, _ = WorkSchedule.objects.get_or_create(
            doctor=doctor, date=timezone.localtime(start).date(), shift="MORNING",
            defaults={"start_time": time(0, 0), "end_time": time(23, 59)})
        return TimeSlot.objects.create(
            doctor=doctor, schedule=schedule,
            start_at=start, end_at=start + timedelta(minutes=30))


class CheckInServiceTests(ReceptionBase):
    def test_check_in_assigns_queue_number(self):
        a = check_in(self.book(self.u1, self.p1, self.slot_in(3)).pk)
        self.assertEqual(a.status, Appointment.Status.CHECKED_IN)
        self.assertEqual(a.queue_number, 1)
        self.assertIsNotNone(a.checked_in_at)

    def test_queue_numbers_increase_per_doctor(self):
        a1 = self.book(self.u1, self.p1, self.slot_in(3))
        a2 = self.book(self.u2, self.p2, self.slot_in(5))
        self.assertEqual(check_in(a1.pk).queue_number, 1)
        self.assertEqual(check_in(a2.pk).queue_number, 2)

    def test_queue_is_separate_for_each_doctor(self):
        other_user = User.objects.create_user(
            username="doc2", password="x", role=User.Role.DOCTOR)
        other = DoctorProfile.objects.create(
            user=other_user, specialty=self.doctor.specialty)
        a1 = self.book(self.u1, self.p1, self.slot_in(3))
        a2 = self.book(self.u2, self.p2, self.slot_in(3, doctor=other))
        self.assertEqual(check_in(a1.pk).queue_number, 1)
        self.assertEqual(check_in(a2.pk).queue_number, 1)

    def test_too_early(self):
        a = self.book(self.u1, self.p1, self.slot_in(180))
        with self.assertRaises(BookingError):
            check_in(a.pk)

    def test_too_late(self):
        a = Appointment.objects.create(
            slot=self.slot_in(-20), profile=self.p1, booked_by=self.u1)
        with self.assertRaises(BookingError):
            check_in(a.pk)

    def test_late_but_within_grace(self):
        a = Appointment.objects.create(
            slot=self.slot_in(-10), profile=self.p1, booked_by=self.u1)
        self.assertEqual(check_in(a.pk).status, Appointment.Status.CHECKED_IN)

    def test_cannot_check_in_twice(self):
        a = self.book(self.u1, self.p1, self.slot_in(3))
        check_in(a.pk)
        with self.assertRaises(BookingError):
            check_in(a.pk)

    def test_cannot_check_in_cancelled(self):
        a = self.book(self.u1, self.p1, self.slot_in(3))
        cancel_appointment(user=self.staff, appointment_id=a.pk, by_staff=True)
        with self.assertRaises(BookingError):
            check_in(a.pk)


class WalkinTests(ReceptionBase):
    def test_creates_account_and_profile(self):
        a = staff_book_appointment(
            slot_id=self.slot_in(10).pk, phone="0987654321",
            full_name="Trần Văn B", symptoms="Sốt")
        self.assertEqual(a.status, Appointment.Status.CONFIRMED)
        self.assertEqual(a.source, Appointment.Source.RECEPTION)
        self.assertEqual(a.profile.full_name, "Trần Văn B")
        self.assertEqual(a.booked_by.phone, "0987654321")
        self.assertFalse(a.booked_by.has_usable_password())

    def test_reuses_account_with_same_phone(self):
        a = staff_book_appointment(
            slot_id=self.slot_in(10).pk, phone=self.u1.phone, full_name="u1")
        self.assertEqual(a.booked_by_id, self.u1.pk)
        self.assertEqual(a.profile_id, self.p1.pk)

    def test_new_person_on_existing_phone_gets_new_profile(self):
        a = staff_book_appointment(
            slot_id=self.slot_in(10).pk, phone=self.u1.phone, full_name="Bé An")
        self.assertEqual(a.booked_by_id, self.u1.pk)
        self.assertNotEqual(a.profile_id, self.p1.pk)
        self.assertEqual(a.profile.relationship, "OTHER")

    def test_ignores_br02_and_br05(self):
        self.book(self.u1, self.p1, self.make_slot(24))
        self.book(self.u1, self.p1, self.make_slot(25))
        self.u1.lock_booking()
        a = staff_book_appointment(
            slot_id=self.make_slot(26).pk, phone=self.u1.phone, full_name="u1")
        self.assertEqual(a.status, Appointment.Status.CONFIRMED)

    def test_rejects_taken_slot(self):
        slot = self.slot_in(10)
        self.book(self.u1, self.p1, slot)
        with self.assertRaises(BookingError):
            staff_book_appointment(slot_id=slot.pk, phone="0987654321", full_name="X")

    def test_rejects_bad_phone(self):
        with self.assertRaises(BookingError):
            staff_book_appointment(
                slot_id=self.slot_in(10).pk, phone="123", full_name="X")

    def test_check_in_now(self):
        a = staff_book_appointment(
            slot_id=self.slot_in(10).pk, phone="0987654321",
            full_name="X", check_in_now=True)
        self.assertEqual(a.status, Appointment.Status.CHECKED_IN)
        self.assertEqual(a.queue_number, 1)

    def test_check_in_now_too_early_rolls_back(self):
        slot = self.slot_in(180)
        with self.assertRaises(BookingError):
            staff_book_appointment(
                slot_id=slot.pk, phone="0987654321", full_name="X", check_in_now=True)
        self.assertFalse(Appointment.objects.filter(slot=slot).exists())
        self.assertFalse(User.objects.filter(phone="0987654321").exists())


class ReceptionViewTests(ReceptionBase):
    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("reception:dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)

    def test_patient_forbidden(self):
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("reception:dashboard")).status_code, 403)
        r = self.client.post(reverse("reception:checkin_lookup"), {"code": "X"})
        self.assertEqual(r.status_code, 403)

    def test_receptionist_can_open_pages(self):
        self.client.force_login(self.staff)
        for name in ("reception:dashboard", "reception:walkin_pick"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_lookup_and_confirm_flow(self):
        a = self.book(self.u1, self.p1, self.slot_in(3))
        self.client.force_login(self.staff)
        r = self.client.post(reverse("reception:checkin_lookup"),
                             {"code": a.code.lower()})
        self.assertRedirects(r, reverse("reception:checkin_confirm", args=[a.pk]))
        r = self.client.post(reverse("reception:checkin_confirm", args=[a.pk]))
        self.assertRedirects(r, reverse("reception:dashboard"))
        a.refresh_from_db()
        self.assertEqual(a.status, Appointment.Status.CHECKED_IN)

    def test_unknown_code(self):
        self.client.force_login(self.staff)
        r = self.client.post(reverse("reception:checkin_lookup"),
                             {"code": "APT-NOPE"}, follow=True)
        self.assertContains(r, "Không tìm thấy")

    def test_reception_does_not_see_symptoms(self):
        a = self.book(self.u1, self.p1, self.slot_in(3))  # triệu chứng: "Đau đầu"
        self.client.force_login(self.staff)
        day = timezone.localtime(a.slot.start_at).date().isoformat()
        r = self.client.get(reverse("reception:dashboard"), {"date": day})
        self.assertContains(r, a.code)               # trang có hiện lịch hẹn
        self.assertNotContains(r, "Đau đầu")
        r = self.client.get(reverse("reception:checkin_confirm", args=[a.pk]))
        self.assertNotContains(r, "Đau đầu")

    def test_staff_can_cancel_inside_two_hour_window(self):
        a = self.book(self.u1, self.p1, self.slot_in(30))
        self.client.force_login(self.staff)
        self.client.post(reverse("reception:cancel", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Appointment.Status.CANCELLED)

    def test_walkin_via_web(self):
        slot = self.slot_in(10)
        self.client.force_login(self.staff)
        r = self.client.post(
            reverse("reception:walkin_book", args=[slot.pk]),
            {"full_name": "Lê Văn C", "phone": "0977777777",
             "symptoms": "Ho", "check_in_now": "on"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Appointment.objects.get(slot=slot).status,
                         Appointment.Status.CHECKED_IN)