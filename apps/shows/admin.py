from django.contrib import admin

from .models import Category, Performance, PerformanceZonePrice, Show


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	list_display = ("name", "slug")
	prepopulated_fields = {"slug": ("name",)}


@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
	list_display = ("title", "category", "status", "created_by")
	list_filter = ("status", "category")
	search_fields = ("title", "created_by__username")


@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
	list_display = ("show", "theater", "hall", "starts_at", "status")
	list_filter = ("status", "theater")


@admin.register(PerformanceZonePrice)
class PerformanceZonePriceAdmin(admin.ModelAdmin):
	list_display = ("performance", "zone", "price")
	list_filter = ("zone",)
