from django.contrib import admin

from .models import Hall, HallZone, Seat, Theater, TheaterAdmin


@admin.register(Theater)
class TheaterAdminConfig(admin.ModelAdmin):
	list_display = ("name", "city", "province", "created_at")
	search_fields = ("name", "city")


@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
	list_display = ("name", "theater", "seat_rows", "seat_cols")
	list_filter = ("theater",)


@admin.register(HallZone)
class HallZoneAdmin(admin.ModelAdmin):
	list_display = ("hall", "zone", "rows", "seats_per_row", "order")
	list_filter = ("hall", "zone")


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
	list_display = ("hall", "row", "number", "zone", "is_accessible")
	list_filter = ("hall", "zone", "is_accessible")


@admin.register(TheaterAdmin)
class TheaterAdminAdmin(admin.ModelAdmin):
	list_display = ("theater", "user", "added_at")
	list_filter = ("theater",)
