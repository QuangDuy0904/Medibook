from django import forms


class NoteForm(forms.Form):
    diagnosis = forms.CharField(
        label="Chẩn đoán sơ bộ", max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))
    advice = forms.CharField(
        label="Lời dặn sau khám", required=False, max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))