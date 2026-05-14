import string

from django.conf import settings
from django.db import models

ZONE_PLATEA = "platea"
ZONE_GALLERIA = "galleria"
ZONE_LOGGIONE = "loggione"
ZONE_BALCONATA = "balconata"
ZONE_LATERALE = "laterale"
ZONE_VIP = "vip"

ZONE_CHOICES = [
	(ZONE_PLATEA, "Platea"),
	(ZONE_GALLERIA, "Galleria"),
	(ZONE_LOGGIONE, "Loggione"),
	(ZONE_BALCONATA, "Balconata"),
	(ZONE_LATERALE, "Laterale"),
	(ZONE_VIP, "VIP"),
]

ZONE_LABELS = dict(ZONE_CHOICES)


class Theater(models.Model):
	name = models.CharField(max_length=200)
	description = models.TextField(blank=True)
	address = models.CharField(max_length=255)
	city = models.CharField(max_length=120)
	province = models.CharField(max_length=40, blank=True)
	postal_code = models.CharField(max_length=10, blank=True)
	latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
	longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self) -> str:
		return self.name


class Hall(models.Model):
	theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name="halls")
	name = models.CharField(max_length=100)
	seat_rows = models.PositiveSmallIntegerField(default=10)
	seat_cols = models.PositiveSmallIntegerField(default=12)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self) -> str:
		return f"{self.theater.name} - {self.name}"

	def _row_labels(self, count):
		labels = []
		alphabet = string.ascii_uppercase
		for i in range(count):
			first = i // len(alphabet)
			second = i % len(alphabet)
			if first == 0:
				labels.append(alphabet[second])
			else:
				labels.append(alphabet[first - 1] + alphabet[second])
		return labels

	def _zone_for_row(self, row_index, rows):
		if rows <= 0:
			return ZONE_PLATEA
		fraction = (row_index + 1) / rows
		if fraction <= 0.4:
			return ZONE_PLATEA
		if fraction <= 0.75:
			return ZONE_GALLERIA
		return ZONE_LOGGIONE

	def create_seats(self, force=False):
		if self.seats.exists():
			if not force:
				return
			self.seats.all().delete()

		zones = list(self.zones.order_by("order", "id"))
		if zones:
			total_rows = sum(zone.rows for zone in zones)
			row_labels = self._row_labels(total_rows)
			row_cursor = 0
			for zone in zones:
				for _ in range(zone.rows):
					row_label = row_labels[row_cursor]
					row_cursor += 1
					for number in range(1, zone.seats_per_row + 1):
						Seat.objects.create(hall=self, row=row_label, number=number, zone=zone.zone)
			return

		rows = min(self.seat_rows, len(string.ascii_uppercase))
		for row_index in range(rows):
			row_label = string.ascii_uppercase[row_index]
			zone = self._zone_for_row(row_index, rows)
			for number in range(1, self.seat_cols + 1):
				Seat.objects.create(hall=self, row=row_label, number=number, zone=zone)

	def regenerate_seats(self):
		self.create_seats(force=True)


class HallZone(models.Model):
	hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name="zones")
	zone = models.CharField(max_length=20, choices=ZONE_CHOICES)
	rows = models.PositiveSmallIntegerField(default=4)
	seats_per_row = models.PositiveSmallIntegerField(default=10)
	order = models.PositiveSmallIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["order", "id"]
		unique_together = ("hall", "zone")

	def __str__(self) -> str:
		return f"{self.hall.name} - {self.get_zone_display()}"


class Seat(models.Model):
	hall = models.ForeignKey(Hall, on_delete=models.CASCADE, related_name="seats")
	row = models.CharField(max_length=2)
	number = models.PositiveSmallIntegerField()
	zone = models.CharField(max_length=20, choices=ZONE_CHOICES, default=ZONE_PLATEA)
	is_accessible = models.BooleanField(default=False)

	class Meta:
		unique_together = ("hall", "row", "number")

	def __str__(self) -> str:
		return f"{self.hall.name} {self.row}{self.number}"


class TheaterAdmin(models.Model):
	theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name="admins")
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	added_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ("theater", "user")

	def __str__(self) -> str:
		return f"{self.user.get_username()} @ {self.theater.name}"
