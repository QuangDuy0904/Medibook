from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r"^(0|\+84)\d{9}$",
    message="Số điện thoại không hợp lệ (ví dụ 0912345678).",
)


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "PATIENT", "Bệnh nhân"
        DOCTOR = "DOCTOR", "Bác sĩ"
        RECEPTIONIST = "RECEPTIONIST", "Tiếp tân / Điều dưỡng"
        ADMIN = "ADMIN", "Quản trị viên"

    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.PATIENT
    )
    # null=True để nhiều tài khoản có thể không có email/SĐT mà vẫn unique
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(
        "số điện thoại", max_length=15, unique=True,
        null=True, blank=True, validators=[phone_validator],
    )
    # BR-05: bị khóa đặt lịch online đến thời điểm này
    booking_locked_until = models.DateTimeField(null=True, blank=True)
    first_name = models.CharField("tên", max_length=150, blank=True)
    last_name = models.CharField("họ và tên đệm", max_length=150, blank=True)

    def get_full_name(self):
        parts = (self.last_name.strip(), self.first_name.strip())
        return " ".join(p for p in parts if p)

    def is_booking_locked(self):
        return bool(
            self.booking_locked_until and self.booking_locked_until > timezone.now()
        )

    def lock_booking(self, days=None):
        days = days or settings.BOOKING_RULES["BOOKING_LOCK_DAYS"]
        self.booking_locked_until = timezone.now() + timedelta(days=days)
        self.save(update_fields=["booking_locked_until"])

    def __str__(self):
        return self.get_full_name() or self.phone or self.email or self.username

    def save(self, *args, **kwargs):
        self.email = self.email.strip() if self.email else None
        self.phone = self.phone.strip() if self.phone else None
        super().save(*args, **kwargs)

class PatientProfile(models.Model):
    """Hồ sơ khám: 1 hồ sơ SELF của chính chủ + nhiều hồ sơ người thân (FR-02, FR-03)."""

    class Gender(models.TextChoices):
        MALE = "M", "Nam"
        FEMALE = "F", "Nữ"
        OTHER = "O", "Khác"

    class Relationship(models.TextChoices):
        SELF = "SELF", "Bản thân"
        CHILD = "CHILD", "Con"
        PARENT = "PARENT", "Cha/Mẹ"
        SPOUSE = "SPOUSE", "Vợ/Chồng"
        OTHER = "OTHER", "Khác"

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="profiles"
    )
    relationship = models.CharField(
        max_length=10, choices=Relationship.choices, default=Relationship.SELF
    )
    full_name = models.CharField("họ tên", max_length=150)
    date_of_birth = models.DateField("ngày sinh", null=True, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    address = models.CharField("địa chỉ", max_length=255, blank=True)
    citizen_id = models.CharField(
        "CMND/CCCD", max_length=12, blank=True,
        validators=[RegexValidator(r"^\d{9}(\d{3})?$", "CMND 9 số hoặc CCCD 12 số.")],
    )
    insurance_number = models.CharField("số thẻ BHYT", max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Mỗi tài khoản chỉ có tối đa 1 hồ sơ "Bản thân"
            models.UniqueConstraint(
                fields=["owner"],
                condition=Q(relationship="SELF"),
                name="unique_self_profile_per_user",
            ),
        ]
        ordering = ["relationship", "full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.get_relationship_display()})"