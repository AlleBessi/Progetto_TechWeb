from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

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

    def with_full_details(self) -> "BookingQuerySet":
        """Attach all data needed for list/detail views in a single pass."""
        return (
            self.select_related("user", "performance__show", "performance__auditorium")
            .prefetch_related("seats__seat")
        )


class BookingSeatQuerySet(models.QuerySet["BookingSeat"]):
    def for_performance(self, performance: Performance) -> "BookingSeatQuerySet":
        return self.filter(performance=performance)

    def reserved_seat_ids(self):
        """Flat queryset of seat PKs — chain after for_performance()."""
        return self.values_list("seat_id", flat=True)

    def conflicting_seat_ids(
        self, performance, seat_ids, exclude_booking=None, exclude_pk=None, lock=False
    ) -> set:
        """Seat IDs among ``seat_ids`` already held by a booking for
        ``performance``.

        The single source of truth for seat-availability. Views pass
        ``lock=True`` inside a transaction for a race-safe
        (``SELECT ... FOR UPDATE``) check; ``exclude_booking`` skips a booking's
        own seats (updates) and ``exclude_pk`` skips a single row (model
        self-validation).
        """
        qs = self.for_performance(performance).filter(seat_id__in=seat_ids)
        if exclude_booking is not None:
            qs = qs.exclude(booking=exclude_booking)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if lock:
            qs = qs.select_for_update()
        return set(qs.reserved_seat_ids())


BookingManager = models.Manager.from_queryset(BookingQuerySet)
BookingSeatManager = models.Manager.from_queryset(BookingSeatQuerySet)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Booking(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings"
    )
    performance = models.ForeignKey(
        "shows.Performance", on_delete=models.CASCADE, related_name="bookings"
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
        if self.performance_id and self.seat_id:
            conflict = BookingSeat.objects.conflicting_seat_ids(
                self.performance_id, [self.seat_id], exclude_pk=self.pk
            )
            if conflict:
                raise ValidationError("Questo posto e' gia' stato prenotato.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
