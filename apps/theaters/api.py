from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views import View

from apps.core.mixins import ManagerAccessMixin
from apps.theaters.models import Auditorium

class AuditoriumZonesAPI(ManagerAccessMixin, View):
    """
    GET /theaters/api/auditoriums/<auditorium_id>/zones/

    Returns the zones for a given auditorium so the performance form can
    rebuild the price fields on the client when the auditorium changes.

    Access rules mirror PerformanceFormBase.test_func:
      - must be authenticated
      - superuser OR a TheaterAdmin for the theater that owns the auditorium
    """

    auditorium: Auditorium

    def get_auditorium(self) -> Auditorium:
        if not hasattr(self, "auditorium"):
            self.auditorium = get_object_or_404(
                Auditorium.objects.select_related("theater"),
                pk=self.kwargs["auditorium_id"],
            )
        return self.auditorium

    def get_theater(self):
        return self.get_auditorium().theater

    def get(self, request, auditorium_id):
        auditorium = self.get_auditorium()

        zones = [
                {"id": zone.pk, "code": str(zone.cod_zone), "label": zone.zone}
            for zone in getattr(auditorium, "zones").order_by("order", "id")
        ]
        return JsonResponse({"auditorium_id": auditorium_id, "zones": zones})
