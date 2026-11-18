from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

app_name = "accounts"

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(
        template_name="accounts/login.html",
        authentication_form=LoginForm,
        redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profiles/", views.profiles, name="profiles"),
    path("profiles/add/", views.profile_add, name="profile_add"),
    path("profiles/<int:pk>/edit/", views.profile_edit, name="profile_edit"),
    path("profiles/<int:pk>/delete/", views.profile_delete, name="profile_delete"),
]