from django.contrib import admin

from .models import Role, Profile


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
	list_display = ("name",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "role", "city", "created_at")
	search_fields = ("user__username", "user__email", "display_name")
