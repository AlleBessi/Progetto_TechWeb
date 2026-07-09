import django_filters
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.core.select2_widgets import ArtistSingleSelect2Widget, ShowSelect2Widget, SimpleSelect2Widget, TheaterSelect2Widget
from apps.shows.models import Category, Performance, Show
from apps.theaters.models import Theater

User = get_user_model()


class PerformanceFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        label="Ricerca",
        method="filter_search",
        widget=forms.TextInput(attrs={"placeholder": "Titolo, descrizione o teatro"}),
    )
    show = django_filters.ModelChoiceFilter(
        label="Spettacolo",
        queryset=Show.objects.all(),
        widget=ShowSelect2Widget(queryset=Show.objects.all(), attrs={"data-placeholder": "Seleziona uno spettacolo..."}),
    )
    theater = django_filters.ModelChoiceFilter(
        label="Teatro",
        field_name="auditorium__theater",
        queryset=Theater.objects.all(),
        widget=TheaterSelect2Widget(attrs={"data-placeholder": "Seleziona un teatro..."}),
    )
    category = django_filters.ModelChoiceFilter(
        label="Categoria",
        field_name="show__category",
        queryset=Category.objects.all(),
        widget=SimpleSelect2Widget(attrs={"data-placeholder": "Tutte le categorie"}),
    )
    artist = django_filters.ModelChoiceFilter(
        label="Artista",
        field_name="show__artist",
        queryset=User.objects.filter(groups__name="artist").distinct(),
        widget=ArtistSingleSelect2Widget(attrs={"data-placeholder": "Seleziona un artista..."}),
    )
    city = django_filters.CharFilter(
        label="Citta",
        field_name="auditorium__theater__city",
        lookup_expr="icontains",
        widget=forms.TextInput(attrs={"placeholder": "Milano, Torino..."}),
    )
    date_from = django_filters.DateFilter(
        label="Data da",
        field_name="starts_at",
        lookup_expr="date__gte",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = django_filters.DateFilter(
        label="Data a",
        field_name="starts_at",
        lookup_expr="date__lte",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    price_min = django_filters.NumberFilter(
        label="Prezzo minimo",
        field_name="zone_prices__price",
        lookup_expr="gte",
        widget=forms.NumberInput(attrs={"placeholder": "0"}),
    )
    price_max = django_filters.NumberFilter(
        label="Prezzo massimo",
        field_name="zone_prices__price",
        lookup_expr="lte",
        widget=forms.NumberInput(attrs={"placeholder": "50"}),
    )

    class Meta:
        model = Performance
        fields = [
            "q",
            "show",
            "theater",
            "category",
            "artist",
            "city",
            "date_from",
            "date_to",
            "price_min",
            "price_max",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(show__title__icontains=value)
            | Q(show__description__icontains=value)
            | Q(auditorium__theater__name__icontains=value)
        ).distinct()
