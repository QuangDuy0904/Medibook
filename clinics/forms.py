from django import forms

from .models import WorkSchedule


class ScheduleForm(forms.Form):
    date = forms.DateField(
        label="Ngày", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    shift = forms.ChoiceField(
        label="Ca", choices=WorkSchedule.Shift.choices,
        widget=forms.Select(attrs={"class": "form-select"}))
    start_time = forms.TimeField(
        label="Giờ bắt đầu", widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}))
    end_time = forms.TimeField(
        label="Giờ kết thúc", widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}))
    slot_minutes = forms.TypedChoiceField(
        label="Độ dài mỗi khung giờ", coerce=int, initial=30,
        choices=[(15, "15 phút"), (30, "30 phút")],
        widget=forms.Select(attrs={"class": "form-select"}))


class DayOffForm(forms.Form):
    date = forms.DateField(
        label="Ngày nghỉ", widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    shift = forms.ChoiceField(
        label="Nghỉ", required=False,
        choices=[("", "Cả ngày")] + list(WorkSchedule.Shift.choices),
        widget=forms.Select(attrs={"class": "form-select"}))
    reason = forms.CharField(
        label="Lý do", required=False, max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control"}))