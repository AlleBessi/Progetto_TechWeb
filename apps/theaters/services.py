from apps.bookings.models import Booking
from apps.shows.models import Performance, Show


def get_performance_management_queryset(theater):
	return (
		Performance.objects.filter(auditorium__theater=theater)
		.select_related("show", "auditorium")
		.order_by("starts_at")
	)


def get_booking_management_queryset(theater):
	return (
		Booking.objects.filter(performance__auditorium__theater=theater)
		.select_related("user", "performance__show", "performance__auditorium")
		.prefetch_related("seats__seat")
		.order_by("-created_at")
	)
