from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Sequence

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

if TYPE_CHECKING:
    from apps.shows.models import Performance
    from apps.theaters.models import Theater


# ---------------------------------------------------------------------------
# QuerySets
# ---------------------------------------------------------------------------

class BookingQuerySet(models.QuerySet["Booking"]):
    def for_theater(self, theater: Theater) -> "BookingQuerySet":
        return self.filter(performance__auditorium__theater=theater)

    def confirmed(self) -> "BookingQuerySet":
        return self.filter(status=Booking.STATUS_CONFIRMED)

    def cancelled(self) -> "BookingQuerySet":
        return self.filter(status=Booking.STATUS_CANCELLED)

    def with_full_details(self) -> "BookingQuerySet":
        """Attach all data needed for list/detail views in a single pass."""
        return (
            self.select_related("user", "performance__show", "performance__auditorium")
            .prefetch_related("seats__seat")
        )


class BookingSeatQuerySet(models.QuerySet["BookingSeat"]):
    def for_performance(self, performance: Performance) -> "BookingSeatQuerySet":
        return self.filter(performance=performance)

    def confirmed(self) -> "BookingSeatQuerySet":
        """Only seats whose booking is confirmed."""
        return self.filter(booking__status=Booking.STATUS_CONFIRMED)

    def reserved_seat_ids(self):
        """Flat queryset of seat PKs — chain after for_performance().confirmed()."""
        return self.values_list("seat_id", flat=True)


BookingManager = models.Manager.from_queryset(BookingQuerySet)
BookingSeatManager = models.Manager.from_queryset(BookingSeatQuerySet)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Booking(models.Model):
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings"
    )
    performance = models.ForeignKey(
        "shows.Performance", on_delete=models.CASCADE, related_name="bookings"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED
    )
    total_price = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects: BookingManager = BookingManager()  # type: ignore[assignment]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.get_username()} - {self.performance}"

    def clean(self):
        # Ensure bookings are only created for scheduled, future performances.
        if self.performance_id:
            from apps.shows.models import Performance

            perf = Performance.objects.filter(pk=self.performance_id).first()
            if perf:
                if perf.status != Performance.STATUS_SCHEDULED:
                    raise ValidationError("Bookings can only be made for scheduled performances.")
                if perf.starts_at and perf.starts_at < timezone.now():
                    raise ValidationError("Cannot create bookings for performances in the past.")

    def save(self, *args, **kwargs):
        # Run full validation before saving to prevent accidental bookings
        # for non-schedulable performances. bulk_create bypasses save(), so
        # callers performing bulk inserts should validate separately.
        self.full_clean()
        super().save(*args, **kwargs)


class BookingSeat(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="seats")
    performance = models.ForeignKey(
        "shows.Performance", on_delete=models.CASCADE, related_name="seat_reservations"
    )
    seat = models.ForeignKey("theaters.Seat", on_delete=models.PROTECT)
    price_at_purchase = models.DecimalField(max_digits=7, decimal_places=2)

    objects: BookingSeatManager = BookingSeatManager()  # type: ignore[assignment]

    class Meta:
        unique_together = ("performance", "seat")

    def __str__(self) -> str:
        return f"{self.performance} {self.seat}"

    def clean(self):
        if self.booking and self.performance:
            if self.booking.performance.pk != self.performance.pk:
                raise ValidationError("Booking and performance must match.")

    def save(self, *args, **kwargs):
        # NOTE: bulk_create() bypasses save() and therefore clean().
        # Use BookingSeat.bulk_create_for_booking() for batch inserts so
        # the invariant is validated before writing.
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def bulk_create_for_booking(
        cls,
        booking: "Booking",
        performance: "Performance",
        seat_prices: list[tuple],
    ) -> Sequence["BookingSeat"]:
        """Create multiple BookingSeat rows in a single query.

        Validates the booking↔performance invariant before inserting, which
        plain bulk_create() would skip.  seat_prices is a list of
        (Seat, Decimal) tuples.
        """
        if booking.performance.pk != performance.pk:
            raise ValidationError("Il booking e la performance non corrispondono.")
        return cls.objects.bulk_create([
            cls(
                booking=booking,
                performance=performance,
                seat=seat,
                price_at_purchase=price,
            )
            for seat, price in seat_prices
        ])
