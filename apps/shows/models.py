from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
	name = models.CharField(max_length=100, unique=True)
	slug = models.SlugField(max_length=120, unique=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]

	def __str__(self) -> str:
		return self.name


class Show(models.Model):
	artist = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shows")
	title = models.CharField(max_length=200)
	description = models.TextField()
	category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="shows")
	duration_minutes = models.PositiveSmallIntegerField()
	poster = models.ImageField(upload_to="posters/", blank=True, null=True)
	cover = models.ImageField(upload_to="covers/", blank=True, null=True, help_text="Immagine di copertina dello spettacolo")
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["title"]

	def __str__(self) -> str:
		return self.title


class Performance(models.Model):
	STATUS_PENDING_ARTIST_CONFIRMATION = "pending_artist_confirmation"
	STATUS_SCHEDULED = "scheduled"
	STATUS_CANCELLED = "cancelled"

	STATUS_CHOICES = [
		(STATUS_PENDING_ARTIST_CONFIRMATION, "Pending artist confirmation"),
		(STATUS_SCHEDULED, "Scheduled"),
		(STATUS_CANCELLED, "Cancelled"),
	]

	show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name="performances")
	auditorium = models.ForeignKey("theaters.Auditorium", on_delete=models.PROTECT, related_name="performances")
	starts_at = models.DateTimeField()
	status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING_ARTIST_CONFIRMATION)
	confirmed_by_artist = models.BooleanField(default=False)
	confirmed_by_artist_at = models.DateTimeField(null=True, blank=True)
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["starts_at"]

	def __str__(self) -> str:
		show_title = self.show.title if self.show_id else "Spettacolo"
		theater_name = self.auditorium.theater.name if self.auditorium_id else "Senza teatro"
		return f"{show_title} @ {theater_name}"

	def zone_price(self, auditorium_zone):
		if auditorium_zone is None:
			return Decimal("0.00")
		zone_price = self.zone_prices.filter(auditorium_zone=auditorium_zone).first()
		return zone_price.price if zone_price else Decimal("0.00")


class PerformancePrice(models.Model):
	performance = models.ForeignKey(Performance, on_delete=models.CASCADE, related_name="zone_prices")
	auditorium_zone = models.ForeignKey("theaters.AuditoriumZone", on_delete=models.CASCADE, related_name="performance_prices")
	price = models.DecimalField(max_digits=7, decimal_places=2, validators=[MinValueValidator(0)])

	class Meta:
		unique_together = ("performance", "auditorium_zone")
		ordering = ["auditorium_zone__cod_zone"]

	def __str__(self) -> str:
		return f"{self.performance} - {self.auditorium_zone.zone}"
