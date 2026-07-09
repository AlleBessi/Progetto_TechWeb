import string

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max


# ---------------------------------------------------------------------------
# QuerySets
# ---------------------------------------------------------------------------

class TheaterQuerySet(models.QuerySet):
    def accessible_by(self, user):
        """Return only the theaters the given user is allowed to manage."""
        if user.is_superuser or user.groups.filter(name="admin").exists():
            return self
        return self.filter(admins__user=user)


class TheaterAdminQuerySet(models.QuerySet):
    def is_admin(self, user, theater) -> bool:
        """Return True if *user* is an assigned manager of *theater*."""
        return self.filter(user=user, theater=theater).exists()


# Manager.from_queryset() exposes every QuerySet method directly on the manager.
TheaterManager = models.Manager.from_queryset(TheaterQuerySet)
TheaterAdminManager = models.Manager.from_queryset(TheaterAdminQuerySet)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Theater(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to="theaters/", blank=True, null=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    province = models.CharField(max_length=40, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    opening_hours = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TheaterManager()

    def __str__(self) -> str:
        return self.name

    def total_seats(self) -> int:
        return Seat.objects.filter(auditorium__theater=self).count()


class Auditorium(models.Model):
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name="auditoriums")
    cod_auditorium = models.PositiveIntegerField(blank=True, null=True)
    name = models.CharField(max_length=100)
    seat_rows = models.PositiveSmallIntegerField(default=0)
    seat_cols = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("theater", "cod_auditorium")

    def __str__(self) -> str:
        return f"{self.theater.name} - {self.name}"

    def _next_cod_auditorium(self) -> int:
        """Compute the next sequential code for this theater.

        Locks the parent Theater row with SELECT FOR UPDATE, which serialises
        all concurrent inserts for the same theater inside their respective
        transactions.  The second transaction waits at the lock, then reads
        the updated MAX and computes a fresh, non-conflicting value.
        No retry loop is required.

        Must be called inside an existing transaction.atomic() block.
        """
        Theater.objects.select_for_update().get(pk=self.theater_id)
        result = Auditorium.objects.filter(theater_id=self.theater_id).aggregate(
            max_code=Max("cod_auditorium")
        )
        return 1 if result["max_code"] is None else result["max_code"] + 1

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.cod_auditorium is None:
                self.cod_auditorium = self._next_cod_auditorium()
            super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Seat generation
    # ------------------------------------------------------------------

    @staticmethod
    def _row_labels(count: int) -> list[str]:
        alphabet = string.ascii_uppercase
        labels = []
        for i in range(count):
            first, second = divmod(i, len(alphabet))
            labels.append(
                alphabet[second] if first == 0 else alphabet[first - 1] + alphabet[second]
            )
        return labels

    @transaction.atomic
    def create_seats(self, force: bool = False) -> None:
        """Generate Seat rows from the zone definitions using bulk_create."""
        if self.seats.exists():
            if not force:
                return
            self.seats.all().delete()

        zones = list(self.zones.order_by("order", "id"))
        if not zones:
            return

        row_labels = self._row_labels(sum(z.rows for z in zones))
        seats: list["Seat"] = []
        row_cursor = 0
        for zone in zones:
            for _ in range(zone.rows):
                label = row_labels[row_cursor]
                row_cursor += 1
                seats.extend(
                    Seat(auditorium=self, auditorium_zone=zone, row=label, number=n)
                    for n in range(1, zone.seats_per_row + 1)
                )
        Seat.objects.bulk_create(seats)

    def regenerate_seats(self) -> None:
        self.create_seats(force=True)


class AuditoriumZone(models.Model):
    auditorium = models.ForeignKey(Auditorium, on_delete=models.CASCADE, related_name="zones")
    cod_zone = models.PositiveIntegerField(blank=True, null=True)
    zone = models.CharField(max_length=50)
    rows = models.PositiveSmallIntegerField(default=4)
    seats_per_row = models.PositiveSmallIntegerField(default=10)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("auditorium", "cod_zone")

    def __str__(self) -> str:
        return f"{self.auditorium.name} - {self.zone}"

    def _next_cod_zone(self) -> int:
        """Lock the parent Auditorium row to serialise zone-code generation.

        Must be called inside an existing transaction.atomic() block.
        """
        Auditorium.objects.select_for_update().get(pk=self.auditorium_id)
        result = AuditoriumZone.objects.filter(auditorium_id=self.auditorium_id).aggregate(
            max_code=Max("cod_zone")
        )
        return 1 if result["max_code"] is None else result["max_code"] + 1

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.cod_zone is None:
                self.cod_zone = self._next_cod_zone()
            super().save(*args, **kwargs)


class Seat(models.Model):
    auditorium = models.ForeignKey(Auditorium, on_delete=models.CASCADE, related_name="seats")
    auditorium_zone = models.ForeignKey(AuditoriumZone, on_delete=models.CASCADE, related_name="seats")
    row = models.CharField(max_length=2)
    number = models.PositiveSmallIntegerField()
    is_accessible = models.BooleanField(default=False)

    class Meta:
        unique_together = ("auditorium", "row", "number")

    def __str__(self) -> str:
        return f"{self.auditorium.name} {self.row}{self.number}"


class TheaterAdmin(models.Model):
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name="admins")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    objects = TheaterAdminManager()

    class Meta:
        unique_together = ("theater", "user")

    def __str__(self) -> str:
        return f"{self.user.get_username()} @ {self.theater.name}"

    def clean(self):
        if self.user_id and not self.user.groups.filter(name="manager").exists():
            raise ValidationError({"user": "Solo i gestori possono essere assegnati ai teatri."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)