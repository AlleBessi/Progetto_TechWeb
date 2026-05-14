"""Simple Select2 widgets without search for basic form selects."""

from typing import cast

from django_select2.forms import Select2MultipleWidget, Select2Widget  # type: ignore[import-untyped]


class SimpleSelect2Widget(Select2Widget):
	"""Basic Select2 widget without search for regular choice fields with classic theme."""
	
	def build_attrs(
		self,
		base_attrs: dict[str, str],
		extra_attrs: dict[str, str] | None = None,
	) -> dict[str, str]:
		"""Hide search box and apply classic theme."""
		default_attrs = {
			"data-minimum-results-for-search": "Infinity",  # Hide search box
		}
		default_attrs.update(base_attrs)
		return cast(dict[str, str], super().build_attrs(default_attrs, extra_attrs=extra_attrs))  # type: ignore[reportUnknownMemberType]


class SimpleSelect2MultipleWidget(Select2MultipleWidget):
	"""Basic Select2 multiple widget without search for regular choice fields with classic theme."""
	
	def build_attrs(
		self,
		base_attrs: dict[str, str],
		extra_attrs: dict[str, str] | None = None,
	) -> dict[str, str]:
		"""Hide search box and apply classic theme."""
		default_attrs = {
			"data-minimum-results-for-search": "Infinity",  # Hide search box
		}
		default_attrs.update(base_attrs)
		return cast(dict[str, str], super().build_attrs(default_attrs, extra_attrs=extra_attrs))  # type: ignore[reportUnknownMemberType]
