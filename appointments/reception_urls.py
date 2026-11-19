from django.urls import path

from . import reception_views as v

app_name = "reception"

urlpatterns = [
    path("", v.dashboard, name="dashboard"),
    path("checkin/", v.checkin_lookup, name="checkin_lookup"),
    path("checkin/<int:pk>/", v.checkin_confirm, name="checkin_confirm"),
    path("walkin/", v.walkin_pick, name="walkin_pick"),
    path("walkin/<int:slot_id>/", v.walkin_book, name="walkin_book"),
    path("<int:pk>/cancel/", v.staff_cancel, name="cancel"),
]