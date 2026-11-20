from django.test import TestCase
from django.urls import reverse

from .models import User


class SessionSeparationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="adm", password="x12345!")
        self.patient = User.objects.create_user(
            username="pat", password="x12345!", phone="0933333333")

    def admin_login(self):
        self.client.post("/admin/login/?next=/admin/",
                         {"username": "adm", "password": "x12345!"})

    def patient_login(self):
        self.client.post(reverse("accounts:login"),
                         {"username": "0933333333", "password": "x12345!"})

    def test_admin_login_does_not_log_into_patient_site(self):
        self.admin_login()
        self.assertIn("admin_sessionid", self.client.cookies)
        self.assertNotIn("sessionid", self.client.cookies)
        r = self.client.get(reverse("accounts:profiles"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.wsgi_request.user, self.admin)

    def test_patient_login_does_not_log_into_admin(self):
        self.patient_login()
        self.assertIn("sessionid", self.client.cookies)
        self.assertNotIn("admin_sessionid", self.client.cookies)
        r = self.client.get(reverse("accounts:profiles"))
        self.assertEqual(r.wsgi_request.user, self.patient)
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/admin/login/", r.url)

    def test_both_logged_in_as_different_users(self):
        self.admin_login()
        self.patient_login()
        r = self.client.get("/admin/")
        self.assertEqual(r.wsgi_request.user, self.admin)
        r = self.client.get(reverse("accounts:profiles"))
        self.assertEqual(r.wsgi_request.user, self.patient)

    def test_admin_logout_keeps_patient_session(self):
        self.admin_login()
        self.patient_login()
        self.client.post("/admin/logout/")
        r = self.client.get(reverse("accounts:profiles"))
        self.assertEqual(r.wsgi_request.user, self.patient)

class LoginRedirectTests(TestCase):
    def go_home(self, role, **extra):
        user = User.objects.create_user(
            username=f"u-{role.lower()}", password="x12345!", role=role, **extra)
        self.client.force_login(user)
        return self.client.get(reverse("accounts:home"))

    def test_doctor_goes_to_doctor_dashboard(self):
        r = self.go_home("DOCTOR")
        self.assertRedirects(r, reverse("doctor:dashboard"), fetch_redirect_response=False)

    def test_receptionist_goes_to_reception(self):
        r = self.go_home("RECEPTIONIST")
        self.assertRedirects(r, reverse("reception:dashboard"), fetch_redirect_response=False)

    def test_patient_goes_to_profiles(self):
        r = self.go_home("PATIENT")
        self.assertRedirects(r, reverse("accounts:profiles"), fetch_redirect_response=False)

    def test_superuser_goes_to_analytics(self):
        admin = User.objects.create_superuser(username="root", password="x12345!")
        self.client.force_login(admin)
        r = self.client.get(reverse("accounts:home"))
        self.assertRedirects(r, reverse("analytics:dashboard"), fetch_redirect_response=False)

    def test_admin_role_goes_to_analytics(self):
        r = self.go_home("ADMIN")
        self.assertRedirects(r, reverse("analytics:dashboard"), fetch_redirect_response=False)
    
    def test_login_form_sends_to_home(self):
        User.objects.create_user(username="doc9", password="x12345!", role="DOCTOR")
        r = self.client.post(reverse("accounts:login"),
                             {"username": "doc9", "password": "x12345!"})
        self.assertRedirects(r, reverse("accounts:home"), fetch_redirect_response=False)