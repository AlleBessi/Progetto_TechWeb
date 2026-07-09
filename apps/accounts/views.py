from django.contrib.auth.mixins import LoginRequiredMixin
from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, ListView, UpdateView, DeleteView
from django.contrib.auth.forms import SetPasswordForm

from .forms import AdminUserCreateForm, ProfileForm, RegistrationForm, AdminUserUpdateForm


def _set_user_role_group(user: User, role: Group | str) -> None:
    from apps.theaters.models import TheaterAdmin  # local import avoids circular

    group, _ = Group.objects.get_or_create(
    name=role if isinstance(role, str) else role.name
    )

    user.groups.set([group])

    if group.name != "manager":
        TheaterAdmin.objects.filter(user=user).delete()


def _get_user_primary_group(user: User) -> Group | None:
	return user.groups.order_by("name").first()


class RegisterView(FormView):
	template_name = "accounts/register.html"
	form_class = RegistrationForm
	success_url = reverse_lazy("accounts:login")

	def form_valid(self, form):
		user = form.save(commit=False)
		user.email = form.cleaned_data["email"]
		user.save()
		_set_user_role_group(user, "client")
		messages.success(self.request, "Registrazione completata. Ora puoi fare login.")
		return super().form_valid(form)


class ProfileView(LoginRequiredMixin, FormView):
	template_name = "accounts/profile.html"
	form_class = ProfileForm
	success_url = reverse_lazy("accounts:profile")

	def get_initial(self):
		return {
			"first_name": self.request.user.first_name,
			"last_name": self.request.user.last_name,
			"email": self.request.user.email,
		}

	def form_valid(self, form):
		self.request.user.first_name = form.cleaned_data.get("first_name", "")
		self.request.user.last_name = form.cleaned_data.get("last_name", "")
		self.request.user.email = form.cleaned_data.get("email", "")
		self.request.user.save(update_fields=["first_name", "last_name", "email"])
		messages.success(self.request, "Profilo aggiornato.")
		return super().form_valid(form)


class AdminUserListView(LoginRequiredMixin, GroupRequiredMixin, ListView):
    model = User
    template_name = "accounts/admin_user_list.html"
    context_object_name = "users"
    group_required = ("admin",)
    raise_exception = True

    def get_queryset(self):
        return User.objects.order_by("username")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_rows"] = [
            {"user": user, "role": _get_user_primary_group(user)}
            for user in context["users"]
        ]
        return context


class AdminUserCreateView(LoginRequiredMixin, GroupRequiredMixin, CreateView):
    form_class = AdminUserCreateForm
    template_name = "accounts/admin_user_form.html"
    group_required = ("admin",)
    raise_exception = True

    def form_valid(self, form):
        user = form.save(commit=False)
        user.email = form.cleaned_data["email"]
        user.save()
        _set_user_role_group(user, form.cleaned_data["role"])
        messages.success(self.request, "Utente creato con successo.")
        return redirect("accounts:admin_user_list")


class AdminUserUpdateView(LoginRequiredMixin, GroupRequiredMixin, UpdateView):
    model = User
    form_class = AdminUserUpdateForm
    template_name = "accounts/admin_user_edit_form.html"
    pk_url_kwarg = "user_id"
    group_required = ("admin",)
    raise_exception = True

    def form_valid(self, form):
        user = form.save()
        _set_user_role_group(user, form.cleaned_data["role"])
        messages.success(self.request, "Utente aggiornato.")
        return redirect("accounts:admin_user_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target_user"] = self.object
        return context


class AdminUserDeleteView(LoginRequiredMixin, GroupRequiredMixin, DeleteView):
    model = User
    pk_url_kwarg = "user_id"
    group_required = ("admin",)
    raise_exception = True

    def post(self, request,  *args, **kwargs):
        target = self.get_object()
        if target == request.user:
            messages.error(request, "Non puoi eliminare il tuo account.")
            return redirect("accounts:admin_user_list")
        target.delete()
        messages.success(request, "Utente eliminato.")
        return redirect("accounts:admin_user_list")
    

class AdminUserSetPasswordView(LoginRequiredMixin, GroupRequiredMixin, FormView):
    form_class = SetPasswordForm
    template_name = "accounts/admin_user_set_password.html"
    group_required = ("admin",)
    raise_exception = True

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.target_user = get_object_or_404(User, pk=kwargs["user_id"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.target_user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, f"Password aggiornata per {self.target_user.username}.")
        return redirect("accounts:admin_user_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target_user"] = self.target_user
        return context