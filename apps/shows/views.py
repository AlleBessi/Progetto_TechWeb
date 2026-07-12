from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, DetailView

from apps.core.mixins import (
    ArtistRequiredMixin,
    ManagerAccessMixin,
)
from apps.theaters.models import Auditorium, Theater

from .forms import PerformanceForm, ShowForm
from .models import Performance, Show


class ShowList(ListView):
	model = Show
	template_name = "shows/show_list.html"
	context_object_name = "shows"

	def get_queryset(self):
		return Show.objects.select_related("category", "artist")


class ShowDetail(UserPassesTestMixin, DetailView):
	model = Show
	template_name = "shows/show_detail.html"
	context_object_name = "show"
	pk_url_kwarg = "show_id"
	raise_exception = True

	def get_queryset(self):
		return Show.objects.select_related("category", "artist")

	def test_func(self):
		return True

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["performances"] = (
			self.object.performances
			.filter(starts_at__gte=timezone.now(), status=Performance.STATUS_SCHEDULED)
			.select_related("auditorium__theater")
			.order_by("starts_at")
		)
		return context


class ShowCreate(ArtistRequiredMixin, CreateView):
	form_class = ShowForm
	template_name = "shows/show_form.html"

	def form_valid(self, form):
		show = form.save(commit=False)
		show.artist = self.request.user
		show.save()
		messages.success(self.request, "Spettacolo creato.")
		return redirect("shows:artist_shows_dashboard")


class ShowUpdate(ArtistRequiredMixin, UpdateView):
	form_class = ShowForm
	template_name = "shows/show_form.html"
	pk_url_kwarg = "show_id"

	def get_initial(self):
		show = self.get_object()
		return {
			"title": show.title,
			"description": show.description,
			"category": show.category,
			"duration_minutes": show.duration_minutes,
			"poster": show.poster,
			"cover": show.cover,
		}

	def get_queryset(self):
		return Show.objects.owned_by(self.request.user)

	def form_valid(self, form):
		response = super().form_valid(form)
		messages.success(self.request, "Spettacolo aggiornato.")
		return response

	def get_success_url(self):
		return reverse("shows:artist_shows_dashboard")


class ShowDelete(ArtistRequiredMixin, DeleteView):
	model = Show
	pk_url_kwarg = "show_id"
	http_method_names = ["post"]
	success_url = reverse_lazy("shows:artist_shows_dashboard")

	def get_queryset(self):
		return Show.objects.owned_by(self.request.user)

	def post(self, request, *args, **kwargs):
		if self.get_object().performances.exists():
			messages.error(request, "Non puoi eliminare uno spettacolo gia programmato.")
			return redirect("shows:artist_shows_dashboard")
		return super().post(request, *args, **kwargs)

	def form_valid(self, form):
		response = super().form_valid(form)
		messages.success(self.request, "Spettacolo eliminato.")
		return response


class ArtistShowsDashboardView(ArtistRequiredMixin, ListView):
	model = Show
	template_name = "shows/artist_dashboard.html"
	context_object_name = "shows"

	def get_queryset(self):
		return Show.objects.owned_by(self.request.user).select_related("category")


class ArtistPerformanceDashboardView(ArtistRequiredMixin, ListView):
	model = Performance
	template_name = "shows/artist_performance_dashboard.html"
	context_object_name = "pending_performances"

	def get_queryset(self):
		return (
			Performance.objects.owned_by(self.request.user)
			.filter(status=Performance.STATUS_PENDING_ARTIST_CONFIRMATION)
			.select_related("show", "show__artist", "auditorium__theater")
		)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context["all_performances"] = (
			Performance.objects.owned_by(self.request.user)
			.select_related("show", "show__artist", "auditorium__theater")
		)
		return context


class PerformanceConfirmView(ArtistRequiredMixin, View):
	action = "confirm"

	def get_performance(self):
		if not hasattr(self, "performance"):
			self.performance = get_object_or_404(
				Performance.objects.select_related("show", "show__artist", "auditorium__theater"),
				pk=self.kwargs["performance_id"],
			)
		return self.performance

	def dispatch(self, request, *args, **kwargs):
		if not request.user.is_authenticated:
			# Let ArtistRequiredMixin handle the anonymous case (login redirect)
			# rather than comparing ownership against AnonymousUser.
			return super().dispatch(request, *args, **kwargs)
		performance = self.get_performance()
		if not request.user.is_superuser and performance.show.artist_id != request.user.id:
			raise PermissionDenied
		if request.method.lower() != "post":
			return redirect("shows:artist_performances_dashboard")
		return super().dispatch(request, *args, **kwargs)

	def post(self, request, *args, **kwargs):
		performance = self.get_performance()
		if self.action == "confirm":
			performance.status = Performance.STATUS_SCHEDULED
			performance.confirmed_by_artist = True
			performance.confirmed_by_artist_at = timezone.now()
			message = "Performance confermata per la programmazione."
		else:
			performance.status = Performance.STATUS_CANCELLED
			performance.confirmed_by_artist = False
			performance.confirmed_by_artist_at = None
			message = "Performance rifiutata."
		performance.save(update_fields=["status", "confirmed_by_artist", "confirmed_by_artist_at"])
		messages.success(request, message)
		return redirect("shows:artist_performances_dashboard")


