from django.contrib import admin

from .models import ConsultationNote


@admin.register(ConsultationNote)
class ConsultationNoteAdmin(admin.ModelAdmin):
    list_display = ("appointment", "created_at", "updated_at")
    search_fields = ("appointment__code", "appointment__profile__full_name")