from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy

from apps.shows.models import Performance
from apps.core.mixins import ClientOnlyMixin

from .forms import BookingForm
from .models import Booking, BookingSeat


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


class BookingCancel(ClientOnlyMixin, View):
	model = Booking
	template_name = "bookings/booking_list.html"
	context_object_name = "booking"

	def post(self, request, booking_id):
		booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
		performance = booking.performance
		if booking.status == Booking.STATUS_CANCELLED:
			messages.error(request, "Prenotazione gia annullata.")
			return redirect("bookings:booking_list")
		if performance.status != Performance.STATUS_SCHEDULED or performance.starts_at < timezone.now():
			messages.error(request, "Non e possibile annullare una prenotazione per una performance gia iniziata o non piu disponibile.")
			return redirect("bookings:booking_list")
		with transaction.atomic():
			booking.status = Booking.STATUS_CANCELLED
			booking.save(update_fields=["status"])
			# Libera i posti: rimuovendo i BookingSeat il posto torna disponibile
			# e riprenotabile senza violare unique_together(performance, seat).
			BookingSeat.objects.filter(booking=booking).delete()
		messages.success(request, "Prenotazione annullata.")
		return redirect("bookings:booking_list")


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
		with transaction.atomic():
			reserved_ids = set(
				BookingSeat.objects.select_for_update()
				.for_performance(self.performance)
				.confirmed()
				.reserved_seat_ids()
            )
			conflict = [seat for seat in selected_seats if seat.id in reserved_ids]
			if conflict:
				messages.error(self.request, "Alcuni posti non sono piu disponibili.")
				return redirect("bookings:booking_create", performance_id=self.performance.pk)
			booking = Booking.objects.create(user=self.request.user, performance=self.performance)
			total = Decimal("0.00")
			for seat in selected_seats:
				price = self.performance.zone_price(seat.auditorium_zone)
				BookingSeat.objects.create(
                    booking=booking,
                    performance=self.performance,
                    seat=seat,
                    price_at_purchase=price,
                )
				total += price
			booking.total_price = total
			booking.save(update_fields=["total_price"])
		messages.success(self.request, "Prenotazione completata.")
		return super().form_valid(form)


class BookingUpdate(ClientOnlyMixin, FormView):
	model = Booking
	template_name = "bookings/booking_update.html"
	form_class = BookingForm
	success_url = reverse_lazy("bookings:booking_list")
	context_object_name = "booking"
	booking: Booking
	performance: Performance

	def dispatch(self, request, *args, **kwargs) -> HttpResponse:
		if not request.user.is_authenticated:
			# Avoid querying with an AnonymousUser as the `user` FK filter below;
			# let ClientOnlyMixin's permission check (super().dispatch()) deny access.
			return super().dispatch(request, *args, **kwargs)  # type: ignore[return-value]
		self.booking = get_object_or_404(Booking, pk=kwargs.get("booking_id"), user=request.user)
		self.performance = self.booking.performance
		if self.booking.status == Booking.STATUS_CANCELLED:
			messages.error(request, "Prenotazione annullata, non modificabile.")
			return redirect("bookings:booking_list")  # type: ignore[return-value]
		if self.performance.status != Performance.STATUS_SCHEDULED or self.performance.starts_at < timezone.now():
			messages.error(request, "Performance non disponibile per la modifica.")
			return redirect("bookings:booking_list")  # type: ignore[return-value]
		return super().dispatch(request, *args, **kwargs)  # type: ignore[return-value]

	def get_initial(self):
		return {"seats": BookingSeat.objects.filter(booking=self.booking).values_list("seat_id", flat=True)}
 
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
		selected_seats = list(form.cleaned_data["seats"])
		with transaction.atomic():
			reserved_ids = set(
				BookingSeat.objects.select_for_update()
				.for_performance(self.performance)
				.confirmed()
				.exclude(booking=self.booking)
				.reserved_seat_ids()
            )
			conflict = [seat for seat in selected_seats if seat.id in reserved_ids]
			if conflict:
				messages.error(self.request, "Alcuni posti non sono piu disponibili.")
				return redirect("bookings:booking_update", booking_id=self.booking.pk)
			BookingSeat.objects.filter(booking=self.booking).delete()
			total = Decimal("0.00")
			for seat in selected_seats:
				price = self.performance.zone_price(seat.auditorium_zone)
				BookingSeat.objects.create(
                    booking=self.booking,
                    performance=self.performance,
                    seat=seat,
                    price_at_purchase=price,
                )
				total += price
			self.booking.total_price = total
			self.booking.save(update_fields=["total_price"])
		messages.success(self.request, "Prenotazione aggiornata.")
		return super().form_valid(form)
