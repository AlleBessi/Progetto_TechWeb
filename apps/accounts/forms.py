from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group, User

from apps.core.select2_widgets import SimpleSelect2Widget


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password1", "password2"]


class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)


class AdminUserCreateForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ModelChoiceField(
        queryset=Group.objects.all().order_by("name"),
        widget=SimpleSelect2Widget(),
        required=True,
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password1", "password2", "role"]

class AdminUserUpdateForm(UserChangeForm):
    role = forms.ModelChoiceField(
        queryset=Group.objects.all().order_by("name"),
        label="Ruolo",
        widget=SimpleSelect2Widget,
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password", "role"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            primary_group = self.instance.groups.order_by("name").first()
            if primary_group:
                self.fields["role"].initial = primary_group.pk


