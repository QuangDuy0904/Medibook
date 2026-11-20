from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Chỉ cho vào nếu đã đăng nhập và có vai trò phù hợp (superuser luôn được)."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not (user.is_superuser or user.role in roles):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


reception_required = role_required("RECEPTIONIST", "ADMIN")
doctor_required = role_required("DOCTOR")
patient_required = role_required("PATIENT")
admin_required = role_required("ADMIN")