class PerformanceFormBase(ManagerAccessMixin):
	model = Performance
	form_class = PerformanceForm
	template_name = "shows/performance_form.html"
	pk_url_kwarg = "performance_id"
	raise_exception = True

	def get_performance(self) -> Performance | None:
		return None

	def get_selected_auditorium(self) -> Auditorium | None:
		return None

	def get_form_kwargs(self):
		kwargs = super().get_form_kwargs()
		kwargs["theater"] = self.get_theater()
		auditorium = self.get_selected_auditorium()
		if auditorium is not None:
			kwargs["selected_auditorium"] = auditorium
		return kwargs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		form: PerformanceForm = context["form"]
		context["theater"] = self.get_theater()
		context["performance"] = self.get_performance()
		context["price_fields"] = [
			(getattr(form.zone_by_field.get(name), "zone", form.fields[name].label), form[name])
			for legend, field_names in form.fieldsets
			if legend == "Prezzi per zona"
			for name in field_names
		]
		return context

	def form_invalid(self, form: PerformanceForm):
		if form.no_zones:
			messages.error(self.request, "Configura prima le zone della sala.")
		return super().form_invalid(form)

	def save_zone_prices(self, performance, form: PerformanceForm):
		"""Parse the form's per-zone price fields and persist them on the model."""
		grouped = {
			legend: {name: form.cleaned_data[name] for name in field_names}
			for legend, field_names in form.fieldsets
		}
		price_by_zone = {
			form.zone_by_field.get(name): value
			for name, value in grouped.get("Prezzi per zona", {}).items()
		}
		performance.set_zone_prices(price_by_zone)


class PerformanceCreate(PerformanceFormBase, CreateView):

	def get_theater(self):
		return get_object_or_404(Theater, pk=self.kwargs["theater_id"])

	def get_selected_auditorium(self):
		auditorium_id = self.request.POST.get("auditorium")
		if not auditorium_id:
			return None
		return get_object_or_404(Auditorium, pk=auditorium_id, theater=self.get_theater())

	def form_valid(self, form):
		if form.no_zones:
			return self.form_invalid(form)

		with transaction.atomic():
			performance = form.save(commit=False)
			performance.created_by = self.request.user
			performance.status = Performance.STATUS_PENDING_ARTIST_CONFIRMATION
			performance.confirmed_by_artist = False
			performance.confirmed_by_artist_at = None
			performance.save()
			self.save_zone_prices(performance, form)

		self.object = performance
		messages.success(self.request, "Performance creata con successo.")
		return redirect(self.get_success_url())


	def get_success_url(self):
		return reverse("theaters:management_schedule", kwargs={"theater_id": self.object.auditorium.theater_id})


class PerformanceUpdate(PerformanceFormBase, UpdateView):
	object: Performance

	def get_theater(self):
		return self.get_performance().auditorium.theater

	def get_queryset(self):
		return Performance.objects.select_related("show", "auditorium__theater", "auditorium")

	@cached_property
	def performance(self) -> Performance:
		return self.get_object()

	def get_performance(self) -> Performance:
		return self.performance

	def get_selected_auditorium(self):
		performance = self.get_performance()
		auditorium_id = self.request.POST.get("auditorium") or performance.auditorium_id
		if not auditorium_id:
			return None
		return get_object_or_404(Auditorium, pk=auditorium_id, theater=performance.auditorium.theater)

	def dispatch(self, request, *args, **kwargs):
		performance = self.get_performance()
		if not performance.is_modifiable:
			messages.error(request, "Questa performance è stata annullata e non può essere modificata.")
			return redirect("theaters:management_schedule", theater_id=performance.auditorium.theater_id)
		return super().dispatch(request, *args, **kwargs)

	def form_valid(self, form):
		if form.no_zones:
			return self.form_invalid(form)

		with transaction.atomic():
			performance = form.save(commit=False)
			performance.created_by = self.request.user
			performance.save()
			self.save_zone_prices(performance, form)

		self.object = performance
		messages.success(self.request, "Performance aggiornata con successo.")
		return redirect(self.get_success_url())

	def get_success_url(self):
		return reverse("theaters:management_schedule", kwargs={"theater_id": self.object.auditorium.theater_id})



class PerformanceDeleteView(ManagerAccessMixin, DeleteView):
	model = Performance
	pk_url_kwarg = "performance_id"
	http_method_names = ["post"]

	def get_queryset(self):
		return Performance.objects.select_related("auditorium__theater")

	@cached_property
	def performance(self) -> Performance:
		return super().get_object()

	def get_object(self, queryset=None) -> Performance:
		return self.performance

	def get_theater(self):
		return self.performance.auditorium.theater

	def post(self, request, *args, **kwargs):
		if self.performance.bookings.exists():
			messages.error(request, "Non puoi eliminare una performance con prenotazioni.")
			return redirect("theaters:management_schedule", theater_id=self.performance.auditorium.theater_id)
		return super().post(request, *args, **kwargs)

	def get_success_url(self):
		return reverse("theaters:management_schedule", kwargs={"theater_id": self.performance.auditorium.theater_id})

	def form_valid(self, form):
		response = super().form_valid(form)
		messages.success(self.request, "Performance eliminata.")
		return response
