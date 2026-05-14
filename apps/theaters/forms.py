from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from apps.accounts.models import Role
from .models import Hall, HallZone, Theater
from .select2_widgets import ManagerSelect2Widget


class TheaterForm(forms.ModelForm):
    class Meta:
        model = Theater
        fields = [
            "name",
            "description",
            "address",
            "city",
            "province",
            "postal_code",
            "latitude",
            "longitude",
        ]


class HallForm(forms.ModelForm):
    class Meta:
        model = Hall
        fields = ["name", "seat_rows", "seat_cols"]


class TheaterAdminForm(forms.Form):
	user = forms.ModelChoiceField(
		queryset=get_user_model().objects.filter(profile__role__name=Role.ROLE_MANAGER),
		widget=ManagerSelect2Widget(attrs={"data-placeholder": "Seleziona un gestore..."}),
		help_text="Seleziona un gestore"
	)

	def clean_user(self):
		user = self.cleaned_data.get("user")
		if not user.profile.role or user.profile.role.name != Role.ROLE_MANAGER:
			raise ValidationError("Solo i gestori possono essere assegnati ai teatri.")
		return user


class HallZoneForm(forms.ModelForm):
    class Meta:
        model = HallZone
        fields = ["zone", "rows", "seats_per_row", "order"]


HallZoneFormSet = inlineformset_factory(
    Hall,
    HallZone,
    form=HallZoneForm,
    extra=3,
    can_delete=True,
)
