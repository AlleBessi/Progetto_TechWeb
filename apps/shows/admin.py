from django.contrib import admin

from .models import Category, Performance, PerformancePrice, Show


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	list_display = ("name", "slug")
	prepopulated_fields = {"slug": ("name",)}


@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
	list_display = ("title", "category", "artist")
	list_filter = ("category",)
	search_fields = ("title", "artist__username")


@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
	list_display = ("show", "auditorium__theater", "auditorium", "starts_at", "status")
	list_filter = ("status", "auditorium__theater")


@admin.register(PerformancePrice)
class PerformancePriceAdmin(admin.ModelAdmin):
	list_display = ("performance", "auditorium_zone", "price")
	list_filter = ("auditorium_zone",)
