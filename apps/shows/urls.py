from django.urls import path

from . import api, views

app_name = "shows"

urlpatterns = [
    # ── Shows – public browsing ──────────────────────────────────────────────
    path("", views.ShowList.as_view(), name="list"),
    path("<int:show_id>/", views.ShowDetail.as_view(), name="detail"),

    # ── Shows – artist management ────────────────────────────────────────────
    path("artist/dashboard/", views.ArtistShowsDashboardView.as_view(), name="artist_dashboard"),
    path("artist/dashboard/shows/", views.ArtistShowsDashboardView.as_view(), name="artist_shows_dashboard"),
    path("artist/dashboard/performances/", views.ArtistPerformanceDashboardView.as_view(), name="artist_performances_dashboard"),
    path("new/", views.ShowCreate.as_view(), name="create"),
    path("<int:show_id>/edit/", views.ShowUpdate.as_view(), name="edit"),
    path("<int:show_id>/delete/", views.ShowDelete.as_view(), name="delete"),

    # ── Performances – Performance management ───────────────────
    path("performances/new/<int:theater_id>/", views.PerformanceCreate.as_view(), name="performance_create"),
    path("performances/<int:performance_id>/edit/", views.PerformanceUpdate.as_view(), name="performance_edit"),
    path("performances/<int:performance_id>/delete/", views.PerformanceDeleteView.as_view(), name="performance_delete"),

    # Workflow actions (confirm / reject by artist)
    path("performances/<int:performance_id>/confirm/", views.PerformanceConfirmView.as_view(action="confirm"), name="performance_confirm"),
    path("performances/<int:performance_id>/reject/", views.PerformanceConfirmView.as_view(action="reject"), name="performance_reject"),

    # ── Internal API ─────────────────────────────────────────────────────────
    path("api/auditoriums/<int:auditorium_id>/zones/", api.AuditoriumZonesAPI.as_view(), name="api_auditorium_zones"),
]