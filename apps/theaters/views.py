from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
from django.views.generic.detail import SingleObjectMixin

from apps.bookings.models import BookingSeat
from apps.bookings.utils import build_zone_layout, calculate_occupancy, performance_rows
from braces.views import LoginRequiredMixin, SuperuserRequiredMixin

from apps.core.mixins import (
    ManagerAccessMixin,
    TheaterManagementContextMixin,
    TheaterManagerRequiredMixin,
    TheaterScopedMixin,
)
from apps.shows.models import Performance

from .forms import AuditoriumForm, AuditoriumZoneFormSet, TheaterAdminForm, TheaterForm
from .filters import BookingManagementFilter, PerformanceManagementFilter
from .models import Auditorium, Theater, TheaterAdmin
from .services import get_booking_management_queryset, get_performance_management_queryset


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------

class TheaterListView(ListView):
    model = Theater
    template_name = "theaters/theater_list.html"
    context_object_name = "theaters"
    ordering = ["name"]


class TheaterDetailView(DetailView):
    model = Theater
    template_name = "theaters/theater_detail.html"
    context_object_name = "theater"
    pk_url_kwarg = "theater_id"
    object: Theater

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        theater = self.object
        context["performances"] = (
            Performance.objects.filter(auditorium__theater=theater, starts_at__gte=timezone.now())
            .select_related("show", "show__artist", "auditorium")
            .order_by("starts_at")
        )
        context["auditoriums"] = Auditorium.objects.filter(theater=theater)
        return context


# ---------------------------------------------------------------------------
# Management — theater-level views
# ---------------------------------------------------------------------------

class ManagementDashboardView(TheaterManagerRequiredMixin, ListView):
    model = Theater
    template_name = "theaters/management_dashboard.html"
    context_object_name = "theaters"

    def get_queryset(self):
        return Theater.objects.accessible_by(self.request.user).order_by("name")
 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only superusers (admins) may create or delete theaters.
        context["can_create_delete"] = self.request.user.is_superuser
        return context


class TheaterManagementView(TheaterManagementContextMixin, TemplateView):
    template_name = "theaters/theater_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        theater = self.get_theater()
        booking_filter = BookingManagementFilter(
            self.request.GET or None,
            queryset=get_booking_management_queryset(theater),
        )
        performances = get_performance_management_queryset(theater)
        context.update({
            "auditoriums": Auditorium.objects.filter(theater=theater),
            "performances": performances,
            "bookings": booking_filter.qs,
            "performance_rows": performance_rows(performances),
        })
        return context


class TheaterManagementDataView(TheaterManagementContextMixin, TemplateView):
    template_name = "theaters/theater_management_data.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["auditoriums"] = Auditorium.objects.filter(theater=self.get_theater()).prefetch_related("zones", "seats")
        return context


class TheaterManagementProgrammazioneView(TheaterManagementContextMixin, TemplateView):
    template_name = "theaters/theater_management_programmazione.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        theater = self.get_theater()
        performance_filter = PerformanceManagementFilter(
            self.request.GET or None,
            queryset=get_performance_management_queryset(theater),
            theater=theater,
        )
        context["performances"] = performance_filter.qs
        context["filter"] = performance_filter
        return context


class TheaterManagementBookingsView(TheaterManagementContextMixin, TemplateView):
    template_name = "theaters/theater_management_bookings.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        theater = self.get_theater()
        booking_filter = BookingManagementFilter(
            self.request.GET or None,
            queryset=get_booking_management_queryset(theater),
        )
        context["bookings"] = booking_filter.qs
        context["filter"] = booking_filter
        return context


class TheaterManagementOccupazioneView(TheaterManagementContextMixin, TemplateView):
    template_name = "theaters/theater_management_occupazione.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        theater = self.get_theater()
        performance_filter = PerformanceManagementFilter(
            self.request.GET or None,
            queryset=get_performance_management_queryset(theater),
            theater=theater,
        )

        context.update({
            "performance_rows": performance_rows(performance_filter.qs),
            "filter": performance_filter,
        })
        return context


