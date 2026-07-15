from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.views.generic import TemplateView
from django_filters.views import FilterView
from django.utils import timezone

from apps.bookings.models import Booking
from apps.shows.models import Performance

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

	# Build the personal affinity signals from the user's whole booking history
	# in a single query. Each past booking increments the weight of its show's
	# category and artist, so a taste booked more often counts proportionally
	# more. booked_show_ids is collected in the same pass to later exclude shows
	# the user has already seen.
	category_weights: dict[int, int] = {}
	artist_weights: dict[int, int] = {}
	booked_show_ids: set[int] = set()
	history = Booking.objects.filter(user=user).values_list(
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

	# Pick one performance per candidate show: the soonest upcoming one. base_qs
	# is already ordered by starts_at, so the first performance seen for a show is
	# its earliest, and setdefault keeps it (later, farther-off dates are ignored).
	# Collapsing to one performance per show stops a single show with many dates
	# from filling every recommendation slot. Shows already booked are skipped so
	# we only ever suggest something new.
	perf_by_show: dict[int, Performance] = {}
	for performance in base_qs:
		if performance.show_id in booked_show_ids:
			continue  # don't recommend a show the user has already booked
		perf_by_show.setdefault(performance.show_id, performance)
	if not perf_by_show:
		return []

	candidate_show_ids = list(perf_by_show)

	# Global popularity: total bookings per candidate show, computed in one
	# aggregate query. Used only as a "trending" tie-breaker when two shows have
	# the same personal affinity — it never overrides the user's own taste.
	popularity = dict(
		Booking.objects.filter(
			performance__show__in=candidate_show_ids,
		)
		.values("performance__show")
		.annotate(n=Count("id"))
		.values_list("performance__show", "n")
	)

	scored = []
	for show_id, performance in perf_by_show.items():
		show = performance.show
		# Affinity score: category matches weigh more than artist matches (3 vs 2),
		# because genre is the stronger predictor of taste than a single artist.
		affinity = category_weights.get(show.category_id, 0) * 3 + artist_weights.get(show.artist_id, 0) * 2
		# Pack the ranking criteria into a tuple in priority order: affinity,
		# then popularity, then soonest date. Comparing tuples makes affinity
		# dominate popularity outright — no weighting/normalisation needed, so a
		# very popular show can never outrank one that better matches the user.
		scored.append((affinity, popularity.get(show_id, 0), performance.starts_at, performance))

	# Sort by the tuple: affinity and popularity descending (hence the minus),
	# starts_at ascending (soonest first). The trailing Performance is not part
	# of the key — it just rides along and is unpacked out at the end.
	scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
	return [performance for *_ignored, performance in scored[:limit]]


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
