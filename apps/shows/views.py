from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Role
from apps.theaters.models import Hall, Theater, ZONE_PLATEA
from apps.theaters.utils import is_theater_admin

from .forms import PerformanceCreateForm, PerformanceUpdateForm, ShowForm
from .models import Performance, PerformanceZonePrice, Show


def show_list(request):
	shows = Show.objects.filter(status=Show.STATUS_APPROVED).select_related("category")
	return render(request, "shows/show_list.html", {"shows": shows})


def show_detail(request, show_id):
	show = get_object_or_404(Show, pk=show_id)
	if show.status != Show.STATUS_APPROVED:
		if not request.user.is_authenticated or show.created_by_id != request.user.id:
			raise PermissionDenied
	upcoming = (
		show.performances.filter(starts_at__gte=timezone.now(), status=Performance.STATUS_SCHEDULED)
		.select_related("theater")
		.order_by("starts_at")
	)
	return render(request, "shows/show_detail.html", {"show": show, "performances": upcoming})


def _is_artist(user):
	return (
		user.is_authenticated
		and hasattr(user, "profile")
		and user.profile.role
		and user.profile.role.name == Role.ROLE_ARTIST
	)


@login_required
@user_passes_test(_is_artist)
def artist_dashboard(request):
	shows = Show.objects.filter(created_by=request.user).select_related("category")
	return render(request, "shows/artist_dashboard.html", {"shows": shows})


@login_required
@user_passes_test(_is_artist)
def show_create(request):
	if request.method == "POST":
		form = ShowForm(request.POST, request.FILES)
		if form.is_valid():
			show = form.save(commit=False)
			show.created_by = request.user
			show.save()
			messages.success(request, "Spettacolo creato in bozza.")
			return redirect("shows:artist_dashboard")
	else:
		form = ShowForm()
	return render(request, "shows/show_form.html", {"form": form})


@login_required
@user_passes_test(_is_artist)
def show_confirm(request, show_id):
	show = get_object_or_404(Show, pk=show_id, created_by=request.user)
	if show.status == Show.STATUS_DRAFT:
		show.status = Show.STATUS_ARTIST_CONFIRMED
		show.save(update_fields=["status"])
		messages.success(request, "Spettacolo confermato per la programmazione.")
	return redirect("shows:artist_dashboard")


@login_required
@user_passes_test(_is_artist)
def show_edit(request, show_id):
	show = get_object_or_404(Show, pk=show_id, created_by=request.user)
	if request.method == "POST":
		form = ShowForm(request.POST, request.FILES, instance=show)
		if form.is_valid():
			form.save()
			messages.success(request, "Spettacolo aggiornato.")
			return redirect("shows:artist_dashboard")
	else:
		form = ShowForm(instance=show)
	return render(request, "shows/show_form.html", {"form": form, "show": show})


@login_required
@user_passes_test(_is_artist)
@require_POST
def show_delete(request, show_id):
	show = get_object_or_404(Show, pk=show_id, created_by=request.user)
	if show.performances.exists():
		messages.error(request, "Non puoi eliminare uno spettacolo gia programmato.")
		return redirect("shows:artist_dashboard")
	show.delete()
	messages.success(request, "Spettacolo eliminato.")
	return redirect("shows:artist_dashboard")


@login_required
def performance_create(request, theater_id):
	theater = get_object_or_404(Theater, pk=theater_id)
	if not is_theater_admin(request.user, theater):
		raise PermissionDenied
	hall_id = request.GET.get("hall") or request.POST.get("hall")
	hall = None
	if hall_id:
		hall = get_object_or_404(Hall, pk=hall_id, theater=theater)
	if hall is None:
		return render(
			request,
			"shows/performance_form.html",
			{"theater": theater, "halls": theater.halls.all(), "hall": None},
		)

	zones = list(hall.zones.order_by("order", "id"))
	if not zones:
		messages.error(request, "Configura prima le zone della sala.")
		return redirect("theaters:hall_manage", theater_id=theater.id, hall_id=hall.id)
	if request.method == "POST":
		form = PerformanceCreateForm(theater, hall=hall, zones=zones, data=request.POST)
		if form.is_valid():
			show = form.cleaned_data["show"]
			starts_list = form.cleaned_data["starts_at_list"]
			zone_prices = {code: form.cleaned_data[f"price_{code}"] for code in form.zone_codes}
			base_price = zone_prices.get(ZONE_PLATEA) or min(zone_prices.values())
			for starts_at in starts_list:
				performance = Performance.objects.create(
					show=show,
					theater=theater,
					hall=hall,
					starts_at=starts_at,
					base_price=base_price,
					created_by=request.user,
				)
				if zone_prices:
					for zone_code, price in zone_prices.items():
						PerformanceZonePrice.objects.get_or_create(
							performance=performance,
							zone=zone_code,
							defaults={"price": price},
						)
			if show.status == Show.STATUS_ARTIST_CONFIRMED:
				show.status = Show.STATUS_APPROVED
				show.save(update_fields=["status"])
			messages.success(request, "Performance create con successo.")
			return redirect("theaters:detail", theater_id=theater.id)
	else:
		form = PerformanceCreateForm(theater, hall=hall, zones=zones)

	return render(
		request,
		"shows/performance_form.html",
		{
			"form": form,
			"theater": theater,
			"hall": hall,
			"halls": theater.halls.all(),
			"zones": zones,
		},
	)


@login_required
def performance_edit(request, performance_id):
	performance = get_object_or_404(Performance, pk=performance_id)
	if not is_theater_admin(request.user, performance.theater):
		raise PermissionDenied
	zones = list(performance.hall.zones.order_by("order", "id"))
	if request.method == "POST":
		form = PerformanceUpdateForm(performance, zones=zones, data=request.POST)
		if form.is_valid():
			performance.starts_at = form.cleaned_data["starts_at"]
			if zones:
				zone_prices = {code: form.cleaned_data[f"price_{code}"] for code in form.zone_codes}
				performance.base_price = zone_prices.get(ZONE_PLATEA) or min(zone_prices.values())
				performance.save(update_fields=["starts_at", "base_price"])
				for zone_code, price in zone_prices.items():
					PerformanceZonePrice.objects.update_or_create(
						performance=performance,
						zone=zone_code,
						defaults={"price": price},
					)
			else:
				performance.base_price = form.cleaned_data["base_price"]
				performance.save(update_fields=["starts_at", "base_price"])
			messages.success(request, "Performance aggiornata.")
			return redirect("theaters:detail", theater_id=performance.theater.id)
	else:
		form = PerformanceUpdateForm(performance, zones=zones, initial={"starts_at": performance.starts_at})
	return render(
		request,
		"shows/performance_edit.html",
		{"form": form, "performance": performance, "theater": performance.theater, "zones": zones},
	)


@login_required
@require_POST
def performance_delete(request, performance_id):
	performance = get_object_or_404(Performance, pk=performance_id)
	if not is_theater_admin(request.user, performance.theater):
		raise PermissionDenied
	if performance.bookings.exists():
		messages.error(request, "Non puoi eliminare una performance con prenotazioni.")
		return redirect("theaters:detail", theater_id=performance.theater.id)
	performance.delete()
	messages.success(request, "Performance eliminata.")
	return redirect("theaters:detail", theater_id=performance.theater.id)
