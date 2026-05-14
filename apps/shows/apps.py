from django.apps import AppConfig


class ShowsConfig(AppConfig):
    name = 'apps.shows'

    def ready(self):
        from . import signals  # noqa: F401
