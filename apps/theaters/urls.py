from django.urls import path

from . import views

app_name = "theaters"

urlpatterns = [
    path("management/", views.management_dashboard, name="management"),
    path("", views.theater_list, name="list"),
    path("new/", views.theater_create, name="create"),
    path("<int:theater_id>/edit/", views.theater_update, name="update"),
    path("<int:theater_id>/delete/", views.theater_delete, name="delete"),
    path("<int:theater_id>/", views.theater_detail, name="detail"),
    path("<int:theater_id>/halls/new/", views.hall_create, name="hall_create"),
    path("<int:theater_id>/halls/<int:hall_id>/manage/", views.hall_manage, name="hall_manage"),
    path("<int:theater_id>/halls/<int:hall_id>/delete/", views.hall_delete, name="hall_delete"),
    path("<int:theater_id>/admins/new/", views.theater_assign_admin, name="assign_admin"),
]
