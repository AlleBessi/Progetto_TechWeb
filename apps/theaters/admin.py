from django.contrib import admin

from .models import Auditorium, AuditoriumZone, Seat, Theater, TheaterAdmin


@admin.register(Theater)
class TheaterAdminConfig(admin.ModelAdmin):
	list_display = ("name", "city", "province", "created_at")
	search_fields = ("name", "city")


@admin.register(Auditorium)
class AuditoriumAdmin(admin.ModelAdmin):
	list_display = ("name", "theater", "cod_auditorium", "seat_rows", "seat_cols")
	list_filter = ("theater",)


@admin.register(AuditoriumZone)
class AuditoriumZoneAdmin(admin.ModelAdmin):
	list_display = ("auditorium", "cod_zone", "zone", "rows", "seats_per_row", "order")
	list_filter = ("auditorium",)


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
	list_display = ("auditorium", "auditorium_zone", "row", "number", "is_accessible")
	list_filter = ("auditorium", "auditorium_zone", "is_accessible")


@admin.register(TheaterAdmin)
class TheaterAdminAdmin(admin.ModelAdmin):
	list_display = ("theater", "user", "added_at")
	list_filter = ("theater",)
