from django import forms

from accounts.models import PatientProfile


class BookingForm(forms.Form):
    profile = forms.ModelChoiceField(
        queryset=PatientProfile.objects.none(), label="Người khám", empty_label=None,
        widget=forms.Select(attrs={"class": "form-select"}))
    symptoms = forms.CharField(
        label="Triệu chứng, lý do khám", max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile"].queryset = user.profiles.all()