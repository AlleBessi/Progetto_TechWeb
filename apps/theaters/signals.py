from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Hall


@receiver(post_save, sender=Hall)
def create_hall_seats(sender, instance, created, **kwargs):
    if created:
        instance.create_seats()
