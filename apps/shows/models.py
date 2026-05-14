from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.theaters.models import ZONE_CHOICES, ZONE_PLATEA


def validate_at_least_one_artist(artists):
	"""Validate that at least one artist is selected."""
	if not artists.exists():
		raise ValidationError("Uno spettacolo deve avere almeno un artista.")


class Category(models.Model):
	name = models.CharField(max_length=100, unique=True)
	slug = models.SlugField(max_length=120, unique=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["name"]

	def __str__(self) -> str:
		return self.name


class Show(models.Model):
	STATUS_DRAFT = "draft"
	STATUS_ARTIST_CONFIRMED = "artist_confirmed"
	STATUS_APPROVED = "approved"
	STATUS_REJECTED = "rejected"

	STATUS_CHOICES = [
		(STATUS_DRAFT, "Draft"),
		(STATUS_ARTIST_CONFIRMED, "Artist confirmed"),
		(STATUS_APPROVED, "Approved"),
		(STATUS_REJECTED, "Rejected"),
	]

	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shows")
	title = models.CharField(max_length=200)
	description = models.TextField()
	category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="shows")
	duration_minutes = models.PositiveSmallIntegerField()
	poster = models.ImageField(upload_to="posters/", blank=True, null=True)
	cover = models.ImageField(upload_to="covers/", blank=True, null=True, help_text="Immagine di copertina dello spettacolo")
	artists = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="performances_as_artist")
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["title"]

	def __str__(self) -> str:
		return self.title

	def clean(self):
		validate_at_least_one_artist(self.artists)

	def can_be_scheduled(self):
		return self.status in {self.STATUS_ARTIST_CONFIRMED, self.STATUS_APPROVED}


class Performance(models.Model):
	STATUS_SCHEDULED = "scheduled"
	STATUS_CANCELLED = "cancelled"

	STATUS_CHOICES = [
		(STATUS_SCHEDULED, "Scheduled"),
		(STATUS_CANCELLED, "Cancelled"),
	]

	show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name="performances")
	theater = models.ForeignKey("theaters.Theater", on_delete=models.CASCADE, related_name="performances")
	hall = models.ForeignKey("theaters.Hall", on_delete=models.PROTECT, related_name="performances")
	starts_at = models.DateTimeField()
	base_price = models.DecimalField(max_digits=7, decimal_places=2, validators=[MinValueValidator(0)])
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED)
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["starts_at"]

	def clean(self):
		if self.hall and self.theater and self.hall.theater_id != self.theater_id:
			raise ValidationError("Hall must belong to the selected theater.")
		if self.show and not self.show.can_be_scheduled():
			raise ValidationError("Show is not ready to be scheduled.")

	def __str__(self) -> str:
		show_title = self.show.title if self.show_id else "Spettacolo"
		theater_name = self.theater.name if self.theater_id else "Senza teatro"
		return f"{show_title} @ {theater_name}"

	def zone_price(self, zone):
		zone_price = self.zone_prices.filter(zone=zone).first()
		return zone_price.price if zone_price else self.base_price


class PerformanceZonePrice(models.Model):
	performance = models.ForeignKey(Performance, on_delete=models.CASCADE, related_name="zone_prices")
	zone = models.CharField(max_length=20, choices=ZONE_CHOICES, default=ZONE_PLATEA)
	price = models.DecimalField(max_digits=7, decimal_places=2, validators=[MinValueValidator(0)])

	class Meta:
		unique_together = ("performance", "zone")
		ordering = ["zone"]

	def __str__(self) -> str:
		return f"{self.performance} - {self.zone}"
