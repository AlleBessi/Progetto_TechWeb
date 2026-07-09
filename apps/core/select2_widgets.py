"""Shared Select2 widgets used across the project."""

from django_select2.forms import ModelSelect2MultipleWidget, ModelSelect2Widget, Select2MultipleWidget, Select2Widget  # type: ignore[import-untyped]


class _BaseSelect2WidgetMixin:
	"""Apply a consistent select2 configuration across widgets."""

	default_widget_attrs = {
		"data-width": "100%",
	}

	# Classes that must always be present for django-select2 to initialize.
	_required_classes = {"django-select2"}
	
	def build_attrs(self, base_attrs: dict[str, str], extra_attrs: dict[str, str] | None = None) -> dict[str, str]:
		merged = {**self.default_widget_attrs, **base_attrs}
		return super().build_attrs(merged, extra_attrs=extra_attrs)  # type: ignore[reportUnknownMemberType]


class SimpleSelect2Widget(_BaseSelect2WidgetMixin, Select2Widget):
	"""Basic Select2 widget without search for regular choice fields."""

	def build_attrs(self, base_attrs: dict[str, str], extra_attrs: dict[str, str] | None = None) -> dict[str, str]:
		base_attrs = dict(base_attrs)
		base_attrs.setdefault("data-minimum-results-for-search", "Infinity")
		return super().build_attrs(base_attrs, extra_attrs=extra_attrs)


class SimpleSelect2MultipleWidget(_BaseSelect2WidgetMixin, Select2MultipleWidget):
	"""Basic Select2 multiple widget without search for regular choice fields."""

	def build_attrs(self, base_attrs: dict[str, str], extra_attrs: dict[str, str] | None = None) -> dict[str, str]:
		base_attrs = dict(base_attrs)
		base_attrs.setdefault("data-minimum-results-for-search", "Infinity")
		return super().build_attrs(base_attrs, extra_attrs=extra_attrs)


class ShowSelect2Widget(_BaseSelect2WidgetMixin,ModelSelect2Widget):
	"""Custom Select2 widget for shows with lazy loading."""

	search_fields = ["title__icontains", "description__icontains"]

	def label_from_instance(self, obj):
		artist = obj.artist.get_full_name() or obj.artist.username
		return f"{obj.title} - {obj.duration_minutes}m - {artist}"


class ArtistSelect2Widget(_BaseSelect2WidgetMixin, ModelSelect2MultipleWidget):
	"""Custom Select2 widget for artist selection."""

	search_fields = ["username__icontains", "first_name__icontains", "last_name__icontains", "email__icontains"]

	def label_from_instance(self, obj):
		return obj.get_full_name() or obj.username


class ArtistSingleSelect2Widget(_BaseSelect2WidgetMixin, ModelSelect2Widget):
	"""Single-select Select2 widget for artists."""

	search_fields = ["username__icontains", "first_name__icontains", "last_name__icontains", "email__icontains"]

	def label_from_instance(self, obj):
		return obj.get_full_name() or obj.username


class ManagerSelect2Widget(_BaseSelect2WidgetMixin, ModelSelect2Widget):
	"""Custom Select2 widget for manager selection."""

	search_fields = ["username__icontains", "first_name__icontains", "last_name__icontains", "email__icontains"]

	def label_from_instance(self, obj):
		display = obj.get_full_name() or obj.username
		if obj.groups.filter(name="manager").exists():
			return f"{display} (Gestore)"
		return display


class TheaterSelect2Widget(_BaseSelect2WidgetMixin, ModelSelect2Widget):
	"""Custom Select2 widget for theater selection."""

	search_fields = ["name__icontains", "city__icontains", "address__icontains"]

	def label_from_instance(self, obj):
		return f"{obj.name} - {obj.city}"


class ZoneSelect2Widget(_BaseSelect2WidgetMixin, ModelSelect2Widget):
	"""Select2 widget for auditorium zone selection.

	Zones are always a small fixed set per auditorium, so search is disabled.
	"""

	search_fields = ["zone__icontains", "auditorium__name__icontains"]

	def build_attrs(self, base_attrs: dict[str, str], extra_attrs: dict[str, str] | None = None) -> dict[str, str]:
		base_attrs = dict(base_attrs)
		base_attrs.setdefault("data-minimum-results-for-search", "Infinity")
		return super().build_attrs(base_attrs, extra_attrs=extra_attrs)

	def label_from_instance(self, obj):
		return f"{obj.auditorium.name} - {obj.zone}"