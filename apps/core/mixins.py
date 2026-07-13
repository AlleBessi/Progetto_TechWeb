"""Centralized access-control and user-filtering mixins.

Every mixin that gates a view or filters users/querysets by group lives here so
that the access rules are defined in a single place. django-braces provides the
building blocks (LoginRequiredMixin, GroupRequiredMixin, UserPassesTestMixin) and
we lean on group membership as much as possible.
"""

from braces.views import GroupRequiredMixin, LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect

from apps.theaters.models import Theater, TheaterAdmin


# ---------------------------------------------------------------------------
# Group-based access mixins (built on django-braces GroupRequiredMixin)
# ---------------------------------------------------------------------------
#
# django-braces' ``GroupRequiredMixin`` already grants access to superusers
# automatically (see ``check_membership``), so admins — which are simply
# superusers — pass every group gate without needing to be listed explicitly.

class ArtistRequiredMixin(LoginRequiredMixin, GroupRequiredMixin):
    """Allow the 'artist' group (and superusers)."""

    group_required = "artist"
    raise_exception = True


class TheaterManagerRequiredMixin(LoginRequiredMixin, GroupRequiredMixin):
    """Allow the 'manager' group (and superusers)."""
    
    group_required = "manager"
    raise_exception = False


class ClientOnlyMixin(LoginRequiredMixin, GroupRequiredMixin):
    """Allow only users in the 'client' group (and superusers)."""

    group_required = "client"

    @staticmethod
    def raise_exception(request: HttpRequest):
        """Generic access-denied message instead of a bare 403."""
        messages.info(request, "Non hai accesso a questa funzionalità.")
        return redirect("core:home")


# ---------------------------------------------------------------------------
# Theater-management access + scoping mixins
# ---------------------------------------------------------------------------

class ManagerAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Per-theater object-level access control for theater-management views.

    Combines "is a superuser" OR "assigned as a TheaterAdmin of the resolved
    theater", which cannot be expressed with GroupRequiredMixin alone. Failures
    raise 403 (``raise_exception = True``).

    Note: this is deliberately distinct from
    :class:`TheaterManagerRequiredMixin`, which is a *group-wide* gate (no
    theater scoping) that redirects on failure. Use that one for views with no
    theater in scope; use this one for views scoped to a single theater.
    """

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
            raise AttributeError(
                f"{self.__class__.__name__} requires either "
                "a get_theater() implementation or a theater_id URL kwarg."
            )

        return get_object_or_404(Theater, pk=theater_id)

    def test_func(self, user) -> bool:
        if user.is_superuser:
            return True

        return TheaterAdmin.objects.is_admin(user, self.get_theater())


class TheaterScopedMixin:
    """Resolve and cache the theater from the ``theater_id`` URL kwarg.

    Data-filtering querysets live on the model (``Theater.objects.accessible_by``),
    not here — views call that manager method directly.
    """

    request: HttpRequest
    kwargs: dict[str, object]

    def get_theater(self) -> Theater:
        if not hasattr(self, "_theater_cache"):
            theater_id = self.kwargs.get("theater_id")
            if theater_id is None:
                raise AttributeError("theater_id is required for this view")
            self._theater_cache = get_object_or_404(Theater, pk=theater_id)
        return self._theater_cache


class TheaterManagementContextMixin(TheaterScopedMixin, ManagerAccessMixin):
    """Injects ``theater`` and ``admin_allowed`` into every management view."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)  # type: ignore[attr-defined]
        context.setdefault("theater", self.get_theater())
        context.setdefault("admin_allowed", True)
        return context


