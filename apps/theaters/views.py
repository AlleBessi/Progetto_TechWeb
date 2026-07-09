from decimal import Decimal
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from typing import Any
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView
from django.views.generic.detail import SingleObjectMixin
from braces.views import GroupRequiredMixin, LoginRequiredMixin

from apps.bookings.models import Booking, BookingSeat
from apps.bookings.forms import BookingForm
from apps.bookings.utils import build_zone_layout, calculate_occupancy, performance_rows
from apps.core.mixins import ManagerAccessMixin
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


class TheaterScopedMixin:
    request: Any
    kwargs: dict[str, Any]

    def get_theater(self) -> Theater:
        if not hasattr(self, "_theater_cache"):
            theater_id = self.kwargs.get("theater_id")
            if theater_id is None:
                raise AttributeError("theater_id is required for this view")
            self._theater_cache = get_object_or_404(Theater, pk=theater_id)
        return self._theater_cache

    def get_theater_queryset(self):
        return Theater.objects.accessible_by(self.request.user)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Management — shared context mixin
# ---------------------------------------------------------------------------

class TheaterManagementContextMixin(TheaterScopedMixin, ManagerAccessMixin):
    """Injects ``theater`` and ``admin_allowed`` into every management view."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore[attr-defined]
        context.setdefault("theater", self.get_theater())
        context.setdefault("admin_allowed", True)
        return context


# ---------------------------------------------------------------------------
# Management — theater-level views
# ---------------------------------------------------------------------------

class ManagementDashboardView(LoginRequiredMixin, ListView):
    model = Theater
    template_name = "theaters/management_dashboard.html"
    context_object_name = "theaters"
 
    def _user_is_privileged(self):
        user = self.request.user
        return (
            user.is_superuser
            or user.groups.filter(name__in=["admin", "manager"]).exists()
        )
 
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not self._user_is_privileged():
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        return super().dispatch(request, *args, **kwargs)
 
    def get_queryset(self):
        return Theater.objects.accessible_by(self.request.user).order_by("name")
 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        # Only admins / superusers may create or delete theaters.
        context["can_create_delete"] = (
            user.is_superuser
            or user.groups.filter(name="admin").exists()
        )
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
    """List-only view: the filtered performances with their occupancy summary.

    Selecting a performance opens the full-page detail (TheaterOccupancyDetailView).
    """
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
    """Full-page occupancy cruscotto for a single performance."""
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
            .confirmed()
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


class TheaterCreateView(LoginRequiredMixin, GroupRequiredMixin, TheaterScopedMixin, CreateView):
    """Create a new theater. Restricted to the 'admin' group and superusers."""
    group_required = ["admin"]
    model = Theater
    form_class = TheaterForm
    template_name = "theaters/theater_form.html"
    object: Theater
    raise_exception = True
 
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Teatro creato.")
        return response
 
    def get_success_url(self):
        return reverse("theaters:management_detail", kwargs={"theater_id": self.object.pk})



class TheaterUpdateView(TheaterScopedMixin, ManagerAccessMixin, UpdateView):
    model = Theater
    form_class = TheaterForm
    template_name = "theaters/theater_form.html"
    context_object_name = "theater"
    pk_url_kwarg = "theater_id"
    object: Theater

    def get_queryset(self):
        return self.get_theater_queryset()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Teatro aggiornato.")
        return response

    def get_success_url(self):
        return reverse("theaters:management_data", kwargs={"theater_id": self.object.pk})


class TheaterDeleteView(GroupRequiredMixin, TheaterScopedMixin, SingleObjectMixin, View):
    """Delete a theater. Restricted to the 'admin' group and superusers."""
    group_required = ["admin"]
    model = Theater
    pk_url_kwarg = "theater_id"
    object: Theater
    raise_exception = True
 
    def get_queryset(self):
        return self.get_theater_queryset()
 
    def get_object(self, queryset=None) -> Theater:
        self.object = super().get_object(queryset)
        return self.object
 
    def post(self, request, *args, **kwargs):
        theater = self.get_object()
        if Performance.objects.filter(auditorium__theater=theater).exists():
            messages.error(request, "Non puoi eliminare un teatro con performance associate.")
            return redirect("theaters:management_detail", theater_id=theater.pk)
        theater.delete()
        messages.success(request, "Teatro eliminato.")
        return redirect("theaters:management")



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
 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

 
class TheaterAdminAddView(TheaterManagementContextMixin, FormView):
    """Form to select and assign a new manager to the theater.
 
    Uses FormView instead of CreateView because TheaterAdminForm is a plain
    forms.Form (not a ModelForm).
    """
 
    template_name = "theaters/theater_admin_add.html"
    form_class = TheaterAdminForm
 
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["theater"] = self.get_theater()
        return kwargs
 
    def form_valid(self, form):
        theater = self.get_theater()
        user = form.cleaned_data["user"]
        TheaterAdmin.objects.get_or_create(theater=theater, user=user)
        messages.success(
            self.request,
            f"Gestore {user.get_full_name() or user.username} assegnato al teatro.",
        )
        return redirect("theaters:management_admins", theater_id=theater.pk)

 
class TheaterAdminRemoveView(TheaterScopedMixin, ManagerAccessMixin, View):
    """Remove a manager from the theater (POST only).
 
    Uses a plain View instead of DeleteView because the URL carries user_id
    (a FK), not the TheaterAdmin pk.
    """
 
    def post(self, request, theater_id, user_id):
        theater = self.get_theater()
        if TheaterAdmin.objects.filter(theater=theater).count() <= 1:
            messages.error(request, "Deve rimanere almeno un gestore assegnato al teatro.")
            return redirect("theaters:management_admins", theater_id=theater.pk)
        TheaterAdmin.objects.filter(theater=theater, user_id=user_id).delete()
        messages.success(request, "Gestore rimosso dal teatro.")
        if request.user.id == user_id:
            messages.info(request, "Hai rimosso te stesso come gestore, stai tornando alla dashboard.")
            return redirect("theaters:management")
        return redirect("theaters:management_admins", theater_id=theater.pk)

 
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

    def get_object(self, queryset=None) -> Auditorium:
        self.object = super().get_object(queryset)
        return self.object

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


class AuditoriumDeleteView(TheaterScopedMixin, ManagerAccessMixin, SingleObjectMixin, View):
    model = Auditorium
    pk_url_kwarg = "auditorium_id"

    def get_object(self, queryset=None) -> Auditorium:
        self.object = super().get_object(queryset)
        return self.object

    def get_queryset(self):
        return Auditorium.objects.filter(theater=self.get_theater())

    def post(self, request, *args, **kwargs):
        auditorium = self.get_object()
        theater = self.get_theater()
        
        if Performance.objects.filter(auditorium=auditorium).exists():
            messages.error(request, "Non puoi eliminare una sala con performance associate.")
            return redirect("theaters:management_data", theater_id=theater.pk)
        auditorium.delete()
        messages.success(request, "Sala eliminata.")
        return redirect("theaters:management_data", theater_id=theater.pk)


# ---------------------------------------------------------------------------
# Management — booking views
# ---------------------------------------------------------------------------

class BookingCancelView(TheaterScopedMixin, ManagerAccessMixin, SingleObjectMixin, View):
    """Cancel a booking scoped to the current theater."""

    model = Booking
    pk_url_kwarg = "booking_id"

    def get_object(self, queryset=None) -> Booking:
        self.object = super().get_object(queryset)
        return self.object

    def get_queryset(self):
        return Booking.objects.filter(performance__auditorium__theater=self.get_theater())

    def post(self, request, *args, **kwargs):
        booking = self.get_object()
        if booking.status != Booking.STATUS_CANCELLED:
            booking.status = Booking.STATUS_CANCELLED
            booking.save(update_fields=["status"])
            messages.success(request, "Prenotazione annullata dalla gestione teatro.")
        return redirect("theaters:management_bookings", theater_id=self.get_theater().pk)


class BookingUpdateManagerView(TheaterScopedMixin, ManagerAccessMixin, SingleObjectMixin, FormView):
    """Update a booking's seats on behalf of a manager.

    SingleObjectMixin provides get_object() / get_queryset() for the Booking
    lookup, automatically scoped to the current theater via get_queryset().
    self.object is set once in dispatch and reused everywhere — no manual
    caching needed.
    """

    template_name = "bookings/booking_update_manager.html"
    model = Booking
    pk_url_kwarg = "booking_id"
    object: Booking

    def get_object(self, queryset=None) -> Booking:
        self.object = super().get_object(queryset)
        return self.object

    def get_queryset(self):
        return (
            Booking.objects.filter(performance__auditorium__theater=self.get_theater())
            .select_related("performance__auditorium", "performance__show")
        )

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status == Booking.STATUS_CANCELLED:
            messages.error(request, "Prenotazione annullata, non modificabile.")
            return redirect("theaters:management_bookings", theater_id=self.get_theater().pk)
        if self.object.performance.status != Performance.STATUS_SCHEDULED or self.object.performance.starts_at < timezone.now():
            messages.error(request, "Performance non disponibile per la modifica.")
            return redirect("theaters:management_bookings", theater_id=self.get_theater().pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        return BookingForm(self.object.performance, **self.get_form_kwargs())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["exclude_booking"] = self.object
        if self.request.method not in ("POST", "PUT"):
            kwargs.pop("data", None)
            kwargs.pop("files", None)
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        performance = self.object.performance
        seat_rows = BookingSeat.objects.filter(performance=performance).values_list(
            "seat_id", "booking_id", "booking__status"
        )
        reserved = {
            seat_id
            for seat_id, booking_id, booking_status in seat_rows
            if booking_id != self.object.pk and booking_status == Booking.STATUS_CONFIRMED
        }
        selected_ids = {
            seat_id
            for seat_id, booking_id, _ in seat_rows
            if booking_id == self.object.pk
        }
        context.update({
            "theater": self.get_theater(),
            "booking": self.object,
            "performance": performance,
            "zone_layout": build_zone_layout(performance, reserved, selected_ids),
        })
        return context

    def form_valid(self, form):
        booking = self.object
        performance = booking.performance
        selected_seats = list(form.cleaned_data["seats"])

        with transaction.atomic():
            reserved_ids = set(
                BookingSeat.objects.filter(
                    performance=performance,
                    booking__status=Booking.STATUS_CONFIRMED,
                )
                .exclude(booking=booking)
                .select_for_update()
                .values_list("seat_id", flat=True)
            )
            if any(s.id in reserved_ids for s in selected_seats):
                form.add_error("seats", "Alcuni posti non sono più disponibili.")
                return self.form_invalid(form)

            seat_prices = [
                (seat, performance.zone_price(seat.auditorium_zone))
                for seat in selected_seats
            ]
            BookingSeat.objects.filter(booking=booking).delete()
            BookingSeat.bulk_create_for_booking(booking, performance, seat_prices)
            booking.total_price = sum((price for _, price in seat_prices), Decimal("0.00"))
            booking.save(update_fields=["total_price"])

        messages.success(self.request, "Prenotazione aggiornata.")
        return redirect("theaters:management_bookings", theater_id=self.get_theater().pk)
