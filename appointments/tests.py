from datetime import time, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import PatientProfile, User
from clinics.models import DayOff, DoctorProfile, Specialty, TimeSlot, WorkSchedule
from clinics.services import available_slots_qs

from .models import Appointment
from .services import (BookingError, book_appointment, cancel_appointment,
                       change_status, reschedule_appointment)


class BookingBase(TestCase):
    def setUp(self):
        spec = Specialty.objects.create(name="Nội tổng quát")
        doc_user = User.objects.create_user(
            username="doc",
            email="doc@medibook.local",
            password="x",
            role=User.Role.DOCTOR,
            first_name="An",
        )
        self.doctor = DoctorProfile.objects.create(user=doc_user, specialty=spec)
        self.u1, self.p1 = self.make_patient("u1", "0911111111")
        self.u2, self.p2 = self.make_patient("u2", "0922222222")

    def make_patient(self, username, phone):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@medibook.local",
            password="x",
            phone=phone,
        )
        profile = PatientProfile.objects.create(
            owner=user, relationship="SELF", full_name=username
        )
        return user, profile

    def make_slot(self, hours_ahead=24):
        start = (timezone.now().replace(minute=0, second=0, microsecond=0)
                 + timedelta(hours=hours_ahead))
        schedule, _ = WorkSchedule.objects.get_or_create(
            doctor=self.doctor, date=timezone.localtime(start).date(), shift="MORNING",
            defaults={"start_time": time(8), "end_time": time(11)})
        return TimeSlot.objects.create(
            doctor=self.doctor, schedule=schedule,
            start_at=start, end_at=start + timedelta(minutes=30))

    def book(self, user, profile, slot):
        return book_appointment(user=user, slot_id=slot.pk,
                                profile_id=profile.pk, symptoms="Đau đầu")


class BookingRulesTests(BookingBase):
    def test_book_success(self):
        appt = self.book(self.u1, self.p1, self.make_slot())
        self.assertEqual(appt.status, Appointment.Status.CONFIRMED)
        self.assertTrue(appt.code.startswith("APT-"))

    def test_br01_service_rejects_second_booking(self):
        slot = self.make_slot()
        self.book(self.u1, self.p1, slot)
        with self.assertRaises(BookingError):
            self.book(self.u2, self.p2, slot)

    def test_br01_database_constraint(self):
        slot = self.make_slot()
        self.book(self.u1, self.p1, slot)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appointment.objects.create(slot=slot, profile=self.p2, booked_by=self.u2)

    def test_booked_slot_is_hidden_then_reopens_after_cancel(self):
        slot = self.make_slot()
        appt = self.book(self.u1, self.p1, slot)
        self.assertFalse(available_slots_qs().filter(pk=slot.pk).exists())
        cancel_appointment(user=self.u1, appointment_id=appt.pk)
        self.assertTrue(available_slots_qs().filter(pk=slot.pk).exists())
        self.book(self.u2, self.p2, slot)  # người khác đặt được

    def test_br02_max_two_active(self):
        self.book(self.u1, self.p1, self.make_slot(24))
        self.book(self.u1, self.p1, self.make_slot(25))
        with self.assertRaises(BookingError):
            self.book(self.u1, self.p1, self.make_slot(26))

    def test_br03_cannot_cancel_within_two_hours(self):
        appt = self.book(self.u1, self.p1, self.make_slot(1))
        with self.assertRaises(BookingError):
            cancel_appointment(user=self.u1, appointment_id=appt.pk)

    def test_cannot_cancel_other_users_appointment(self):
        appt = self.book(self.u1, self.p1, self.make_slot())
        with self.assertRaises(BookingError):
            cancel_appointment(user=self.u2, appointment_id=appt.pk)

    def test_br05_locked_user_cannot_book(self):
        self.u1.lock_booking()
        with self.assertRaises(BookingError):
            self.book(self.u1, self.p1, self.make_slot())

    def test_cannot_use_someone_elses_profile(self):
        with self.assertRaises(BookingError):
            self.book(self.u1, self.p2, self.make_slot())

    def test_day_off_hides_and_blocks_slot(self):
        slot = self.make_slot()
        DayOff.objects.create(doctor=self.doctor, date=slot.schedule.date, shift="")
        self.assertFalse(available_slots_qs().filter(pk=slot.pk).exists())
        with self.assertRaises(BookingError):
            self.book(self.u1, self.p1, slot)


class RescheduleAndStatusTests(BookingBase):
    def test_reschedule_moves_appointment(self):
        a, b = self.make_slot(24), self.make_slot(25)
        old = self.book(self.u1, self.p1, a)
        new = reschedule_appointment(user=self.u1, appointment_id=old.pk, new_slot_id=b.pk)
        old.refresh_from_db()
        self.assertEqual(old.status, Appointment.Status.CANCELLED)
        self.assertEqual(new.slot_id, b.pk)
        self.assertEqual(new.profile_id, self.p1.pk)

    def test_reschedule_failure_keeps_old_appointment(self):
        a, b = self.make_slot(24), self.make_slot(25)
        old = self.book(self.u1, self.p1, a)
        self.book(self.u2, self.p2, b)  # b đã có người đặt
        with self.assertRaises(BookingError):
            reschedule_appointment(user=self.u1, appointment_id=old.pk, new_slot_id=b.pk)
        old.refresh_from_db()
        self.assertEqual(old.status, Appointment.Status.CONFIRMED)

    def test_valid_status_flow(self):
        appt = self.book(self.u1, self.p1, self.make_slot())
        for s in ["CHECKED_IN", "IN_CONSULTATION", "COMPLETED"]:
            appt = change_status(appt.pk, s)
        self.assertEqual(appt.status, Appointment.Status.COMPLETED)
        self.assertIsNotNone(appt.checked_in_at)

    def test_invalid_status_jump(self):
        appt = self.book(self.u1, self.p1, self.make_slot())
        with self.assertRaises(BookingError):
            change_status(appt.pk, "COMPLETED")
        change_status(appt.pk, "CHECKED_IN")
        change_status(appt.pk, "IN_CONSULTATION")
        change_status(appt.pk, "COMPLETED")
        with self.assertRaises(BookingError):
            change_status(appt.pk, "CANCELLED")