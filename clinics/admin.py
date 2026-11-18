from django.contrib import admin, messages

from .models import DayOff, DoctorProfile, Specialty, TimeSlot, WorkSchedule
from .services import generate_slots


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ("__str__", "specialty", "years_experience",
                    "consultation_fee", "slot_minutes", "is_active")
    list_filter = ("specialty", "is_active")
    search_fields = ("user__first_name", "user__last_name", "user__username")


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ("doctor", "date", "shift", "start_time", "end_time", "slot_minutes")
    list_filter = ("shift", "doctor")
    date_hierarchy = "date"
    actions = ["regenerate"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        n = generate_slots(obj)  # lưu xong là tự sinh khung giờ
        messages.info(request, f"Đã sinh {n} khung giờ.")

    @admin.action(description="Sinh lại khung giờ cho các ca đã chọn")
    def regenerate(self, request, queryset):
        total = sum(generate_slots(s) for s in queryset)
        self.message_user(request, f"Đã xử lý {total} khung giờ.")


@admin.register(DayOff)
class DayOffAdmin(admin.ModelAdmin):
    list_display = ("doctor", "date", "shift", "reason")
    list_filter = ("doctor",)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("doctor", "start_at", "end_at")
    list_filter = ("doctor",)
    date_hierarchy = "start_at"