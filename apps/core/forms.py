from django import forms

from apps.core.select2_widgets import SimpleSelect2Widget
from apps.shows.models import Category


class SearchForm(forms.Form):
    q = forms.CharField(max_length=200, required=False)
    category = forms.ModelChoiceField(queryset=Category.objects.none(), required=False, widget=SimpleSelect2Widget())
    city = forms.CharField(max_length=120, required=False)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.all()
