from braces.views import GroupRequiredMixin, LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, DetailView
from typing import cast

from apps.core.mixins import ManagerAccessMixin
from apps.theaters.models import Auditorium, Theater

from .forms import PerformanceForm, ShowForm
from .models import Performance, PerformancePrice, Show


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


class ShowCreate(LoginRequiredMixin, GroupRequiredMixin, CreateView):
	form_class = ShowForm
	template_name = "shows/show_form.html"
	group_required = ("artist", "admin")
	raise_exception = True

	def form_valid(self, form):
		show = form.save(commit=False)
		show.artist = self.request.user
		show.save()
		messages.success(self.request, "Spettacolo creato.")
		return redirect("shows:artist_shows_dashboard")


class ShowUpdate(LoginRequiredMixin, GroupRequiredMixin, UpdateView):
	form_class = ShowForm
	template_name = "shows/show_form.html"
	pk_url_kwarg = "show_id"
	group_required = ("artist", "admin")
	raise_exception = True

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
		qs = Show.objects.all()
		if self.request.user.is_superuser or self.request.user.groups.filter(name="admin").exists():
			return qs
		return qs.filter(artist=self.request.user)

	def form_valid(self, form):
		response = super().form_valid(form)
		messages.success(self.request, "Spettacolo aggiornato.")
		return response

	def get_success_url(self):
		return reverse("shows:artist_shows_dashboard")


class ShowDelete(LoginRequiredMixin, GroupRequiredMixin, View):
	group_required = ("artist", "admin")
	raise_exception = True

	def post(self, request, show_id):
		show = get_object_or_404(Show, pk=show_id)
		if not (request.user.is_superuser or request.user.groups.filter(name="admin").exists()) and show.artist_id != request.user.id:
			raise PermissionDenied
		if show.performances.exists():
			messages.error(request, "Non puoi eliminare uno spettacolo gia programmato.")
			return redirect("shows:artist_shows_dashboard")
		show.delete()
		messages.success(request, "Spettacolo eliminato.")
		return redirect("shows:artist_shows_dashboard")


class ArtistShowsDashboardView(LoginRequiredMixin, GroupRequiredMixin, ListView):
	model = Show
	template_name = "shows/artist_dashboard.html"
	context_object_name = "shows"
	group_required = ("artist", "admin")
	raise_exception = True

	def get_queryset(self):
		qs = Show.objects.select_related("category")
		if self.request.user.is_superuser or self.request.user.groups.filter(name="admin").exists():
			return qs
		return qs.filter(artist=self.request.user)


class ArtistPerformanceDashboardView(LoginRequiredMixin, GroupRequiredMixin, ListView):
	model = Performance
	template_name = "shows/artist_performance_dashboard.html"
	context_object_name = "pending_performances"
	group_required = ("artist", "admin")
	raise_exception = True

	def get_queryset(self):
		pending_qs = Performance.objects.filter(status=Performance.STATUS_PENDING_ARTIST_CONFIRMATION).select_related(
			"show", "show__artist", "auditorium__theater"
		)
		if not (self.request.user.is_superuser or self.request.user.groups.filter(name="admin").exists()):
			pending_qs = pending_qs.filter(show__artist=self.request.user)
		return pending_qs

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		all_qs = Performance.objects.select_related("show", "show__artist", "auditorium__theater")
		if not (self.request.user.is_superuser or self.request.user.groups.filter(name="admin").exists()):
			all_qs = all_qs.filter(show__artist=self.request.user)
		context["all_performances"] = all_qs
		return context


class PerformanceConfirmView(LoginRequiredMixin, GroupRequiredMixin, View):
	group_required = ("artist", "admin")
	raise_exception = True
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
			return super().dispatch(request, *args, **kwargs)
		performance = self.get_performance()
		user = request.user
		is_admin = user.is_superuser or user.groups.filter(name="admin").exists()
		if not is_admin and performance.show.artist_id != user.id:
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
		if form.no_zones:
			messages.error(self.request, "Configura prima le zone della sala.")
		return context


	def form_invalid(self, form: PerformanceForm):
		if form.no_zones:
			messages.error(self.request, "Configura prima le zone della sala.")
		return super().form_invalid(form)

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
			selected_zone_ids: set[int] = set()
			grouped = {
				legend: {name: form.cleaned_data[name] for name in field_names}
				for legend, field_names in form.fieldsets
			}
			for name, value in grouped.get("Prezzi per zona", {}).items():
				zone = form.zone_by_field.get(name)
				if zone is None:
					continue
				PerformancePrice.objects.update_or_create(
					performance=performance,
					auditorium_zone=zone,
					defaults={"price": value},
				)
				selected_zone_ids.add(zone.pk)
			performance.zone_prices.exclude(auditorium_zone_id__in=selected_zone_ids).delete()

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

	def get_performance(self):
		if not hasattr(self, "performance"):
			self.performance = get_object_or_404(
				Performance.objects.select_related("auditorium__theater"),
				pk=self.kwargs["performance_id"],
			)
		return self.performance

	def get_selected_auditorium(self):
		performance = self.get_performance()
		auditorium_id = self.request.POST.get("auditorium") or performance.auditorium_id
		if not auditorium_id:
			return None
		return get_object_or_404(Auditorium, pk=auditorium_id, theater=performance.auditorium.theater)

	def dispatch(self, request, *args, **kwargs):
		performance = self.get_performance()
		if performance.status == Performance.STATUS_CANCELLED:
			messages.error(request, "Questa performance è stata annullata e non può essere modificata.")
			return redirect(
				reverse("theaters:management_schedule", kwargs={"theater_id": performance.auditorium.theater_id})
            )
		return super().dispatch(request, *args, **kwargs)
	
	def form_valid(self, form):
		if form.no_zones:
			return self.form_invalid(form)

		with transaction.atomic():
			performance = form.save(commit=False)
			performance.created_by = self.request.user
			performance.save()
			selected_zone_ids: set[int] = set()
			grouped = {
				legend: {name: form.cleaned_data[name] for name in field_names}
				for legend, field_names in form.fieldsets
			}
			for name, value in grouped.get("Prezzi per zona", {}).items():
				zone = form.zone_by_field.get(name)
				if zone is None:
					continue
				PerformancePrice.objects.update_or_create(
					performance=performance,
					auditorium_zone=zone,
					defaults={"price": value},
				)
				selected_zone_ids.add(zone.pk)
			performance.zone_prices.exclude(auditorium_zone_id__in=selected_zone_ids).delete()

		self.object = performance
		messages.success(self.request, "Performance aggiornata con successo.")
		return redirect(self.get_success_url())

	def get_success_url(self):
		return reverse("theaters:management_schedule", kwargs={"theater_id": self.object.auditorium.theater_id})



class PerformanceDeleteView(ManagerAccessMixin, DeleteView):
	performance: Performance

	def get_theater(self):
		return self.get_performance().auditorium.theater

	def get_performance(self):
		if not hasattr(self, "performance"):
			self.performance = get_object_or_404(
				Performance.objects.select_related("auditorium__theater"),
				pk=self.kwargs["performance_id"],
			)
		return self.performance

	def post(self, request, performance_id):
		performance = self.get_performance()
		if getattr(performance, "bookings").exists():
			messages.error(request, "Non puoi eliminare una performance con prenotazioni.")
		else:
			theater_id = performance.auditorium.theater_id
			performance.delete()
			messages.success(request, "Performance eliminata.")
			return redirect("theaters:management_schedule", theater_id=theater_id)
		return redirect("theaters:management_schedule", theater_id=performance.auditorium.theater_id)
