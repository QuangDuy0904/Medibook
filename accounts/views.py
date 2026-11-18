from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:home")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.IdentifierBackend")
        messages.success(request, "Đăng ký thành công!")
        return redirect("accounts:home")
    return render(request, "accounts/register.html", {"form": form})


@login_required
def home(request):
    # Trang tạm, sẽ thay bằng trang hồ sơ ở bước 1.4
    return render(request, "accounts/home.html")