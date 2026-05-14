from django_select2.forms import ModelSelect2Widget


class ManagerSelect2Widget(ModelSelect2Widget):
	"""Custom Select2 widget for manager selection."""
	
	search_fields = ["username__icontains", "first_name__icontains", "last_name__icontains", "email__icontains"]
	
	def label_from_instance(self, obj):
		"""Display full name or username."""
		display = obj.get_full_name() or obj.username
		if obj.profile and obj.profile.role and obj.profile.role.name == "manager":
			return f"{display} (Gestore)"
		return display
