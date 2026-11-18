from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class IdentifierBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        User = get_user_model()
        ident = username.strip()
        user = User.objects.filter(
            Q(phone=ident) | Q(email__iexact=ident) | Q(username=ident)
        ).first()
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None