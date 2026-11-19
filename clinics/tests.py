from datetime import time, timedelta

from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from appointments.models import Appointment
from appointments.tests import BookingBase
from clinics.models import DoctorProfile, TimeSlot, WorkSchedule
from clinics.schedule_services import (ScheduleError, add_day_off, create_schedule,
                                       delete_schedule, remove_day_off)
from clinics.services import available_slots_qs


class ScheduleBase(BookingBase):
    def setUp(self):
        super().setUp()
        other_user = User.objects.create_user(
            username="doc2", password="x", role=User.Role.DOCTOR, first_name="Bình")
        self.other = DoctorProfile.objects.create(
            user=other_user, specialty=self.doctor.specialty)
        self.tomorrow = timezone.localdate() + timedelta(days=1)

    def make(self, doctor=None, day=None, shift="MORNING",
             start=time(8, 0), end=time(10, 0), minutes=30):
        return create_schedule(
            doctor=doctor or self.doctor, date=day or self.tomorrow, shift=shift,
            start_time=start, end_time=end, slot_minutes=minutes)


class CreateScheduleTests(ScheduleBase):
    def test_create_generates_slots(self):
        sched, n = self.make()
        self.assertEqual(n, 4)  # 08:00 đến 10:00, mỗi khung 30 phút
        self.assertEqual(TimeSlot.objects.filter(schedule=sched).count(), 4)

    def test_rejects_past_date(self):
        with self.assertRaises(ScheduleError):
            self.make(day=timezone.localdate() - timedelta(days=1))

    def test_rejects_end_before_start(self):
        with self.assertRaises(ScheduleError):
            self.make(start=time(10, 0), end=time(8, 0))

    def test_rejects_too_short(self):
        with self.assertRaises(ScheduleError):
            self.make(start=time(8, 0), end=time(8, 20), minutes=30)

    def test_rejects_duplicate_shift(self):
        self.make()
        with self.assertRaises(ScheduleError):
            self.make(start=time(10, 0), end=time(11, 0))

    def test_rejects_overlap_between_shifts(self):
        self.make(shift="MORNING", start=time(8, 0), end=time(10, 0))
        with self.assertRaises(ScheduleError):
            self.make(shift="AFTERNOON", start=time(9, 0), end=time(12, 0))


class DeleteScheduleTests(ScheduleBase):
    def test_delete_free_schedule(self):
        sched, _ = self.make()
        delete_schedule(doctor=self.doctor, schedule_id=sched.pk)
        self.assertFalse(WorkSchedule.objects.filter(pk=sched.pk).exists())

    def test_delete_blocked_when_has_appointment(self):
        sched, _ = self.make()
        self.book(self.u1, self.p1, TimeSlot.objects.filter(schedule=sched).first())
        with self.assertRaises(ScheduleError):
            delete_schedule(doctor=self.doctor, schedule_id=sched.pk)

    def test_cannot_delete_other_doctors_schedule(self):
        sched, _ = self.make(doctor=self.other)
        with self.assertRaises(ScheduleError):
            delete_schedule(doctor=self.doctor, schedule_id=sched.pk)


class DayOffTests(ScheduleBase):
    def test_day_off_cancels_confirmed_and_hides_slot(self):
        slot = self.make_slot()
        appt = self.book(self.u1, self.p1, slot)
        _off, codes = add_day_off(doctor=self.doctor, date=slot.schedule.date)
        self.assertEqual(codes, [appt.code])
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.CANCELLED)
        self.assertFalse(available_slots_qs().filter(pk=slot.pk).exists())

    def test_shift_day_off_only_affects_that_shift(self):
        slot = self.make_slot()  # ca sáng
        appt = self.book(self.u1, self.p1, slot)
        _off, codes = add_day_off(
            doctor=self.doctor, date=slot.schedule.date, shift="AFTERNOON")
        self.assertEqual(codes, [])
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.CONFIRMED)

    def test_rejects_past_day_off(self):
        with self.assertRaises(ScheduleError):
            add_day_off(doctor=self.doctor, date=timezone.localdate() - timedelta(days=1))

    def test_rejects_duplicate_day_off(self):
        add_day_off(doctor=self.doctor, date=self.tomorrow)
        with self.assertRaises(ScheduleError):
            add_day_off(doctor=self.doctor, date=self.tomorrow)

    def test_remove_day_off_reopens_slot(self):
        slot = self.make_slot()
        off, _ = add_day_off(doctor=self.doctor, date=slot.schedule.date)
        remove_day_off(doctor=self.doctor, dayoff_id=off.pk)
        self.assertTrue(available_slots_qs().filter(pk=slot.pk).exists())


class ScheduleViewTests(ScheduleBase):
    def test_patient_forbidden(self):
        self.client.force_login(self.u1)
        r = self.client.get(reverse("doctor_schedule:home"))
        self.assertEqual(r.status_code, 403)

    def test_doctor_sees_page(self):
        self.client.force_login(self.doctor.user)
        r = self.client.get(reverse("doctor_schedule:home"))
        self.assertEqual(r.status_code, 200)

    def test_add_schedule_via_web(self):
        self.client.force_login(self.doctor.user)
        self.client.post(reverse("doctor_schedule:add"), {
            "date": self.tomorrow.isoformat(), "shift": "MORNING",
            "start_time": "08:00", "end_time": "10:00", "slot_minutes": "30"})
        sched = WorkSchedule.objects.get(doctor=self.doctor, date=self.tomorrow)
        self.assertEqual(TimeSlot.objects.filter(schedule=sched).count(), 4)

    def test_other_doctor_cannot_delete_via_web(self):
        sched, _ = self.make(doctor=self.doctor)
        self.client.force_login(self.other.user)
        self.client.post(reverse("doctor_schedule:delete", args=[sched.pk]))
        self.assertTrue(WorkSchedule.objects.filter(pk=sched.pk).exists())