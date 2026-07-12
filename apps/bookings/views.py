from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import FormView
from django.urls import reverse, reverse_lazy

from apps.shows.models import Performance
from apps.core.mixins import ClientOnlyMixin, ManagerAccessMixin, TheaterScopedMixin

from .forms import BookingForm
from .models import Booking, BookingSeat
from .utils import build_zone_layout


def allocate_seats(booking, performance, seats):
	"""Replace ``booking``'s seats with ``seats`` and recompute total_price.

	Shared by the create and update flows. Relies on ``BookingSeat.clean()`` /
	the ``unique_together`` constraint for the availability check; the caller
	runs it inside a transaction so a conflict rolls back.
	"""
	seat_prices = [
		(seat, performance.zone_price(seat.auditorium_zone)) for seat in seats
	]
	booking.seats.all().delete()
	for seat, price in seat_prices:
		BookingSeat.objects.create(
			booking=booking,
			performance=performance,
			seat=seat,
			price_at_purchase=price,
		)
	booking.total_price = sum((price for _, price in seat_prices), Decimal("0.00"))
	booking.save(update_fields=["total_price"])


class BookingList(ClientOnlyMixin, ListView):
	model = Booking
	template_name = "bookings/booking_list.html"
	context_object_name = "bookings"

	def get_queryset(self):
		return (
			Booking.objects.filter(user=self.request.user)
			.select_related("performance__show", "performance__auditorium__theater")
			.prefetch_related("seats__seat")
		)


class BookingCancelBase(View):
	"""Cancel (hard-delete) a booking, freeing its seats. POST only.

	Access control and scoping (queryset, success URL, cancel rule) are supplied
	by the concrete client / manager subclasses.
	"""

	def get_queryset(self):
		raise NotImplementedError

	def get_success_url(self):
		raise NotImplementedError

	def cancel_blocked_redirect(self, booking) -> HttpResponse | None:
		"""Return a redirect if this booking may not be cancelled, else None."""
		return None

	def post(self, request, *args, **kwargs):
		booking = get_object_or_404(self.get_queryset(), pk=kwargs.get("booking_id"))
		blocked = self.cancel_blocked_redirect(booking)
		if blocked is not None:
			return blocked
		booking.delete()
		messages.success(request, "Prenotazione annullata.")
		return redirect(self.get_success_url())


class BookingCancel(ClientOnlyMixin, BookingCancelBase):
	"""Client-facing booking cancellation."""

	def get_queryset(self):
		return Booking.objects.filter(user=self.request.user)

	def get_success_url(self):
		return reverse("bookings:booking_list")

	def cancel_blocked_redirect(self, booking):
		performance = booking.performance
		if performance.status != Performance.STATUS_SCHEDULED or performance.starts_at < timezone.now():
			messages.error(self.request, "Non e possibile annullare una prenotazione per una performance gia iniziata o non piu disponibile.")
			return redirect(self.get_success_url())
		return None


class BookingCreate(ClientOnlyMixin, FormView):
	model = Booking
	template_name = "bookings/booking_create.html"
	form_class = BookingForm
	success_url = reverse_lazy("bookings:booking_list")
	context_object_name = "performance"
	performance: Performance

	def dispatch(self, request, *args, **kwargs) -> HttpResponse:
		self.performance = get_object_or_404(Performance, pk=kwargs.get("performance_id"))
		if self.performance.status != Performance.STATUS_SCHEDULED or self.performance.starts_at < timezone.now():
			messages.error(request, "Performance non disponibile per la prenotazione.")
			return redirect("core:home")  # type: ignore[return-value]
		return super().dispatch(request, *args, **kwargs)  # type: ignore[return-value]

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["performance"] = self.performance
		return kwargs

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["performance"] = self.performance
		return ctx

	def form_valid(self, form):
		selected_seats = list(form.cleaned_data["seats"])
		try:
			with transaction.atomic():
				booking = Booking.objects.create(user=self.request.user, performance=self.performance)
				allocate_seats(booking, self.performance, selected_seats)
		except (ValidationError, IntegrityError):
			messages.error(self.request, "Alcuni posti non sono più disponibili.")
			return redirect("bookings:booking_create", performance_id=self.performance.pk)
		messages.success(self.request, "Prenotazione completata.")
		return super().form_valid(form)


