from django.contrib import admin

from .models import Booking, BookingSeat


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
	list_display = ("user", "performance", "status", "total_price", "created_at")
	list_filter = ("status",)


@admin.register(BookingSeat)
class BookingSeatAdmin(admin.ModelAdmin):
	list_display = ("performance", "seat", "price_at_purchase")
	list_filter = ("performance",)
