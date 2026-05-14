from apps.theaters.utils import is_any_theater_admin


def booking_permissions(request):
    is_admin = is_any_theater_admin(request.user)
    is_artist = bool(
        request.user.is_authenticated
        and hasattr(request.user, "profile")
        and request.user.profile.role
        and request.user.profile.role.name == "artist"
    )
    return {
        "is_theater_admin": is_admin,
        "is_artist": is_artist,
        "can_book": request.user.is_authenticated and not is_admin and not is_artist,
    }
