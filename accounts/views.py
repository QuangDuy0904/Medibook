from django.contrib import messages
from django.contrib.auth import login
from .permissions import patient_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PatientProfileForm, RegisterForm
from .models import PatientProfile


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profiles")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.IdentifierBackend")
        messages.success(request, "Đăng ký thành công!")
        return redirect("accounts:profiles")
    return render(request, "accounts/register.html", {"form": form})


ROLE_HOME = {
    "DOCTOR": "doctor:dashboard",
    "RECEPTIONIST": "reception:dashboard",
    "ADMIN": "analytics:dashboard",
}


@login_required
def home(request):
    """Sau đăng nhập, đưa mỗi vai trò về đúng khu vực làm việc của họ."""
    user = request.user
    if user.is_superuser:
        return redirect("analytics:dashboard")
    return redirect(ROLE_HOME.get(user.role, "accounts:profiles"))

@patient_required
def profiles(request):
    return render(request, "accounts/profiles.html",
                  {"profiles": request.user.profiles.all()})


@patient_required
def profile_add(request):
    form = PatientProfileForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.owner = request.user
        obj.save()
        messages.success(request, "Đã thêm hồ sơ.")
        return redirect("accounts:profiles")
    return render(request, "accounts/profile_form.html",
                  {"form": form, "title": "Thêm hồ sơ người thân"})

@patient_required
def profile_edit(request, pk):
    # Chỉ lấy hồ sơ của chính mình, người khác gõ URL sẽ ra 404
    obj = get_object_or_404(PatientProfile, pk=pk, owner=request.user)
    is_self = obj.relationship == PatientProfile.Relationship.SELF
    form = PatientProfileForm(request.POST or None, instance=obj, is_self=is_self)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật hồ sơ.")
        return redirect("accounts:profiles")
    return render(request, "accounts/profile_form.html",
                  {"form": form, "title": f"Sửa hồ sơ: {obj.full_name}"})


@patient_required
def profile_delete(request, pk):
    obj = get_object_or_404(PatientProfile, pk=pk, owner=request.user)
    if obj.relationship == PatientProfile.Relationship.SELF:
        messages.error(request, "Không thể xóa hồ sơ bản thân.")
        return redirect("accounts:profiles")
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Đã xóa hồ sơ.")
        return redirect("accounts:profiles")
    return render(request, "accounts/profile_confirm_delete.html", {"obj": obj})