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

class WalkinForm(forms.Form):
    full_name = forms.CharField(label="Họ tên bệnh nhân", max_length=150)
    phone = forms.CharField(label="Số điện thoại", max_length=15)
    symptoms = forms.CharField(
        label="Triệu chứng, lý do khám", required=False, max_length=1000,
        widget=forms.Textarea(attrs={"rows": 2}))
    check_in_now = forms.BooleanField(
        label="Check-in ngay (bệnh nhân đang có mặt, giờ hẹn trong 30 phút tới)",
        required=False)