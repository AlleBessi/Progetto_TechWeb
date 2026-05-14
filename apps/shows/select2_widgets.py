from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget


class ShowSelect2Widget(ModelSelect2Widget):
	"""Custom Select2 widget for shows with lazy loading."""
	
	search_fields = ["title__icontains", "description__icontains"]
	
	def label_from_instance(self, obj):
		"""Display show info in the select dropdown."""
		artists = ", ".join([a.get_full_name() or a.username for a in obj.artists.all()])
		return f"{obj.title} - {obj.duration_minutes}m - {artists}" if artists else f"{obj.title} - {obj.duration_minutes}m"


class ShowSelect2MultipleWidget(ModelSelect2MultipleWidget):
	"""Custom Select2 widget for multiple show selection."""
	
	search_fields = ["title__icontains", "description__icontains"]
	
	def label_from_instance(self, obj):
		"""Display show info in the select dropdown."""
		artists = ", ".join([a.get_full_name() or a.username for a in obj.artists.all()])
		return f"{obj.title} - {obj.duration_minutes}m - {artists}" if artists else f"{obj.title} - {obj.duration_minutes}m"


class ArtistSelect2Widget(ModelSelect2MultipleWidget):
	"""Custom Select2 widget for artist selection."""
	
	search_fields = ["username__icontains", "first_name__icontains", "last_name__icontains", "email__icontains"]
	
	def label_from_instance(self, obj):
		"""Display full name or username."""
		return obj.get_full_name() or obj.username
