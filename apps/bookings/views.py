from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.shows.models import Performance
from apps.theaters.models import ZONE_CHOICES
from apps.theaters.utils import is_any_theater_admin

from .forms import BookingForm
from .models import Booking, BookingSeat


def _deny_booking_access(request):
	if not request.user.is_authenticated:
		return False
	is_artist = (
		hasattr(request.user, "profile")
		and request.user.profile.role
		and request.user.profile.role.name == "artist"
	)
	if is_artist:
		messages.error(request, "Gli artisti non possono prenotare spettacoli.")
		return True
	if is_any_theater_admin(request.user):
		messages.error(request, "I gestori non possono prenotare spettacoli.")
		return True
	return False


def _build_zone_layout(performance, reserved_ids, selected_ids=None):
	selected_ids = selected_ids or set()
	hall = performance.hall
	zone_defs = list(hall.zones.order_by("order", "id"))
	if zone_defs:
		zone_order = [zone.zone for zone in zone_defs]
		zone_labels = {zone.zone: zone.get_zone_display() for zone in zone_defs}
	else:
		zone_order = [zone for zone, _label in ZONE_CHOICES]
		zone_labels = {zone: label for zone, label in ZONE_CHOICES}

	zone_rows = {zone: defaultdict(list) for zone in zone_order}
	seats = performance.hall.seats.all().order_by("row", "number")
	for seat in seats:
		zone_rows.setdefault(seat.zone, defaultdict(list))
		zone_rows[seat.zone][seat.row].append(
			{
				"seat": seat,
				"zone": seat.zone,
				"price": performance.zone_price(seat.zone),
				"is_reserved": seat.id in reserved_ids,
				"is_selected": seat.id in selected_ids,
			}
		)

	zone_layout = []
	for index, zone in enumerate(zone_order, start=1):
		rows = zone_rows.get(zone)
		if not rows:
			continue
		zone_layout.append(
			{
				"zone": zone,
				"label": zone_labels.get(zone, zone),
				"price": performance.zone_price(zone),
				"rows": sorted(rows.items()),
				"color_class": f"seat-zone-{index}",
			}
		)
	return zone_layout


@login_required
def performance_booking(request, performance_id):
	if _deny_booking_access(request):
		return redirect("core:home")
	performance = get_object_or_404(Performance, pk=performance_id)
	if performance.status != Performance.STATUS_SCHEDULED or performance.starts_at < timezone.now():
		messages.error(request, "Performance non disponibile per la prenotazione.")
		return redirect("core:home")
	if request.method == "POST":
		form = BookingForm(performance, request.POST)
		if form.is_valid():
			selected_seats = list(form.cleaned_data["seats"])
			with transaction.atomic():
				reserved_ids = set(
					BookingSeat.objects.select_for_update()
					.filter(performance=performance, booking__status=Booking.STATUS_CONFIRMED)
					.values_list("seat_id", flat=True)
				)
				conflict = [seat for seat in selected_seats if seat.id in reserved_ids]
				if conflict:
					messages.error(request, "Alcuni posti non sono piu disponibili.")
					return redirect("bookings:performance_booking", performance_id=performance.id)
				booking = Booking.objects.create(user=request.user, performance=performance)
				total = 0
				for seat in selected_seats:
					price = performance.zone_price(seat.zone)
					BookingSeat.objects.create(
						booking=booking,
						performance=performance,
						seat=seat,
						price_at_purchase=price,
					)
					total += price
				booking.total_price = total
				booking.save(update_fields=["total_price"])
			messages.success(request, "Prenotazione completata.")
			return redirect("bookings:list")
	else:
		form = BookingForm(performance)

	reserved = set(
		BookingSeat.objects.filter(performance=performance, booking__status=Booking.STATUS_CONFIRMED).values_list(
			"seat_id", flat=True
		)
	)
	zone_layout = _build_zone_layout(performance, reserved)

	return render(
		request,
		"bookings/performance_booking.html",
		{"performance": performance, "form": form, "zone_layout": zone_layout},
	)


@login_required
def booking_list(request):
	if _deny_booking_access(request):
		return redirect("core:home")
	bookings = (
		Booking.objects.filter(user=request.user)
		.select_related("performance__show", "performance__theater")
		.prefetch_related("seats__seat")
	)
	return render(request, "bookings/booking_list.html", {"bookings": bookings})


@login_required
@require_POST
def booking_cancel(request, booking_id):
	if _deny_booking_access(request):
		return redirect("core:home")
	booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
	if booking.status != Booking.STATUS_CANCELLED:
		booking.status = Booking.STATUS_CANCELLED
		booking.save(update_fields=["status"])
		messages.success(request, "Prenotazione annullata.")
	return redirect("bookings:list")


@login_required
def booking_update(request, booking_id):
	if _deny_booking_access(request):
		return redirect("core:home")
	booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
	if booking.status == Booking.STATUS_CANCELLED:
		messages.error(request, "Prenotazione annullata, non modificabile.")
		return redirect("bookings:list")
	performance = booking.performance
	if performance.status != Performance.STATUS_SCHEDULED or performance.starts_at < timezone.now():
		messages.error(request, "Performance non disponibile per la modifica.")
		return redirect("bookings:list")

	if request.method == "POST":
		form = BookingForm(performance, request.POST, exclude_booking=booking)
		if form.is_valid():
			selected_seats = list(form.cleaned_data["seats"])
			with transaction.atomic():
				reserved_ids = set(
					BookingSeat.objects.select_for_update()
					.filter(performance=performance, booking__status=Booking.STATUS_CONFIRMED)
					.exclude(booking=booking)
					.values_list("seat_id", flat=True)
				)
				conflict = [seat for seat in selected_seats if seat.id in reserved_ids]
				if conflict:
					messages.error(request, "Alcuni posti non sono piu disponibili.")
					return redirect("bookings:update", booking_id=booking.id)

				booking.seats.all().delete()
				total = 0
				for seat in selected_seats:
					price = performance.zone_price(seat.zone)
					BookingSeat.objects.create(
						booking=booking,
						performance=performance,
						seat=seat,
						price_at_purchase=price,
					)
					total += price
				booking.total_price = total
				booking.save(update_fields=["total_price"])
			messages.success(request, "Prenotazione aggiornata.")
			return redirect("bookings:list")
	else:
		form = BookingForm(performance, exclude_booking=booking)

	reserved = set(
		BookingSeat.objects.filter(performance=performance, booking__status=Booking.STATUS_CONFIRMED)
		.exclude(booking=booking)
		.values_list("seat_id", flat=True)
	)
	selected_ids = set(booking.seats.values_list("seat_id", flat=True))
	zone_layout = _build_zone_layout(performance, reserved, selected_ids)

	return render(
		request,
		"bookings/booking_update.html",
		{
			"booking": booking,
			"performance": performance,
			"form": form,
			"zone_layout": zone_layout,
		},
	)
