from django.urls import path

from . import consumers

ws_urlpatterns = [
    path("ws/theaters/performance/<int:performance_id>/", consumers.OccupancyConsumer.as_asgi()),
]
