"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("doctors/", include("clinics.urls")),
    path("appointments/", include("appointments.urls")),
    path("", lambda request: redirect("clinics:doctor_list")),
    path("reception/", include("appointments.reception_urls")),
    path("doctor/schedule/", include("clinics.doctor_urls")),
    path("doctor/", include("medical_records.doctor_urls")),
    path("records/", include("medical_records.urls")),
    path("analytics/", include("analytics.urls")),
]
