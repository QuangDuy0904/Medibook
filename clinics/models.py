from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Specialty(models.Model):
    name = models.CharField("tên chuyên khoa", max_length=100, unique=True)
    description = models.TextField("mô tả", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "chuyên khoa"
        verbose_name_plural = "chuyên khoa"

    def __str__(self):
        return self.name


class DoctorProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="doctor_profile", limit_choices_to={"role": "DOCTOR"},
    )
    specialty = models.ForeignKey(
        Specialty, on_delete=models.PROTECT, related_name="doctors"
    )
    title = models.CharField("học hàm, học vị", max_length=100, blank=True,
                             help_text="Ví dụ: TS.BS, ThS.BS")
    years_experience = models.PositiveSmallIntegerField("số năm kinh nghiệm", default=0)
    bio = models.TextField("mô tả dịch vụ", blank=True)
    consultation_fee = models.DecimalField(
        "phí khám tham khảo (VNĐ)", max_digits=10, decimal_places=0, default=0,
        help_text="Nhập số, không gõ dấu chấm. Ví dụ: 200000",
    )
    slot_minutes = models.PositiveSmallIntegerField(
        "số phút mỗi khung giờ", default=30,
        choices=[(15, "15 phút"), (30, "30 phút")],
    )
    is_active = models.BooleanField("đang nhận khám", default=True)

    class Meta:
        verbose_name = "hồ sơ bác sĩ"
        verbose_name_plural = "hồ sơ bác sĩ"

    def __str__(self):
        return f"{self.title} {self.user.get_full_name() or self.user.username}".strip()

    @property
    def fee_display(self):
        """200000 -> '200.000 VNĐ' (dùng cho cả template và admin)."""
        return f"{int(self.consultation_fee):,}".replace(",", ".") + " VNĐ"

class WorkSchedule(models.Model):
    class Shift(models.TextChoices):
        MORNING = "MORNING", "Sáng"
        AFTERNOON = "AFTERNOON", "Chiều"

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE,
                               related_name="schedules")
    date = models.DateField("ngày")
    shift = models.CharField("ca", max_length=10, choices=Shift.choices)
    start_time = models.TimeField("giờ bắt đầu")
    end_time = models.TimeField("giờ kết thúc")
    slot_minutes = models.PositiveSmallIntegerField(
        "số phút mỗi khung", choices=[(15, "15 phút"), (30, "30 phút")], default=30,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["doctor", "date", "shift"],
                                    name="unique_schedule_per_shift"),
        ]
        ordering = ["date", "start_time"]
        verbose_name = "lịch làm việc"
        verbose_name_plural = "lịch làm việc"

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Giờ kết thúc phải sau giờ bắt đầu.")

    def __str__(self):
        return f"{self.doctor} - {self.date} ({self.get_shift_display()})"


class DayOff(models.Model):
    """Nghỉ phép hoặc báo bận đột xuất. Để trống 'ca' nghĩa là nghỉ cả ngày."""
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE,
                               related_name="days_off")
    date = models.DateField("ngày nghỉ")
    shift = models.CharField("ca", max_length=10, choices=WorkSchedule.Shift.choices,
                             blank=True)
    reason = models.CharField("lý do", max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["doctor", "date", "shift"],
                                    name="unique_dayoff_per_shift"),
        ]
        ordering = ["-date"]
        verbose_name = "ngày nghỉ"
        verbose_name_plural = "ngày nghỉ"

    def __str__(self):
        return f"{self.doctor} nghỉ {self.date} ({self.get_shift_display() or 'cả ngày'})"


class TimeSlot(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE,
                               related_name="slots")
    schedule = models.ForeignKey(WorkSchedule, on_delete=models.CASCADE,
                                 related_name="slots")
    start_at = models.DateTimeField("bắt đầu")
    end_at = models.DateTimeField("kết thúc")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["doctor", "start_at"],
                                    name="unique_slot_per_doctor_time"),
        ]
        ordering = ["start_at"]
        verbose_name = "khung giờ"
        verbose_name_plural = "khung giờ"

    def __str__(self):
        return f"{self.doctor} {self.start_at:%d/%m/%Y %H:%M}"