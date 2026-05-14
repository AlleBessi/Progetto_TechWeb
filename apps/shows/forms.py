from datetime import datetime

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_select2.forms import ModelSelect2Widget

from apps.accounts.models import Role
from apps.theaters.models import Hall

from .models import Performance, Show
from .select2_widgets import ArtistSelect2Widget, ShowSelect2Widget

User = get_user_model()


class ShowForm(forms.ModelForm):
    artists = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(profile__role__name=Role.ROLE_ARTIST),
        widget=ArtistSelect2Widget(
            attrs={"data-placeholder": "Seleziona almeno un artista..."}
        ),
        help_text="Seleziona almeno un artista",
    )

    class Meta:
        model = Show
        fields = ["title", "description", "category", "duration_minutes", "poster", "cover", "artists"]

    def clean_artists(self):
        artists = self.cleaned_data.get("artists")
        if not artists or artists.count() == 0:
            raise ValidationError("Uno spettacolo deve avere almeno un artista.")
        return artists


class PerformanceForm(forms.ModelForm):
    show = forms.ModelChoiceField(
        queryset=Show.objects.filter(status__in=[Show.STATUS_ARTIST_CONFIRMED, Show.STATUS_APPROVED]),
        widget=ShowSelect2Widget(attrs={"data-placeholder": "Seleziona uno spettacolo..."})
    )

    class Meta:
        model = Performance
        fields = ["show", "theater", "hall", "starts_at", "base_price"]
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class PerformanceCreateForm(forms.Form):
    show = forms.ModelChoiceField(
        queryset=Show.objects.none(),
        widget=ShowSelect2Widget(attrs={"data-placeholder": "Seleziona uno spettacolo..."})
    )
    hall = forms.ModelChoiceField(queryset=Hall.objects.none())
    starts_at_list = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="Una data/ora per riga. Formato: YYYY-MM-DD HH:MM",
    )

    def __init__(self, theater, hall=None, zones=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.theater = theater
        self.hall = hall
        self.zone_codes = []

        self.fields["show"].queryset = Show.objects.filter(
            status__in=[Show.STATUS_ARTIST_CONFIRMED, Show.STATUS_APPROVED]
        )
        self.fields["hall"].queryset = theater.halls.all()
        if hall is not None:
            self.fields["hall"].initial = hall
            self.fields["hall"].disabled = True
            self.fields["hall"].required = False

        zones = zones or []
        if zones:
            for zone in zones:
                code = zone.zone
                label = zone.get_zone_display()
                field_name = f"price_{code}"
                self.fields[field_name] = forms.DecimalField(
                    min_value=0,
                    label=f"Prezzo {label} (EUR)",
                    required=True,
                )
                self.zone_codes.append(code)
        else:
            self.fields["base_price"] = forms.DecimalField(
                min_value=0,
                label="Prezzo unico (EUR)",
                required=True,
            )

    def clean_starts_at_list(self):
        raw = self.cleaned_data["starts_at_list"]
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            raise ValidationError("Inserisci almeno una data/ora.")
        parsed = []
        for line in lines:
            normalized = line.replace("T", " ")
            dt = None
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(normalized, fmt)
                    break
                except ValueError:
                    continue
            if dt is None:
                raise ValidationError("Formato non valido: usa YYYY-MM-DD HH:MM")
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            parsed.append(dt)
        return parsed


class PerformanceUpdateForm(forms.Form):
    starts_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))

    def __init__(self, performance, zones=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.performance = performance
        self.zone_codes = []
        zones = zones or []
        if zones:
            for zone in zones:
                code = zone.zone
                label = zone.get_zone_display()
                field_name = f"price_{code}"
                price_obj = performance.zone_prices.filter(zone=code).first()
                self.fields[field_name] = forms.DecimalField(
                    min_value=0,
                    label=f"Prezzo {label} (EUR)",
                    required=True,
                    initial=price_obj.price if price_obj else performance.base_price,
                )
                self.zone_codes.append(code)
        else:
            self.fields["base_price"] = forms.DecimalField(
                min_value=0,
                label="Prezzo unico (EUR)",
                required=True,
                initial=performance.base_price,
            )

    def clean_starts_at(self):
        dt = self.cleaned_data["starts_at"]
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt
