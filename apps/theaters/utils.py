from .models import TheaterAdmin


def is_theater_admin(user, theater):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return TheaterAdmin.objects.filter(user=user, theater=theater).exists()


def is_any_theater_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return TheaterAdmin.objects.filter(user=user).exists()
