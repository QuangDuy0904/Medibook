from django.db import models


class ConsultationNote(models.Model):
    """Kết quả sơ bộ sau khám (FR-15). Mỗi lịch hẹn có tối đa một ghi chú."""
    appointment = models.OneToOneField(
        "appointments.Appointment", on_delete=models.CASCADE, related_name="note")
    diagnosis = models.TextField("chẩn đoán sơ bộ")
    advice = models.TextField("lời dặn", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ghi chú sau khám"
        verbose_name_plural = "ghi chú sau khám"

    def __str__(self):
        return f"Ghi chú {self.appointment.code}"