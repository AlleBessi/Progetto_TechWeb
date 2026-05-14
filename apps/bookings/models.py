from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Booking(models.Model):
	STATUS_CONFIRMED = "confirmed"
	STATUS_CANCELLED = "cancelled"

	STATUS_CHOICES = [
		(STATUS_CONFIRMED, "Confirmed"),
		(STATUS_CANCELLED, "Cancelled"),
	]

	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
	performance = models.ForeignKey("shows.Performance", on_delete=models.CASCADE, related_name="bookings")
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)
	total_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"{self.user.get_username()} - {self.performance}"


class BookingSeat(models.Model):
	booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="seats")
	performance = models.ForeignKey("shows.Performance", on_delete=models.CASCADE, related_name="seat_reservations")
	seat = models.ForeignKey("theaters.Seat", on_delete=models.PROTECT)
	price_at_purchase = models.DecimalField(max_digits=7, decimal_places=2)

	class Meta:
		unique_together = ("performance", "seat")

	def clean(self):
		if self.booking and self.performance and self.booking.performance_id != self.performance_id:
			raise ValidationError("Booking and performance must match.")

	def save(self, *args, **kwargs):
		self.clean()
		super().save(*args, **kwargs)

	def __str__(self) -> str:
		return f"{self.performance} {self.seat}"
