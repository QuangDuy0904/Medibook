from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command

from clinics.schedule_services import add_day_off

from .models import Appointment
from .services import send_due_reminders
from .test_reception import ReceptionBase

S = Appointment.Status


class ReminderTests(ReceptionBase):
    def setUp(self):
        super().setUp()
        self.u1.email = "u1@example.com"
        self.u1.save()
        self.u2.email = None          # u2 không có email, dù dữ liệu mẫu gán gì
        self.u2.save()

    def appt(self, user, profile, minutes, status=S.CONFIRMED):
        return Appointment.objects.create(
            slot=self.slot_in(minutes), profile=profile, booked_by=user, status=status)

    def test_sends_reminder_within_window(self):
        a = self.appt(self.u1, self.p1, 60 * 5)
        self.assertEqual(send_due_reminders(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["u1@example.com"])
        self.assertIn(a.code, mail.outbox[0].body)
        a.refresh_from_db()
        self.assertIsNotNone(a.reminder_sent_at)

    def test_not_sent_twice(self):
        self.appt(self.u1, self.p1, 60 * 5)
        send_due_reminders()
        self.assertEqual(send_due_reminders(), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_too_far_in_future(self):
        self.appt(self.u1, self.p1, 60 * 30)
        self.assertEqual(send_due_reminders(), 0)

    def test_past_appointment_not_reminded(self):
        self.appt(self.u1, self.p1, -10)
        self.assertEqual(send_due_reminders(), 0)

    def test_user_without_email_skipped(self):
        a = self.appt(self.u2, self.p2, 60 * 5)  # u2 không có email
        self.assertEqual(send_due_reminders(), 0)
        self.assertEqual(len(mail.outbox), 0)
        a.refresh_from_db()
        self.assertIsNone(a.reminder_sent_at)

    def test_only_confirmed_appointments(self):
        self.appt(self.u1, self.p1, 60 * 5, status=S.CANCELLED)
        self.assertEqual(send_due_reminders(), 0)

    def test_send_failure_is_not_marked_as_sent(self):
        a = self.appt(self.u1, self.p1, 60 * 5)
        with mock.patch("appointments.notifications.send_mail",
                        side_effect=Exception("smtp down")):
            self.assertEqual(send_due_reminders(), 0)
        a.refresh_from_db()
        self.assertIsNone(a.reminder_sent_at)
        self.assertEqual(send_due_reminders(), 1)  # lần quét sau gửi lại được

    def test_command_sends_reminders(self):
        self.appt(self.u1, self.p1, 60 * 5)
        call_command("process_no_shows", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    def test_day_off_notifies_cancelled_patient(self):
        slot = self.make_slot()
        self.book(self.u1, self.p1, slot)
        with self.captureOnCommitCallbacks(execute=True):
            add_day_off(doctor=self.doctor, date=slot.schedule.date, reason="Việc gia đình")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("đã bị hủy", mail.outbox[0].subject)
        self.assertIn("Việc gia đình", mail.outbox[0].body)

    def test_user_with_blank_email_skipped(self):
        self.u2.email = ""
        self.u2.save()
        self.appt(self.u2, self.p2, 60 * 5)
        self.assertEqual(send_due_reminders(), 0)
        self.assertEqual(len(mail.outbox), 0)