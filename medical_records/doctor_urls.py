from django.urls import path

from . import views

app_name = "doctor"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("call-next/", views.call_next, name="call_next"),
    path("<int:pk>/", views.consult, name="consult"),
]