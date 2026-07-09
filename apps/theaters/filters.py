import django_filters
from django import forms
from django.db.models import Q

from apps.core.select2_widgets import SimpleSelect2Widget, ShowSelect2Widget, SimpleSelect2Widget
from apps.shows.models import Performance, Show
from apps.theaters.models import Auditorium
from apps.bookings.models import Booking


class PerformanceManagementFilter(django_filters.FilterSet):
    show = django_filters.ModelChoiceFilter(
        label="Spettacolo",
        queryset=Show.objects.all(),
        widget=ShowSelect2Widget(attrs={"data-placeholder": "Seleziona uno spettacolo..."}),
    )
    auditorium: django_filters.ModelChoiceFilter = django_filters.ModelChoiceFilter(
        label="Sala",
        field_name="auditorium",
        queryset=Auditorium.objects.none(),
        widget=SimpleSelect2Widget(attrs={"data-placeholder": "Seleziona una sala..."}),
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
    status = django_filters.ChoiceFilter(
        label="Stato",
        choices=Performance.STATUS_CHOICES,
        widget=SimpleSelect2Widget(),
    )

    class Meta:
        model = Performance
        fields = ["show", "auditorium", "date_from", "date_to", "status"]

    def __init__(self, data=None, queryset=None, *, theater=None, request=None, prefix=None):
        super().__init__(data=data, queryset=queryset, request=request, prefix=prefix)
        if theater is not None:
            self.filters["auditorium"].field.queryset = Auditorium.objects.filter(theater=theater)


class BookingManagementFilter(django_filters.FilterSet):
    show = django_filters.ModelChoiceFilter(
        label="Spettacolo",
        field_name="performance__show",
        queryset=Show.objects.all(),
        widget=ShowSelect2Widget(attrs={"data-placeholder": "Seleziona uno spettacolo..."}),
    )
    customer = django_filters.CharFilter(
        label="Cliente",
        method="filter_customer",
        widget=forms.TextInput(attrs={"placeholder": "Nome o username"}),
    )
    date_from = django_filters.DateFilter(
        label="Data da",
        field_name="performance__starts_at",
        lookup_expr="date__gte",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = django_filters.DateFilter(
        label="Data a",
        field_name="performance__starts_at",
        lookup_expr="date__lte",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    status = django_filters.ChoiceFilter(
        label="Stato",
        choices=Booking.STATUS_CHOICES,
        widget=SimpleSelect2Widget(),
    )

    class Meta:
        model = Booking
        fields = ["show", "customer", "date_from", "date_to", "status"]

    def filter_customer(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(user__username__icontains=value)
            | Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
        )
