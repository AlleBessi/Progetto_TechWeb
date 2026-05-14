from django.apps import AppConfig


class TheatersConfig(AppConfig):
    name = 'apps.theaters'

    def ready(self):
        from . import signals  # noqa: F401
