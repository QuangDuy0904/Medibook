from django.urls import path

from . import views

app_name = "appointments"

urlpatterns = [
    path("mine/", views.mine, name="mine"),
    path("book/<int:slot_id>/", views.book, name="book"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/cancel/", views.cancel, name="cancel"),
    path("<int:pk>/reschedule/", views.reschedule, name="reschedule"),
    path("<int:pk>/qr.png", views.qr_png, name="qr"),
]