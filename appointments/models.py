import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import PatientProfile
from datetime import timedelta
from clinics.models import TimeSlot

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bỏ O/0, I/1 cho dễ đọc


def generate_code():
    """Mã hẹn duy nhất, ví dụ APT-20261118-K7M2QX (FR-10)."""
    day = timezone.localdate().strftime("%Y%m%d")
    for _ in range(10):
        rand = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        code = f"APT-{day}-{rand}"
        if not Appointment.objects.filter(code=code).exists():
            return code
    raise RuntimeError("Không sinh được mã hẹn duy nhất.")


class Appointment(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Đã xác nhận"
        CHECKED_IN = "CHECKED_IN", "Đã check-in"
        IN_CONSULTATION = "IN_CONSULTATION", "Đang khám"
        COMPLETED = "COMPLETED", "Hoàn thành"
        CANCELLED = "CANCELLED", "Đã hủy"
        NO_SHOW = "NO_SHOW", "Vắng mặt"

    # Lịch còn chiếm slot. CANCELLED và NO_SHOW thì nhả slot.
    ACTIVE_STATUSES = ["CONFIRMED", "CHECKED_IN", "IN_CONSULTATION", "COMPLETED"]

    # FR-12: chuyển trạng thái hợp lệ
    TRANSITIONS = {
        "CONFIRMED": {"CHECKED_IN", "CANCELLED", "NO_SHOW"},
        "CHECKED_IN": {"IN_CONSULTATION"},
        "IN_CONSULTATION": {"COMPLETED"},
        "COMPLETED": set(),
        "CANCELLED": set(),
        "NO_SHOW": set(),
    }

    def can_change_online(self):
        """Còn được hủy/đổi lịch trực tuyến không (BR-03)."""
        hours = settings.BOOKING_RULES["CANCEL_MIN_HOURS"]
        return (self.status == self.Status.CONFIRMED
                and self.slot.start_at - timezone.now() >= timedelta(hours=hours))

    code = models.CharField("mã hẹn", max_length=20, unique=True, editable=False)
    slot = models.ForeignKey(TimeSlot, on_delete=models.PROTECT,
                             related_name="appointments")
    profile = models.ForeignKey(PatientProfile, on_delete=models.PROTECT,
                                related_name="appointments")
    booked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                  related_name="appointments")
    symptoms = models.TextField("triệu chứng, lý do khám", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.CONFIRMED)
    queue_number = models.PositiveIntegerField("số thứ tự", null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # BR-01: mỗi slot chỉ có tối đa 1 lịch còn hiệu lực
            models.UniqueConstraint(
                fields=["slot"],
                condition=~Q(status__in=["CANCELLED", "NO_SHOW"]),
                name="unique_active_appointment_per_slot",
            ),
        ]
        ordering = ["-slot__start_at"]
        verbose_name = "lịch hẹn"
        verbose_name_plural = "lịch hẹn"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_code()
        super().save(*args, **kwargs)

    def can_transition_to(self, new_status):
        return new_status in self.TRANSITIONS.get(self.status, set())

    def __str__(self):
        return f"{self.code} - {self.profile.full_name}"