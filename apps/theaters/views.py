from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bookings.models import Booking
from apps.shows.models import Performance

from .forms import HallForm, HallZoneFormSet, TheaterAdminForm, TheaterForm
from .models import Hall, Theater, TheaterAdmin
from .utils import is_any_theater_admin, is_theater_admin


def theater_list(request):
	theaters = Theater.objects.all().order_by("name")
	return render(request, "theaters/theater_list.html", {"theaters": theaters})


def theater_detail(request, theater_id):
	theater = get_object_or_404(Theater, pk=theater_id)
	upcoming = (
		Performance.objects.filter(theater=theater, starts_at__gte=timezone.now())
		.select_related("show")
		.order_by("starts_at")
	)
	admin_allowed = is_theater_admin(request.user, theater)
	return render(
		request,
		"theaters/theater_detail.html",
		{
			"theater": theater,
			"performances": upcoming,
			"admin_allowed": admin_allowed,
			"halls": theater.halls.all(),
		},
	)


@login_required
def management_dashboard(request):
	if not is_any_theater_admin(request.user):
		raise PermissionDenied
	if request.user.is_superuser:
		theaters = Theater.objects.all().order_by("name")
	else:
		theaters = Theater.objects.filter(admins__user=request.user).order_by("name")
	return render(request, "theaters/management_dashboard.html", {"theaters": theaters})


@login_required
def theater_create(request):
	if not request.user.is_superuser:
		raise PermissionDenied
	if request.method == "POST":
		form = TheaterForm(request.POST)
		if form.is_valid():
			theater = form.save()
			messages.success(request, "Teatro creato.")
			return redirect("theaters:detail", theater_id=theater.id)
	else:
		form = TheaterForm()
	return render(request, "theaters/theater_form.html", {"form": form})


@login_required
def theater_update(request, theater_id):
	if not request.user.is_superuser:
		raise PermissionDenied
	theater = get_object_or_404(Theater, pk=theater_id)
	if request.method == "POST":
		form = TheaterForm(request.POST, instance=theater)
		if form.is_valid():
			form.save()
			messages.success(request, "Teatro aggiornato.")
			return redirect("theaters:detail", theater_id=theater.id)
	else:
		form = TheaterForm(instance=theater)
	return render(request, "theaters/theater_form.html", {"form": form, "theater": theater})


@login_required
@require_POST
def theater_delete(request, theater_id):
	if not request.user.is_superuser:
		raise PermissionDenied
	theater = get_object_or_404(Theater, pk=theater_id)
	if theater.performances.exists():
		messages.error(request, "Non puoi eliminare un teatro con performance associate.")
		return redirect("theaters:detail", theater_id=theater.id)
	theater.delete()
	messages.success(request, "Teatro eliminato.")
	return redirect("theaters:management")


@login_required
def hall_create(request, theater_id):
	theater = get_object_or_404(Theater, pk=theater_id)
	if not is_theater_admin(request.user, theater):
		raise PermissionDenied
	if request.method == "POST":
		form = HallForm(request.POST)
		if form.is_valid():
			hall = form.save(commit=False)
			hall.theater = theater
			hall.save()
			messages.success(request, "Sala creata con posti generati.")
			return redirect("theaters:detail", theater_id=theater.id)
	else:
		form = HallForm()
	return render(request, "theaters/hall_form.html", {"form": form, "theater": theater})


@login_required
def hall_manage(request, theater_id, hall_id):
	theater = get_object_or_404(Theater, pk=theater_id)
	if not is_theater_admin(request.user, theater):
		raise PermissionDenied
	hall = get_object_or_404(Hall, pk=hall_id, theater=theater)
	if request.method == "POST":
		hall_form = HallForm(request.POST, instance=hall)
		zone_formset = HallZoneFormSet(request.POST, instance=hall)
		if hall_form.is_valid() and zone_formset.is_valid():
			hall_form.save()
			zone_formset.save()
			if request.POST.get("regenerate") == "1":
				has_bookings = hall.performances.filter(bookings__status=Booking.STATUS_CONFIRMED).exists()
				if has_bookings:
					messages.error(request, "Impossibile rigenerare: esistono prenotazioni confermate.")
				else:
					hall.regenerate_seats()
					messages.success(request, "Posti rigenerati con nuove zone.")
			messages.success(request, "Composizione sala aggiornata.")
			return redirect("theaters:hall_manage", theater_id=theater.id, hall_id=hall.id)
	else:
		hall_form = HallForm(instance=hall)
		zone_formset = HallZoneFormSet(instance=hall)
	return render(
		request,
		"theaters/hall_manage.html",
		{"hall": hall, "theater": theater, "hall_form": hall_form, "zone_formset": zone_formset},
	)


@login_required
@require_POST
def hall_delete(request, theater_id, hall_id):
	theater = get_object_or_404(Theater, pk=theater_id)
	if not is_theater_admin(request.user, theater):
		raise PermissionDenied
	hall = get_object_or_404(Hall, pk=hall_id, theater=theater)
	if hall.performances.exists():
		messages.error(request, "Non puoi eliminare una sala con performance associate.")
		return redirect("theaters:detail", theater_id=theater.id)
	hall.delete()
	messages.success(request, "Sala eliminata.")
	return redirect("theaters:detail", theater_id=theater.id)


@login_required
def theater_assign_admin(request, theater_id):
	theater = get_object_or_404(Theater, pk=theater_id)
	
	# Check permission: only superusers or theater managers can assign admins
	is_theater_manager = is_theater_admin(request.user, theater)
	is_superuser = request.user.is_superuser
	
	if not (is_superuser or is_theater_manager):
		raise PermissionDenied
	
	if request.method == "POST":
		form = TheaterAdminForm(request.POST)
		if form.is_valid():
			user = form.cleaned_data["user"]
			
			# Verify user is a manager
			if not (user.profile.role and user.profile.role.name == "manager"):
				messages.error(request, "Solo i gestori possono essere assegnati ai teatri.")
				return redirect("theaters:assign_admin", theater_id=theater.id)
			
			TheaterAdmin.objects.get_or_create(theater=theater, user=user)
			messages.success(request, f"Gestore {user.get_full_name or user.username} assegnato al teatro.")
			return redirect("theaters:detail", theater_id=theater.id)
	else:
		form = TheaterAdminForm()
	
	return render(request, "theaters/theater_admin_form.html", {"form": form, "theater": theater})
