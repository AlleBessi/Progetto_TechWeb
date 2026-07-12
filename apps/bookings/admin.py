from django.contrib import admin

from .models import Booking, BookingSeat


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
	list_display = ("user", "performance", "total_price", "created_at")
	list_filter = ("performance",)


@admin.register(BookingSeat)
class BookingSeatAdmin(admin.ModelAdmin):
	list_display = ("performance", "seat", "price_at_purchase")
	list_filter = ("performance",)
