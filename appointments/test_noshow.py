from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from .models import Appointment
from .services import BookingError, mark_no_show, process_overdue_appointments
from .test_reception import ReceptionBase

S = Appointment.Status


class NoShowBase(ReceptionBase):
    def appt(self, user, profile, minutes, status=S.CONFIRMED):
        """Lịch hẹn trực tiếp trong DB; minutes âm nghĩa là giờ hẹn đã qua."""
        return Appointment.objects.create(
            slot=self.slot_in(minutes), profile=profile, booked_by=user, status=status)


class NoShowServiceTests(NoShowBase):
    def test_overdue_marked_no_show(self):
        a = self.appt(self.u1, self.p1, -20)
        self.assertEqual(process_overdue_appointments(), 1)
        a.refresh_from_db()
        self.assertEqual(a.status, S.NO_SHOW)

    def test_not_yet_overdue_untouched(self):
        a = self.appt(self.u1, self.p1, -10)  # mới trễ 10 phút, còn trong thời gian cho phép
        self.assertEqual(process_overdue_appointments(), 0)
        a.refresh_from_db()
        self.assertEqual(a.status, S.CONFIRMED)

    def test_checked_in_untouched(self):
        a = self.appt(self.u1, self.p1, -20, status=S.CHECKED_IN)
        self.assertEqual(process_overdue_appointments(), 0)
        a.refresh_from_db()
        self.assertEqual(a.status, S.CHECKED_IN)

    def test_slot_can_be_rebooked_after_no_show(self):
        a = self.appt(self.u1, self.p1, -20)
        process_overdue_appointments()
        Appointment.objects.create(slot=a.slot, profile=self.p2, booked_by=self.u2)

    def test_mark_rejects_not_overdue(self):
        a = self.appt(self.u1, self.p1, 30)
        with self.assertRaises(BookingError):
            mark_no_show(a.pk)

    def test_mark_rejects_non_confirmed(self):
        a = self.appt(self.u1, self.p1, -20, status=S.CHECKED_IN)
        with self.assertRaises(BookingError):
            mark_no_show(a.pk)


class PenaltyTests(NoShowBase):
    def test_one_no_show_does_not_lock(self):
        self.appt(self.u1, self.p1, -20)
        process_overdue_appointments()
        self.u1.refresh_from_db()
        self.assertFalse(self.u1.is_booking_locked())

    def test_two_no_shows_lock_account_for_30_days(self):
        self.appt(self.u1, self.p1, -20)
        self.appt(self.u1, self.p1, -25)
        process_overdue_appointments()
        self.u1.refresh_from_db()
        self.assertTrue(self.u1.is_booking_locked())
        self.assertGreater(self.u1.booking_locked_until,
                           timezone.now() + timedelta(days=29))

    def test_old_no_show_outside_window_not_counted(self):
        old = self.appt(self.u1, self.p1, -60 * 24 * 40)  # 40 ngày trước
        Appointment.objects.filter(pk=old.pk).update(status=S.NO_SHOW)
        self.appt(self.u1, self.p1, -20)
        process_overdue_appointments()
        self.u1.refresh_from_db()
        self.assertFalse(self.u1.is_booking_locked())

    def test_lock_not_extended_when_already_locked(self):
        self.u1.lock_booking(days=5)
        self.appt(self.u1, self.p1, -20)
        self.appt(self.u1, self.p1, -25)
        process_overdue_appointments()
        self.u1.refresh_from_db()
        self.assertLess(self.u1.booking_locked_until, timezone.now() + timedelta(days=6))

    def test_other_user_not_affected(self):
        self.appt(self.u1, self.p1, -20)
        self.appt(self.u1, self.p1, -25)
        process_overdue_appointments()
        self.u2.refresh_from_db()
        self.assertFalse(self.u2.is_booking_locked())


class CommandAndBannerTests(NoShowBase):
    def test_command_runs(self):
        a = self.appt(self.u1, self.p1, -20)
        call_command("process_no_shows", stdout=StringIO())
        a.refresh_from_db()
        self.assertEqual(a.status, S.NO_SHOW)

    def test_locked_patient_sees_banner(self):
        self.u1.lock_booking()
        self.client.force_login(self.u1)
        r = self.client.get(reverse("appointments:mine"))
        self.assertContains(r, "tạm khóa")