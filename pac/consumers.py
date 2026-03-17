import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

class PlainteConsumer(AsyncWebsocketConsumer):
    """
    Consumer pour les admins/DCN : reçoit TOUTES les notifications de plaintes.
    Group name : 'plaintes_global'
    """

    async def connect(self):
        self.user = self.scope.get("user")

        # Vérification authentification
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Vérification rôle (admin ou DCN uniquement)
        is_authorized = await self.check_admin_or_dcn(self.user)
        if not is_authorized:
            await self.close(code=4003)
            return

        self.group_name = "plaintes_global"

        # Rejoindre le groupe
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

        # Message de confirmation
        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connecté aux notifications de plaintes."
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    # Reçoit un message du groupe → l'envoie au WebSocket client
    async def plainte_notification(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    @database_sync_to_async
    def check_admin_or_dcn(self, user):
        return user.is_staff or getattr(user, 'role', None) in ['ADMIN', 'DCN']


class PlainteUserConsumer(AsyncWebsocketConsumer):
    """
    Consumer pour un utilisateur PUBLIC : reçoit uniquement ses propres notifications.
    Group name : 'plaintes_user_{user_id}'
    """

    async def connect(self):
        self.user = self.scope.get("user")
        self.user_id = self.scope['url_route']['kwargs']['user_id']

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # L'utilisateur ne peut écouter que son propre canal
        if str(self.user.id) != str(self.user_id):
            await self.close(code=4003)
            return

        self.group_name = f"plaintes_user_{self.user_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connection_established",
            "message": "Connecté à vos notifications personnelles."
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def plainte_notification(self, event):
        await self.send(text_data=json.dumps(event["data"]))