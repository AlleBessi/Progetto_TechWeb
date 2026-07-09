from django.urls import path
 
from . import views
 
app_name = "bookings"
 
urlpatterns = [
    path("", views.BookingList.as_view(), name="booking_list"),
    path("new/<int:performance_id>/", views.BookingCreate.as_view(), name="booking_create"),
    path("<int:booking_id>/edit/", views.BookingUpdate.as_view(), name="booking_update"),
    path("<int:booking_id>/cancel/", views.BookingCancel.as_view(), name="booking_cancel"),
]
