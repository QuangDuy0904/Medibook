from django.urls import path

from . import doctor_views as v

app_name = "doctor_schedule"

urlpatterns = [
    path("", v.home, name="home"),
    path("add/", v.add, name="add"),
    path("<int:pk>/delete/", v.delete, name="delete"),
    path("off/add/", v.off_add, name="off_add"),
    path("off/<int:pk>/delete/", v.off_delete, name="off_delete"),
]