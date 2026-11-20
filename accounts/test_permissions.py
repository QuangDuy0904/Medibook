from django.test import TestCase
from django.urls import reverse

from clinics.models import DoctorProfile, Specialty

from .models import User

ROLES = ["PATIENT", "DOCTOR", "RECEPTIONIST", "ADMIN"]
ANALYTICS_PAGES = [("analytics:dashboard", [])]

# (tên url, tham số), id 1 không tồn tại: vai trò đúng thì 404, sai vai trò thì 403
PATIENT_PAGES = [
    ("accounts:profiles", []), ("accounts:profile_add", []),
    ("appointments:mine", []), ("appointments:detail", [1]),
    ("appointments:qr", [1]), ("appointments:book", [1]),
    ("records:history", []),
]
DOCTOR_PAGES = [
    ("doctor:dashboard", []), ("doctor:consult", [1]),
    ("doctor_schedule:home", []),
]
RECEPTION_PAGES = [
    ("reception:dashboard", []), ("reception:walkin_pick", []),
    ("reception:checkin_confirm", [1]),
]
AREAS = [
    (PATIENT_PAGES, {"PATIENT"}),
    (DOCTOR_PAGES, {"DOCTOR"}),
    (RECEPTION_PAGES, {"RECEPTIONIST", "ADMIN"}),
    (ANALYTICS_PAGES, {"ADMIN"}),
]

# Các thao tác chỉ nhận POST: (tên url, tham số, vai trò được phép)
POST_ACTIONS = [
    ("appointments:cancel", [1], {"PATIENT"}),
    ("reception:checkin_lookup", [], {"RECEPTIONIST", "ADMIN"}),
    ("reception:cancel", [1], {"RECEPTIONIST", "ADMIN"}),
    ("doctor:call_next", [], {"DOCTOR"}),
    ("doctor_schedule:add", [], {"DOCTOR"}),
    ("doctor_schedule:off_add", [], {"DOCTOR"}),

]




class PermissionBase(TestCase):
    def setUp(self):
        self.users = {
            role: User.objects.create_user(
                username=role.lower(), password="x12345!", role=role)
            for role in ROLES}
        DoctorProfile.objects.create(
            user=self.users["DOCTOR"], specialty=Specialty.objects.create(name="Nội"))


class RoleMatrixTests(PermissionBase):
    def test_pages_match_role_matrix(self):
        for pages, allowed in AREAS:
            for role, user in self.users.items():
                self.client.force_login(user)
                for name, args in pages:
                    with self.subTest(role=role, page=name):
                        r = self.client.get(reverse(name, args=args))
                        if role in allowed:
                            self.assertIn(r.status_code, (200, 404))
                        else:
                            self.assertEqual(r.status_code, 403)

    def test_post_actions_match_role_matrix(self):
        for name, args, allowed in POST_ACTIONS:
            for role, user in self.users.items():
                self.client.force_login(user)
                with self.subTest(role=role, action=name):
                    r = self.client.post(reverse(name, args=args))
                    self.assertEqual(r.status_code, 302 if role in allowed else 403)

    def test_anonymous_redirected_to_login(self):
        for pages, _allowed in AREAS:
            for name, args in pages:
                with self.subTest(page=name):
                    r = self.client.get(reverse(name, args=args))
                    self.assertEqual(r.status_code, 302)
                    self.assertIn("/accounts/login/", r.url)

    def test_superuser_can_open_every_area(self):
        root = User.objects.create_superuser(username="root", password="x12345!")
        self.client.force_login(root)
        for name in ("reception:dashboard", "doctor:dashboard",
                     "accounts:profiles", "records:history"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_forbidden_page_is_friendly(self):
        self.client.force_login(self.users["PATIENT"])
        r = self.client.get(reverse("reception:dashboard"))
        self.assertContains(r, "không có quyền", status_code=403)


class RegistrationRoleTests(PermissionBase):
    def test_register_always_creates_patient(self):
        self.client.post(reverse("accounts:register"), {
            "full_name": "Nguyễn Văn Kiểm", "phone": "0912345678",
            "password1": "Xk9#mPq2vL!z", "password2": "Xk9#mPq2vL!z",
            "role": "ADMIN",  # cố tình gửi kèm để leo quyền
        })
        user = User.objects.get(phone="0912345678")
        self.assertEqual(user.role, "PATIENT")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)