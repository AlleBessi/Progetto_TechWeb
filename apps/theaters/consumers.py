import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


class OccupancyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get the performance id from the URL
        self.performance_id = self.scope['url_route']['kwargs']['performance_id']
        self.room_group_name = f'performance_{self.performance_id}'

        # Only theater managers (or superusers) of the owning theater may watch
        # the occupancy dashboard, so we gate the socket like the HTTP page.
        if not await self.user_can_manage():
            await self.close()
            return

        # Subscribe the consumer to the performance group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Remove the consumer when it leaves
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def user_can_manage(self):
        # Imported lazily so importing this module (via asgi.py -> routing.py)
        # does not touch the app registry before the apps are loaded.
        from apps.shows.models import Performance
        from apps.theaters.models import TheaterAdmin

        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            return False

        performance = (
            Performance.objects
            .select_related('auditorium__theater')
            .filter(pk=self.performance_id)
            .first()
        )
        if performance is None:
            return False

        if user.is_superuser:
            return True

        theater = performance.auditorium.theater
        return TheaterAdmin.objects.is_admin(user, theater)

    async def occupancy_update(self, event):
        # We send the update to the client
        await self.send(text_data=json.dumps({
            'type': 'occupancy_update',
            'reserved_seats': event['reserved_seats'],
            'occupancy': event['occupancy'],
        }))
