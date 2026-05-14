import math

from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from apps.bookings.models import Booking
from apps.shows.models import Performance
from apps.theaters.models import Theater

from .forms import SearchForm


def _haversine_km(lat1, lon1, lat2, lon2):
	radius = 6371
	lat1_rad = math.radians(lat1)
	lon1_rad = math.radians(lon1)
	lat2_rad = math.radians(lat2)
	lon2_rad = math.radians(lon2)
	dlat = lat2_rad - lat1_rad
	dlon = lon2_rad - lon1_rad
	a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
	c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
	return radius * c


def _recommended_performances(user, base_qs):
	if not user.is_authenticated:
		return base_qs.none()

	interests = list(user.profile.interests.all())
	if interests:
		qs = base_qs.filter(show__category__in=interests)
	else:
		booked_categories = (
			Booking.objects.filter(user=user, status=Booking.STATUS_CONFIRMED)
			.values_list("performance__show__category", flat=True)
			.distinct()
		)
		qs = base_qs.filter(show__category__in=booked_categories)

	qs = qs.exclude(bookings__user=user)
	return qs.distinct()[:6]


def _nearby_theaters(user):
	if not user.is_authenticated:
		return []
	profile = user.profile
	if profile.latitude is None or profile.longitude is None:
		return []
	theaters = Theater.objects.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
	with_distance = []
	for theater in theaters:
		distance = _haversine_km(
			float(profile.latitude),
			float(profile.longitude),
			float(theater.latitude),
			float(theater.longitude),
		)
		with_distance.append((distance, theater))
	with_distance.sort(key=lambda item: item[0])
	return with_distance[:5]


def home(request):
	now = timezone.now()
	upcoming = (
		Performance.objects.filter(starts_at__gte=now, status=Performance.STATUS_SCHEDULED)
		.select_related("show", "theater")
		.order_by("starts_at")
	)
	recommendations = _recommended_performances(request.user, upcoming)
	nearby = _nearby_theaters(request.user)

	return render(
		request,
		"core/home.html",
		{
			"performances": upcoming[:12],
			"recommendations": recommendations,
			"nearby": nearby,
		},
	)


def search(request):
	form = SearchForm(request.GET or None)
	qs = Performance.objects.filter(
		status=Performance.STATUS_SCHEDULED,
		starts_at__gte=timezone.now(),
	).select_related("show", "theater")
	if form.is_valid():
		q = form.cleaned_data.get("q")
		category = form.cleaned_data.get("category")
		city = form.cleaned_data.get("city")
		date_from = form.cleaned_data.get("date_from")
		date_to = form.cleaned_data.get("date_to")

		if q:
			qs = qs.filter(Q(show__title__icontains=q) | Q(show__description__icontains=q) | Q(theater__name__icontains=q))
		if category:
			qs = qs.filter(show__category=category)
		if city:
			qs = qs.filter(theater__city__icontains=city)
		if date_from:
			qs = qs.filter(starts_at__date__gte=date_from)
		if date_to:
			qs = qs.filter(starts_at__date__lte=date_to)

	return render(request, "core/search.html", {"form": form, "performances": qs})
