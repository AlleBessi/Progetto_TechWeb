from django.urls import path

from . import views

app_name = "shows"

urlpatterns = [
    path("", views.show_list, name="list"),
    path("<int:show_id>/", views.show_detail, name="detail"),
    path("artist/dashboard/", views.artist_dashboard, name="artist_dashboard"),
    path("artist/new/", views.show_create, name="create"),
    path("artist/<int:show_id>/edit/", views.show_edit, name="edit"),
    path("artist/<int:show_id>/delete/", views.show_delete, name="delete"),
    path("artist/<int:show_id>/confirm/", views.show_confirm, name="confirm"),
    path("theater/<int:theater_id>/performance/new/", views.performance_create, name="performance_create"),
    path("performance/<int:performance_id>/edit/", views.performance_edit, name="performance_edit"),
    path("performance/<int:performance_id>/delete/", views.performance_delete, name="performance_delete"),
]