class BookingUpdateBase(FormView):
	"""Reassign a booking's seats. POST rewrites the seats atomically.

	Access control and scoping (queryset, success URL, redirect targets) are
	supplied by the concrete client / manager subclasses.
	"""

	form_class = BookingForm

	def get_queryset(self):
		raise NotImplementedError

	@cached_property
	def booking(self) -> Booking:
		return get_object_or_404(self.get_queryset(), pk=self.kwargs.get("booking_id"))

	@cached_property
	def performance(self) -> Performance:
		return self.booking.performance

	def editable_or_redirect(self):
		"""Return a redirect response if the booking may not be edited, else None."""
		if self.performance.status != Performance.STATUS_SCHEDULED or self.performance.starts_at < timezone.now():
			messages.error(self.request, "Performance non disponibile per la modifica.")
			return redirect(self.get_success_url())
		return None

	def conflict_redirect(self):
		raise NotImplementedError

	def get(self, request, *args, **kwargs):
		return self.editable_or_redirect() or super().get(request, *args, **kwargs)

	def get_initial(self):
		return {"seats": self.booking.seats.values_list("seat_id", flat=True)}

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["performance"] = self.performance
		kwargs["exclude_booking"] = self.booking
		return kwargs

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		ctx["booking"] = self.booking
		ctx["performance"] = self.performance
		return ctx

	def form_valid(self, form):
		blocked = self.editable_or_redirect()
		if blocked is not None:
			return blocked
		selected_seats = list(form.cleaned_data["seats"])
		try:
			with transaction.atomic():
				allocate_seats(self.booking, self.performance, selected_seats)
		except (ValidationError, IntegrityError):
			messages.error(self.request, "Alcuni posti non sono più disponibili.")
			return self.conflict_redirect()
		messages.success(self.request, "Prenotazione aggiornata.")
		return super().form_valid(form)


class BookingUpdate(ClientOnlyMixin, BookingUpdateBase):
	"""Client-facing booking update."""

	template_name = "bookings/booking_update.html"
	success_url = reverse_lazy("bookings:booking_list")

	def get_queryset(self):
		return Booking.objects.filter(user=self.request.user)

	def conflict_redirect(self):
		return redirect("bookings:booking_update", booking_id=self.booking.pk)


# ---------------------------------------------------------------------------
# Theater-manager variants — reuse the base booking views, scoped to a theater.
# Routed from theaters/urls.py under the theaters: namespace.
# ---------------------------------------------------------------------------

class BookingCancelManager(TheaterScopedMixin, ManagerAccessMixin, BookingCancelBase):
	"""Cancel a booking on behalf of a theater manager (POST only).

	Managers may cancel regardless of the performance schedule, so the base
	``cancel_blocked_redirect`` (always None) is used as-is.
	"""

	def get_queryset(self):
		return Booking.objects.filter(performance__auditorium__theater=self.get_theater())

	def get_success_url(self):
		return reverse("theaters:management_bookings", kwargs={"theater_id": self.get_theater().pk})


class BookingUpdateManager(TheaterScopedMixin, ManagerAccessMixin, BookingUpdateBase):
	"""Update a booking's seats on behalf of a theater manager."""

	template_name = "bookings/booking_update_manager.html"

	def get_queryset(self):
		return (
			Booking.objects.filter(performance__auditorium__theater=self.get_theater())
			.select_related("performance__auditorium", "performance__show")
		)

	def get_success_url(self):
		return reverse("theaters:management_bookings", kwargs={"theater_id": self.get_theater().pk})

	def conflict_redirect(self):
		return redirect("theaters:booking_update", theater_id=self.get_theater().pk, booking_id=self.booking.pk)

	def get_context_data(self, **kwargs):
		ctx = super().get_context_data(**kwargs)
		performance = self.performance
		reserved = set(
			BookingSeat.objects.for_performance(performance)
			.exclude(booking=self.booking)
			.reserved_seat_ids()
		)
		selected_ids = set(self.booking.seats.values_list("seat_id", flat=True))
		ctx["theater"] = self.get_theater()
		ctx["zone_layout"] = build_zone_layout(performance, reserved, selected_ids)
		return ctx
