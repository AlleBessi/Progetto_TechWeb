from django.conf import settings
from django.db import models


class Role(models.Model):
	ROLE_ADMIN = "admin"
	ROLE_ARTIST = "artist"
	ROLE_MANAGER = "manager"
	ROLE_CLIENT = "client"

	CHOICES = [
		(ROLE_ADMIN, "Amministratore"),
		(ROLE_ARTIST, "Artista"),
		(ROLE_MANAGER, "Gestore"),
		(ROLE_CLIENT, "Cliente"),
	]

	name = models.CharField(max_length=20, choices=CHOICES, unique=True)

	class Meta:
		ordering = ["name"]

	def __str__(self) -> str:
		return self.get_name_display()


class Profile(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True)
	display_name = models.CharField(max_length=150, blank=True)
	city = models.CharField(max_length=120, blank=True)
	latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
	longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
	interests = models.ManyToManyField('shows.Category', blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self) -> str:
		return self.display_name or self.user.get_username()
