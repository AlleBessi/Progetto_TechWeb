from django import forms

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
        reserved_qs = BookingSeat.objects.filter(
            performance=performance, booking__status=Booking.STATUS_CONFIRMED
        )
        if exclude_booking is not None:
            reserved_qs = reserved_qs.exclude(booking=exclude_booking)
        reserved = reserved_qs.values_list("seat_id", flat=True)
        self.fields["seats"].queryset = performance.hall.seats.exclude(id__in=reserved)
