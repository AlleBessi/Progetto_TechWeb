from django import forms

from apps.core.select2_widgets import SimpleSelect2Widget, ShowSelect2Widget
from apps.theaters.models import Auditorium, AuditoriumZone

from .models import Category, Performance, PerformancePrice, Show


class ShowForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        widget=SimpleSelect2Widget(),
    )

    class Meta:
        model = Show
        fields = ["title", "description", "category", "duration_minutes", "poster", "cover"]


class PerformanceForm(forms.ModelForm):
    show = forms.ModelChoiceField(
        queryset=Show.objects.all(),
        widget=ShowSelect2Widget(attrs={"data-placeholder": "Seleziona uno spettacolo..."}),
    )
    auditorium = forms.ModelChoiceField(
        queryset=Auditorium.objects.none(),
        widget=SimpleSelect2Widget(attrs={"data-placeholder": "Seleziona una sala..."}),
    )
    starts_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"],
    )

    class Meta:
        model = Performance
        fields = ["show", "auditorium", "starts_at"]

    def __init__(self, *args, theater=None, selected_auditorium=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.no_zones: bool = False
        # zone_by_field: field_name → zone_obj — used for saving prices
        self.zone_by_field: dict[str, AuditoriumZone] = {}
        self.fieldsets: list[tuple[str, list[str]]] = [
            ("Dettagli performance", ["show", "auditorium", "starts_at"]),
            ("Prezzi per zona", []),
        ]

        if theater is not None:
            self.fields["auditorium"].queryset = theater.auditoriums.all()

        # Resolve the auditorium to use for zone generation:
        # priority → explicit argument, then existing instance's auditorium
        if selected_auditorium is None and self.instance.pk:
            selected_auditorium = self.instance.auditorium

        if selected_auditorium is not None:
            self.fields["auditorium"].initial = selected_auditorium.pk
            self._add_zone_fields(selected_auditorium)

    def _add_zone_fields(self, auditorium: Auditorium) -> None:
        zones = list(getattr(auditorium, "zones").order_by("order", "id"))
        if not zones:
            self.no_zones = True
            return

        price_lookup: dict[int, PerformancePrice] = {}
        if self.instance.pk:
            price_lookup = {
                pp.auditorium_zone_id: pp
                for pp in self.instance.zone_prices.filter(auditorium_zone__in=zones)
            }

        for zone in zones:
            field_name = str(zone.cod_zone)
            price_obj = price_lookup.get(zone.pk)
            self.fields[field_name] = forms.DecimalField(
                min_value=0,
                label=f"Prezzo {zone.zone} (EUR)",
                required=True,
                initial=price_obj.price if price_obj else 0,
            )
            self.zone_by_field[field_name] = zone
            self.fieldsets[1][1].append(field_name)