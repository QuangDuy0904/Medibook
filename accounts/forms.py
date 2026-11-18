from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .models import PatientProfile, User, phone_validator


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Số điện thoại hoặc email")
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput)


class RegisterForm(forms.Form):
    full_name = forms.CharField(label="Họ tên", max_length=150)
    phone = forms.CharField(label="Số điện thoại", max_length=15, required=False,
                            validators=[phone_validator])
    email = forms.EmailField(label="Email", required=False)
    password1 = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Nhập lại mật khẩu", widget=forms.PasswordInput)

    def clean_phone(self):
        phone = self.cleaned_data["phone"].replace(" ", "")
        if phone and User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("Số điện thoại đã được đăng ký.")
        return phone or None

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email đã được đăng ký.")
        return email or None

    def clean(self):
        data = super().clean()
        if not data.get("phone") and not data.get("email"):
            raise forms.ValidationError("Cần nhập ít nhất số điện thoại hoặc email.")
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Mật khẩu nhập lại không khớp.")
            else:
                validate_password(p1)
        return data

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(
            username=d["phone"] or d["email"],
            email=d["email"], phone=d["phone"],
            password=d["password1"], first_name=d["full_name"],
            role=User.Role.PATIENT,
        )
        # Tự tạo hồ sơ "Bản thân" cho tài khoản mới
        PatientProfile.objects.create(
            owner=user, relationship=PatientProfile.Relationship.SELF,
            full_name=d["full_name"],
        )
        return user