class TheaterOccupancyDetailView(TheaterManagementContextMixin, TemplateView):
    template_name = "theaters/theater_occupancy_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        performance = get_object_or_404(
            Performance,
            pk=self.kwargs["performance_id"],
            auditorium__theater=self.get_theater(),
        )
        reserved = set(
            BookingSeat.objects
            .for_performance(performance)
            .reserved_seat_ids()
        )
        zone_layout = build_zone_layout(performance, reserved)
        occupancy_data = calculate_occupancy(performance, zone_layout)

        context.update({
            "selected_performance": performance,
            "zone_layout": zone_layout,
            "occupancy_data": occupancy_data,
        })
        return context


class TheaterCreateView(LoginRequiredMixin, SuperuserRequiredMixin, CreateView):
    """Create a new theater. Restricted to superusers (admins)."""
    raise_exception = True
    model = Theater
    form_class = TheaterForm
    template_name = "theaters/theater_form.html"
    object: Theater

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Teatro creato.")
        return response
 
    def get_success_url(self):
        return reverse("theaters:management_detail", kwargs={"theater_id": self.object.pk})



class TheaterUpdateView(ManagerAccessMixin, UpdateView):
    model = Theater
    form_class = TheaterForm
    template_name = "theaters/theater_form.html"
    context_object_name = "theater"
    pk_url_kwarg = "theater_id"
    object: Theater

    def get_queryset(self):
        return Theater.objects.accessible_by(self.request.user)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Teatro aggiornato.")
        return response

    def get_success_url(self):
        return reverse("theaters:management_data", kwargs={"theater_id": self.object.pk})


class TheaterDeleteView(LoginRequiredMixin, SuperuserRequiredMixin, DeleteView):
    """Delete a theater. Restricted to superusers (admins)."""
    raise_exception = True
    model = Theater
    pk_url_kwarg = "theater_id"
    http_method_names = ["post"]
    success_url = reverse_lazy("theaters:management")

    def get_queryset(self):
        return Theater.objects.accessible_by(self.request.user)

    def post(self, request, *args, **kwargs):
        theater = self.get_object()
        if Performance.objects.filter(auditorium__theater=theater).exists():
            messages.error(request, "Non puoi eliminare un teatro con performance associate.")
            return redirect("theaters:management_detail", theater_id=theater.pk)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Teatro eliminato.")
        return response



# ---------------------------------------------------------------------------
# Management — admin assignment views
# ---------------------------------------------------------------------------

class TheaterAdminListView(TheaterManagementContextMixin, ListView):
    """List all managers assigned to the theater."""
 
    model = TheaterAdmin
    template_name = "theaters/theater_admin_list.html"
    context_object_name = "theater_admins"
 
    def get_queryset(self):
        return (
            TheaterAdmin.objects
            .filter(theater=self.get_theater())
            .select_related("user")
            .order_by("user__username")
        )


class TheaterAdminAddView(TheaterManagementContextMixin, CreateView):
    """Assign a new manager to the theater."""

    model = TheaterAdmin
    form_class = TheaterAdminForm
    template_name = "theaters/theater_admin_add.html"
    object: TheaterAdmin

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["theater"] = self.get_theater()
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object.user
        messages.success(
            self.request,
            f"Gestore {user.get_full_name() or user.username} assegnato al teatro.",
        )
        return response

    def get_success_url(self):
        return reverse("theaters:management_admins", kwargs={"theater_id": self.get_theater().pk})

 
class TheaterAdminRemoveView(TheaterScopedMixin, ManagerAccessMixin, DeleteView):
    """Remove a manager from the theater (POST only).

    The URL carries theater_id + user_id (not the TheaterAdmin pk), so the
    lookup is scoped to the theater and keyed on user_id via slug_field.
    """

    model = TheaterAdmin
    http_method_names = ["post"]
    slug_field = "user_id"
    slug_url_kwarg = "user_id"

    def get_queryset(self):
        return TheaterAdmin.objects.filter(theater=self.get_theater())

    def post(self, request, *args, **kwargs):
        if TheaterAdmin.objects.filter(theater=self.get_theater()).count() <= 1:
            messages.error(request, "Deve rimanere almeno un gestore assegnato al teatro.")
            return redirect("theaters:management_admins", theater_id=self.get_theater().pk)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Gestore rimosso dal teatro.")
        return response

    def get_success_url(self):
        if self.request.user.id == self.kwargs["user_id"]:
            messages.info(self.request, "Hai rimosso te stesso come gestore, stai tornando alla dashboard.")
            return reverse("theaters:management")
        return reverse("theaters:management_admins", kwargs={"theater_id": self.get_theater().pk})

 
