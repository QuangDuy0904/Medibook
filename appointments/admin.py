from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("code", "profile", "doctor", "start", "status", "booked_by")
    list_filter = ("status", "slot__doctor")
    search_fields = ("code", "profile__full_name", "booked_by__phone")
    readonly_fields = ("code", "created_at")

    @admin.display(description="Bác sĩ")
    def doctor(self, obj):
        return obj.slot.doctor

    @admin.display(description="Giờ khám", ordering="slot__start_at")
    def start(self, obj):
        return obj.slot.start_at