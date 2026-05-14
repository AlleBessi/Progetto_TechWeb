from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.theaters.models import (
    ZONE_BALCONATA,
    ZONE_CHOICES,
    ZONE_GALLERIA,
    ZONE_LOGGIONE,
    ZONE_LATERALE,
    ZONE_PLATEA,
    ZONE_VIP,
)

from .models import Performance, PerformanceZonePrice

ZONE_MULTIPLIERS = {
    ZONE_PLATEA: Decimal("1.00"),
    ZONE_GALLERIA: Decimal("0.85"),
    ZONE_LOGGIONE: Decimal("0.70"),
    ZONE_BALCONATA: Decimal("0.75"),
    ZONE_LATERALE: Decimal("0.90"),
    ZONE_VIP: Decimal("1.40"),
}


@receiver(post_save, sender=Performance)
def create_zone_prices(sender, instance, created, **kwargs):
    if not created and instance.zone_prices.exists():
        return
    zones = list(instance.hall.zones.values_list("zone", flat=True))
    if not zones:
        zones = [zone for zone, _label in ZONE_CHOICES]
    base_price = Decimal(str(instance.base_price))
    for zone in zones:
        multiplier = ZONE_MULTIPLIERS.get(zone, Decimal("1.00"))
        price = (base_price * multiplier).quantize(Decimal("0.01"))
        PerformanceZonePrice.objects.get_or_create(
            performance=instance,
            zone=zone,
            defaults={"price": price},
        )