# ---------------------------------------------------------------------------
# Management — auditorium views
# ---------------------------------------------------------------------------

class AuditoriumCreateView(TheaterScopedMixin, ManagerAccessMixin, CreateView):
    model = Auditorium
    form_class = AuditoriumForm
    template_name = "theaters/auditorium_form.html"
    object: Auditorium

    def form_valid(self, form):
        auditorium = form.save(commit=False)
        auditorium.theater = self.get_theater()
        auditorium.save()
        self.object = auditorium
        messages.success(self.request, "Sala creata.")
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["theater"] = self.get_theater()
        return context

    def get_success_url(self):
        return reverse("theaters:management_data", kwargs={"theater_id": self.get_theater().pk})


class AuditoriumManageView(TheaterScopedMixin, ManagerAccessMixin, SingleObjectMixin, TemplateView):
    """Edit an auditorium and its zones.

    Uses SingleObjectMixin so that get_object() / get_queryset() handle
    lookup and scoping — no manual get_object_or_404 needed.
    """

    template_name = "theaters/auditorium_manage.html"
    model = Auditorium
    pk_url_kwarg = "auditorium_id"

    def get_queryset(self):
        # Scope the lookup to auditoriums belonging to the current theater.
        return Auditorium.objects.filter(theater=self.get_theater())

    def _build_context(self, auditorium, auditorium_form, zone_formset):
        return {
            "auditorium": auditorium,
            "theater": self.get_theater(),
            "auditorium_form": auditorium_form,
            "zone_formset": zone_formset,
            "has_bookings": Performance.objects.filter(
                auditorium=auditorium,
                bookings__isnull=False,
            ).exists(),
        }

    def get(self, request, *args, **kwargs):
        auditorium = self.get_object()
        return self.render_to_response(
            self._build_context(
                auditorium,
                AuditoriumForm(instance=auditorium),
                AuditoriumZoneFormSet(instance=auditorium),
            )
        )

    def post(self, request, *args, **kwargs):
        auditorium = self.get_object()
        has_bookings = Performance.objects.filter(auditorium=auditorium, bookings__isnull=False).exists()
        auditorium_form = AuditoriumForm(request.POST, instance=auditorium)
        zone_formset = AuditoriumZoneFormSet(request.POST, instance=auditorium)

        if auditorium_form.is_valid() and zone_formset.is_valid():
            zone_changes = zone_formset.has_changed()
            auditorium_form.save()
            if zone_changes and has_bookings:
                messages.error(request, "Non puoi modificare le zone di una sala che ha già prenotazioni.")
            else:
                zone_formset.save()
                if zone_changes:
                    auditorium.regenerate_seats()
                    messages.success(request, "Zone aggiornate e posti rigenerati automaticamente.")
                else:
                    messages.success(request, "Dati sala aggiornati.")
            return redirect(
                "theaters:management_data",
                theater_id=self.get_theater().pk
            )
        return self.render_to_response(
            self._build_context(auditorium, auditorium_form, zone_formset)
        )


class AuditoriumDeleteView(TheaterScopedMixin, ManagerAccessMixin, DeleteView):
    model = Auditorium
    pk_url_kwarg = "auditorium_id"
    http_method_names = ["post"]

    def get_queryset(self):
        return Auditorium.objects.filter(theater=self.get_theater())

    def post(self, request, *args, **kwargs):
        if Performance.objects.filter(auditorium=self.get_object()).exists():
            messages.error(request, "Non puoi eliminare una sala con performance associate.")
            return redirect("theaters:management_data", theater_id=self.get_theater().pk)
        return super().post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse("theaters:management_data", kwargs={"theater_id": self.get_theater().pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Sala eliminata.")
        return response