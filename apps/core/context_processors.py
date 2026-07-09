def navigation_context(request):
	user = getattr(request, "user", None)
	is_authenticated = bool(user and user.is_authenticated)
	is_admin = bool(is_authenticated and (user.is_superuser or user.groups.filter(name="admin").exists()))
	is_artist = bool(is_authenticated and user.groups.filter(name="artist").exists())
	is_manager = bool(is_authenticated and user.groups.filter(name="manager").exists())
	# Any manager (or admin) sees the "Gestione teatri" menu, even when not yet
	# assigned to a theater; access to individual theaters is enforced in the views
	# via Theater.objects.accessible_by(user).
	is_theater_admin = bool(is_authenticated and (is_admin or is_manager))

	return {
		"is_admin": is_admin,
		"is_artist": is_artist,
		"is_manager": is_manager,
		"is_theater_admin": is_theater_admin,
		"can_access_dashboard": is_authenticated and (is_admin or is_manager),
		"can_book": is_authenticated and (is_admin or (not is_artist and not is_manager and not is_theater_admin)),
	}
