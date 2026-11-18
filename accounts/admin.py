from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PatientProfile, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "phone", "email", "role", "booking_locked_until", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "phone", "email")
    fieldsets = UserAdmin.fieldsets + (
        ("Thông tin bổ sung", {"fields": ("role", "phone", "booking_locked_until")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Thông tin bổ sung", {"fields": ("first_name", "last_name", "role", "phone", "email")}),
    )


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "relationship", "owner", "date_of_birth")
    list_filter = ("relationship", "gender")
    search_fields = ("full_name", "citizen_id", "owner__phone")