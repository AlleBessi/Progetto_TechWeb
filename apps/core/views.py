from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.views.generic import TemplateView
from django_filters.views import FilterView
from django.utils import timezone

from apps.bookings.models import Booking
from apps.shows.models import Performance
from apps.theaters.models import Theater

from .filters import PerformanceFilter


def _recommended_performances(user, base_qs, limit=4):
	"""Personalised homepage suggestions, ranked by relevance.

	Recommends upcoming shows the user is likely to enjoy, scored (in priority
	order) by:
	  1. Personal affinity — how often the user has booked the show's category
	     and artist before (frequency-weighted, category above artist).
	  2. Global popularity — confirmed bookings for the show (trending signal),
	     used as a tie-breaker.
	  3. Soonest date, as the final tie-breaker.

	Shows the user has already booked are excluded. Returns [] when there is no
	personalisation signal (anonymous users, or users without booking history),
	so the section only appears when it is genuinely personalised — and stays
	distinct from the chronological "Prossime performance" list.

	Runs in a bounded number of queries (the user's history, one popularity
	aggregate) beyond the already-evaluated candidate list.
	"""
	if not user.is_authenticated:
		return []

	# Personal affinity signals, derived from the user's confirmed bookings.
	category_weights: dict[int, int] = {}
	artist_weights: dict[int, int] = {}
	booked_show_ids: set[int] = set()
	history = Booking.objects.filter(
		user=user, status=Booking.STATUS_CONFIRMED
	).values_list(
		"performance__show_id",
		"performance__show__category_id",
		"performance__show__artist_id",
	)
	for show_id, category_id, artist_id in history:
		booked_show_ids.add(show_id)
		category_weights[category_id] = category_weights.get(category_id, 0) + 1
		artist_weights[artist_id] = artist_weights.get(artist_id, 0) + 1

	if not booked_show_ids:
		return []  # no history → nothing to personalise on

	# Soonest upcoming performance per not-yet-booked show (base_qs is ordered by
	# starts_at), so a single show cannot fill every recommendation slot.
	perf_by_show: dict[int, Performance] = {}
	for performance in base_qs:
		if performance.show_id in booked_show_ids:
			continue  # don't recommend a show the user has already booked
		perf_by_show.setdefault(performance.show_id, performance)
	if not perf_by_show:
		return []

	candidate_show_ids = list(perf_by_show)

	# Global popularity: confirmed bookings per candidate show (one aggregate).
	popularity = dict(
		Booking.objects.filter(
			status=Booking.STATUS_CONFIRMED,
			performance__show__in=candidate_show_ids,
		)
		.values("performance__show")
		.annotate(n=Count("id"))
		.values_list("performance__show", "n")
	)

	scored = []
	for show_id, performance in perf_by_show.items():
		show = performance.show
		affinity = category_weights.get(show.category_id, 0) * 3 + artist_weights.get(show.artist_id, 0) * 2
		# Sort key: affinity first, then popularity, then soonest date. Using a
		# tuple guarantees affinity always dominates popularity regardless of scale.
		scored.append((affinity, popularity.get(show_id, 0), performance.starts_at, performance))

	scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
	return [performance for *_ignored, performance in scored[:limit]]


def _featured_theaters():
	return Theater.objects.order_by("name")[:5]


class HomeView(TemplateView):
	template_name = "core/home.html"

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		now = timezone.now()
		# Evaluate the upcoming performances once and reuse for both sections.
		upcoming = list(
			Performance.objects.filter(starts_at__gte=now, status=Performance.STATUS_SCHEDULED)
			.select_related("show", "show__artist", "auditorium__theater")
			.order_by("starts_at")
		)
		# Chronological list: keep only the soonest performance per show so the
		# same show is not shown several times.
		upcoming_by_show: dict[int, Performance] = {}
		for performance in upcoming:
			upcoming_by_show.setdefault(performance.show_id, performance)
		distinct_upcoming = list(upcoming_by_show.values())

		recommendations = _recommended_performances(self.request.user, upcoming)

		context.update(
			{
				"performances": distinct_upcoming[:4],
				"recommendations": recommendations,
				"featured_theaters": _featured_theaters(),
			}
		)
		return context


class SearchView(FilterView):
	template_name = "core/search.html"
	filterset_class = PerformanceFilter
	context_object_name = "performances"

	def get_queryset(self):
		return (
			Performance.objects.filter(status=Performance.STATUS_SCHEDULED, starts_at__gte=timezone.now())
			.select_related("show", "show__artist", "auditorium__theater")
		)
