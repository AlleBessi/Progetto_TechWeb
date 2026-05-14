from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from apps.accounts.models import Role
from apps.core.select2_widgets import SimpleSelect2Widget, SimpleSelect2MultipleWidget
from apps.shows.models import Category


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=True, widget=SimpleSelect2Widget())
    interests = forms.ModelMultipleChoiceField(
        queryset=Category.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    city = forms.CharField(max_length=120, required=False)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2", "role", "city", "latitude", "longitude", "interests"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interests"].queryset = Category.objects.all()


class ProfileForm(forms.Form):
    display_name = forms.CharField(max_length=150, required=False)
    role = forms.ModelChoiceField(queryset=Role.objects.all(), required=True, widget=SimpleSelect2Widget())
    interests = forms.ModelMultipleChoiceField(
        queryset=Category.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    city = forms.CharField(max_length=120, required=False)
    latitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)
    longitude = forms.DecimalField(max_digits=9, decimal_places=6, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interests"].queryset = Category.objects.all()
