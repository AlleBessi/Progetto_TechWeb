from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("", views.booking_list, name="list"),
    path("performance/<int:performance_id>/", views.performance_booking, name="performance_booking"),
    path("<int:booking_id>/edit/", views.booking_update, name="update"),
    path("<int:booking_id>/cancel/", views.booking_cancel, name="cancel"),
]
