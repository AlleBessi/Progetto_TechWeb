from django import forms

from .utils import build_zone_layout
from apps.theaters.models import Seat

from .models import Booking, BookingSeat


class BookingForm(forms.Form):
    seats = forms.ModelMultipleChoiceField(
        queryset=Seat.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    def __init__(self, performance, *args, exclude_booking=None, **kwargs):
        super().__init__(*args, **kwargs)

        reserved_qs = BookingSeat.objects.for_performance(performance).confirmed()

        if exclude_booking:
            reserved_qs = reserved_qs.exclude(booking=exclude_booking)

        self.reserved_ids = set(reserved_qs.reserved_seat_ids())

        # The queryset includes all seats (not just available ones) so that a
        # seat reserved by someone else between page render and submit fails
        # our own availability check in clean_seats() below, instead of
        # Django's generic "not a valid choice" field error.
        self.fields["seats"].queryset = performance.auditorium.seats.all()

        # Pre-selected seat IDs come from the form's initial data (set by the
        # view via get_initial), so no extra query is needed here.
        selected_ids = set(self.initial.get("seats", []))

        self.zone_layout = build_zone_layout(
            performance,
            self.reserved_ids,
            selected_ids,
        )

    def clean_seats(self):
        seats = self.cleaned_data["seats"]
        if any(seat.id in self.reserved_ids for seat in seats):
            raise forms.ValidationError("Alcuni posti non sono più disponibili.")
        return seats
