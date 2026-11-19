from django.urls import reverse

from accounts.models import User
from appointments.models import Appointment
from appointments.services import BookingError, check_in
from appointments.test_reception import ReceptionBase
from clinics.models import DoctorProfile

from .models import ConsultationNote
from .services import call_next_patient, save_consultation_note

S = Appointment.Status


class DoctorBase(ReceptionBase):
    def setUp(self):
        super().setUp()
        other_user = User.objects.create_user(
            username="doc2", password="x", role=User.Role.DOCTOR, first_name="Bình")
        self.other = DoctorProfile.objects.create(
            user=other_user, specialty=self.doctor.specialty)

    def checked_in(self, user, profile, minutes=3, doctor=None):
        appt = self.book(user, profile, self.slot_in(minutes, doctor=doctor))
        return check_in(appt.pk)


class DoctorServiceTests(DoctorBase):
    def test_call_next_follows_queue_order(self):
        a1 = self.checked_in(self.u1, self.p1, 3)
        self.checked_in(self.u2, self.p2, 5)
        called = call_next_patient(self.doctor)
        self.assertEqual(called.pk, a1.pk)
        self.assertEqual(called.status, S.IN_CONSULTATION)

    def test_cannot_call_next_while_consulting(self):
        self.checked_in(self.u1, self.p1, 3)
        self.checked_in(self.u2, self.p2, 5)
        call_next_patient(self.doctor)
        with self.assertRaises(BookingError):
            call_next_patient(self.doctor)

    def test_nobody_waiting(self):
        with self.assertRaises(BookingError):
            call_next_patient(self.doctor)

    def test_only_own_queue(self):
        self.checked_in(self.u1, self.p1, 3, doctor=self.other)
        with self.assertRaises(BookingError):
            call_next_patient(self.doctor)

    def test_finish_consultation_creates_note(self):
        a = self.checked_in(self.u1, self.p1)
        call_next_patient(self.doctor)
        save_consultation_note(doctor=self.doctor, appointment_id=a.pk,
                               diagnosis="Viêm họng", advice="Uống nhiều nước")
        a.refresh_from_db()
        self.assertEqual(a.status, S.COMPLETED)
        self.assertEqual(
            ConsultationNote.objects.get(appointment_id=a.pk).diagnosis, "Viêm họng")

    def test_requires_diagnosis(self):
        a = self.checked_in(self.u1, self.p1)
        call_next_patient(self.doctor)
        with self.assertRaises(BookingError):
            save_consultation_note(doctor=self.doctor, appointment_id=a.pk, diagnosis="  ")
        a.refresh_from_db()
        self.assertEqual(a.status, S.IN_CONSULTATION)

    def test_cannot_write_note_for_other_doctors_patient(self):
        a = self.checked_in(self.u1, self.p1, 3, doctor=self.other)
        call_next_patient(self.other)
        with self.assertRaises(BookingError):
            save_consultation_note(doctor=self.doctor, appointment_id=a.pk, diagnosis="x")

    def test_cannot_write_note_before_consultation(self):
        a = self.checked_in(self.u1, self.p1)  # mới check-in, chưa được gọi
        with self.assertRaises(BookingError):
            save_consultation_note(doctor=self.doctor, appointment_id=a.pk, diagnosis="x")

    def test_can_edit_note_after_completion(self):
        a = self.checked_in(self.u1, self.p1)
        call_next_patient(self.doctor)
        save_consultation_note(doctor=self.doctor, appointment_id=a.pk, diagnosis="Viêm họng")
        save_consultation_note(doctor=self.doctor, appointment_id=a.pk,
                               diagnosis="Viêm họng cấp")
        self.assertEqual(ConsultationNote.objects.filter(appointment_id=a.pk).count(), 1)
        self.assertEqual(
            ConsultationNote.objects.get(appointment_id=a.pk).diagnosis, "Viêm họng cấp")


class DoctorViewTests(DoctorBase):
    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("doctor:dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)

    def test_patient_forbidden(self):
        self.client.force_login(self.u1)
        self.assertEqual(self.client.get(reverse("doctor:dashboard")).status_code, 403)

    def test_dashboard_shows_only_own_patients(self):
        mine = self.checked_in(self.u1, self.p1, 3)
        theirs = self.checked_in(self.u2, self.p2, 3, doctor=self.other)
        self.client.force_login(self.doctor.user)
        r = self.client.get(reverse("doctor:dashboard"))
        self.assertContains(r, mine.code)
        self.assertContains(r, "Đau đầu")           # bác sĩ thấy triệu chứng
        self.assertNotContains(r, theirs.code)

    def test_other_doctors_consult_page_is_404(self):
        a = self.checked_in(self.u1, self.p1, 3, doctor=self.other)
        self.client.force_login(self.doctor.user)
        r = self.client.get(reverse("doctor:consult", args=[a.pk]))
        self.assertEqual(r.status_code, 404)

    def test_web_flow(self):
        a = self.checked_in(self.u1, self.p1)
        self.client.force_login(self.doctor.user)
        r = self.client.post(reverse("doctor:call_next"))
        self.assertRedirects(r, reverse("doctor:consult", args=[a.pk]))
        r = self.client.post(reverse("doctor:consult", args=[a.pk]),
                             {"diagnosis": "Cảm cúm", "advice": "Nghỉ ngơi"})
        self.assertRedirects(r, reverse("doctor:dashboard"))
        a.refresh_from_db()
        self.assertEqual(a.status, S.COMPLETED)

    def test_history_visible_to_owner_only(self):
        a = self.checked_in(self.u1, self.p1)
        call_next_patient(self.doctor)
        save_consultation_note(doctor=self.doctor, appointment_id=a.pk,
                               diagnosis="Viêm họng", advice="Uống nhiều nước")
        self.client.force_login(self.u1)
        self.assertContains(self.client.get(reverse("records:history")), "Viêm họng")
        self.client.force_login(self.u2)
        self.assertNotContains(self.client.get(reverse("records:history")), "Viêm họng")