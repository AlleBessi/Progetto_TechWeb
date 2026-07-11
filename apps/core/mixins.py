from braces.views import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect

from apps.theaters.models import Theater, TheaterAdmin


class ManagerAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Access control mixin for all theater-management views."""

    raise_exception = True

    request: HttpRequest
    kwargs: dict[str, object]

    def get_theater(self) -> Theater:
        """
        Default theater resolver.

        Can be overridden by TheaterScopedMixin or any other mixin
        that knows how to derive the theater.
        """
        theater_id = self.kwargs.get("theater_id")
        if theater_id is None:
            theater_id = get_object_or_404(Theater, auditoriums__pk=auditorium_id).pk

        if theater_id is None:
            raise AttributeError(
                f"{self.__class__.__name__} requires either "
                "a get_theater() implementation or a theater_id or auditorium_id URL kwarg."
            )

        return get_object_or_404(Theater, pk=theater_id)

    def test_func(self, user) -> bool:
        if user.is_superuser:
            return True

        if user.groups.filter(name="admin").exists():
            return True

        return TheaterAdmin.objects.is_admin(user, self.get_theater())


class ClientOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow only users in the 'client' group."""

    request: HttpRequest

    @staticmethod
    def raise_exception(request: HttpRequest):
        """Generic access-denied message instead of a bare 403."""
        messages.info(request, "Non hai accesso a questa funzionalità.")
        return redirect("core:home")

    def test_func(self, user) -> bool:
        return user.groups.filter(name="client").exists()