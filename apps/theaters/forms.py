from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from apps.core.select2_widgets import ManagerSelect2Widget
from .models import Auditorium, AuditoriumZone, Theater


class TheaterForm(forms.ModelForm):
    class Meta:
        model = Theater
        fields = [
            "name",
            "description",
            "photo",
            "address",
            "city",
            "province",
            "postal_code",
            "phone",
            "email",
            "opening_hours",
            "latitude",
            "longitude",
        ]


class AuditoriumForm(forms.ModelForm):
    class Meta:
        model = Auditorium
        fields = ["name", "seat_rows", "seat_cols"]


class TheaterAdminForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=get_user_model().objects.filter(groups__name="manager").distinct(),
        widget=ManagerSelect2Widget(attrs={"data-placeholder": "Seleziona un gestore..."}),
        help_text="Seleziona un gestore",
    )

    def __init__(self, *args, **kwargs):
        theater = kwargs.pop("theater", None)
        super().__init__(*args, **kwargs)
        managers_qs = get_user_model().objects.filter(groups__name="manager").distinct().order_by("username")
        self.fields["user"].queryset = managers_qs
        if theater is not None:
            self.theater = theater

    def clean_user(self):
        user = self.cleaned_data.get("user")
        if not user or not user.groups.filter(name="manager").exists():
            raise ValidationError("Solo i gestori possono essere assegnati ai teatri.")
        return user


class AuditoriumZoneForm(forms.ModelForm):
    class Meta:
        model = AuditoriumZone
        fields = ["zone", "rows", "seats_per_row", "order"]
        widgets = {
            "zone": forms.TextInput(),
        }


AuditoriumZoneFormSet = inlineformset_factory(
    Auditorium,
    AuditoriumZone,
    form=AuditoriumZoneForm,
    extra=0,
    can_delete=True,
)