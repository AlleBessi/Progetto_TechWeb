from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm, RegistrationForm


def register(request):
	if request.method == "POST":
		form = RegistrationForm(request.POST)
		if form.is_valid():
			user = form.save(commit=False)
			user.email = form.cleaned_data["email"]
			user.save()
			profile = user.profile
			profile.role = form.cleaned_data.get("role")
			profile.city = form.cleaned_data.get("city", "")
			profile.latitude = form.cleaned_data.get("latitude")
			profile.longitude = form.cleaned_data.get("longitude")
			profile.save()
			profile.interests.set(form.cleaned_data.get("interests"))
			messages.success(request, "Registrazione completata. Ora puoi fare login.")
			return redirect("login")
	else:
		form = RegistrationForm()
	return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
	profile_obj = request.user.profile
	if request.method == "POST":
		form = ProfileForm(request.POST)
		if form.is_valid():
			profile_obj.display_name = form.cleaned_data.get("display_name", "")
			profile_obj.role = form.cleaned_data.get("role")
			profile_obj.city = form.cleaned_data.get("city", "")
			profile_obj.latitude = form.cleaned_data.get("latitude")
			profile_obj.longitude = form.cleaned_data.get("longitude")
			profile_obj.save()
			profile_obj.interests.set(form.cleaned_data.get("interests"))
			messages.success(request, "Profilo aggiornato.")
			return redirect("accounts:profile")
	else:
		form = ProfileForm(
			initial={
				"display_name": profile_obj.display_name,
				"role": profile_obj.role,
				"interests": profile_obj.interests.all(),
				"city": profile_obj.city,
				"latitude": profile_obj.latitude,
				"longitude": profile_obj.longitude,
			}
		)
	return render(request, "accounts/profile.html", {"form": form})
