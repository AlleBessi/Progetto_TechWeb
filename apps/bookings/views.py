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


def allocate_seats(booking, performance, seats):
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
		except IntegrityError:
			messages.error(self.request, "Errore di integrità.")
			return redirect("bookings:booking_create", performance_id=self.performance.pk)
		except ValidationError as exc:
			messages.error(self.request, " ".join(exc.messages))
			return redirect("bookings:booking_create", performance_id=self.performance.pk)
		messages.success(self.request, "Prenotazione completata.")
		return super().form_valid(form)


class BookingUpdate(ClientOnlyMixin, FormView):
	"""Client-facing booking update. Reassign a booking's seats; POST rewrites
	the seats atomically."""

	form_class = BookingForm
	template_name = "bookings/booking_update.html"
	success_url = reverse_lazy("bookings:booking_list")

	def get_queryset(self):
		return Booking.objects.filter(user=self.request.user)

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
		return redirect("bookings:booking_update", booking_id=self.booking.pk)

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


class BookingCancelBase(View):
	http_method_names = ["post"]

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
