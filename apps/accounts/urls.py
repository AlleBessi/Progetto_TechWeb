from django.contrib.auth import views as auth_views
from django.urls import path
 
from . import views
 
app_name = "accounts"
 
urlpatterns = [
    # ── Auth ────────────────────────────────────────────────────────────────
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
 
    # ── Super-admin: user management ────────────────────────────────────────
    path("users/", views.AdminUserListView.as_view(), name="admin_user_list"),
    path("users/new/", views.AdminUserCreateView.as_view(), name="admin_user_create"),
    path("users/<int:user_id>/edit/",   views.AdminUserUpdateView.as_view(), name="admin_user_edit"),
    path("users/<int:user_id>/delete/", views.AdminUserDeleteView.as_view(), name="admin_user_delete"),
    path("users/<int:user_id>/password/", views.AdminUserSetPasswordView.as_view(), name="admin_user_set_password"),
]
