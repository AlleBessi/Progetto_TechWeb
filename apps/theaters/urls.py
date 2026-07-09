from django.urls import path

from . import views

app_name = "theaters"

urlpatterns = [
    # ── Public ───────────────────────────────────────────────────────────────
    path("", views.TheaterListView.as_view(), name="list"),
    path("<int:theater_id>/", views.TheaterDetailView.as_view(), name="detail"),

    # ── Theater management dashboard ─────────────────────────────────────────
    path("management/", views.ManagementDashboardView.as_view(), name="management"),

    # ── Theater CRUD ─────────────────────────────────────────────────────────
    path("management/new/", views.TheaterCreateView.as_view(), name="create"),
    path("management/<int:theater_id>/", views.TheaterManagementView.as_view(), name="management_detail"),
    path("management/<int:theater_id>/edit/", views.TheaterUpdateView.as_view(), name="update"),
    path("management/<int:theater_id>/delete/", views.TheaterDeleteView.as_view(), name="delete"),

    # ── Theater management sub-sections ──────────────────────────────────────
    # (dashboard panels; not CRUD – no new/edit/delete variants needed here)
    path("management/<int:theater_id>/data/", views.TheaterManagementDataView.as_view(), name="management_data"),
    path("management/<int:theater_id>/schedule/", views.TheaterManagementProgrammazioneView.as_view(), name="management_schedule"),
    path("management/<int:theater_id>/bookings/", views.TheaterManagementBookingsView.as_view(), name="management_bookings"),
    path("management/<int:theater_id>/occupancy/", views.TheaterManagementOccupazioneView.as_view(), name="management_occupancy"),
    path("management/<int:theater_id>/occupancy/<int:performance_id>/", views.TheaterOccupancyDetailView.as_view(), name="management_occupancy_detail"),

    # ── Theater admins (gestori) — split CRUD ────────────────────────────────
    path("management/<int:theater_id>/admins/", views.TheaterAdminListView.as_view(), name="management_admins"),
    path("management/<int:theater_id>/admins/add/", views.TheaterAdminAddView.as_view(), name="admin_add"),
    path("management/<int:theater_id>/admins/<int:user_id>/remove/", views.TheaterAdminRemoveView.as_view(), name="admin_delete"),


    # ── Auditorium CRUD – nested under their theater ─────────────────────────
    path("management/<int:theater_id>/auditoriums/new/", views.AuditoriumCreateView.as_view(), name="auditorium_create"),
    path("management/<int:theater_id>/auditoriums/<int:auditorium_id>/", views.AuditoriumManageView.as_view(), name="auditorium_update"),
    path("management/<int:theater_id>/auditoriums/<int:auditorium_id>/delete/", views.AuditoriumDeleteView.as_view(), name="auditorium_delete"),

    # ── Booking management – theater-scoped overrides ────────────────────────
    # Full user-facing booking CRUD lives in the bookings app.
    # Only theater-manager-specific actions (with theater context) live here.
    path("management/<int:theater_id>/bookings/<int:booking_id>/edit/", views.BookingUpdateManagerView.as_view(), name="booking_update"),
    path("management/<int:theater_id>/bookings/<int:booking_id>/cancel/", views.BookingCancelView.as_view(), name="booking_cancel"),

    # NOTE: Performance CRUD (create / edit / delete / confirm / reject) is
    # defined in shows/urls.py and should be linked from templates using the
    # shows: namespace – e.g. {% url 'shows:performance_create' theater.pk %}.
    # This eliminates the previous cross-app import of show_views here.
]