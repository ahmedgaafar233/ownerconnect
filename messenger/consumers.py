import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Thread, Message
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        self.room_group_name = f"chat_{self.thread_id}"

        user = self.scope["user"]
        if not user.is_authenticated or not await self.is_valid_member(user, self.thread_id):
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_text = data.get("message", "").strip()
            user = self.scope["user"]

            if message_text:
                msg_obj = await self.save_message(user, self.thread_id, message_text)
                
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "id": msg_obj.id,
                        "message": message_text,
                        "sender": user.fullname or user.phone,
                        "sender_id": user.id,
                        "created_at": msg_obj.created_at.isoformat()
                    }
                )
        except Exception:
            pass

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "id": event["id"],
            "message": event["message"],
            "sender": event["sender"],
            "sender_id": event["sender_id"],
            "created_at": event["created_at"]
        }))

    @database_sync_to_async
    def is_valid_member(self, user, thread_id):
        return Thread.objects.filter(
            id=thread_id, 
            participants=user
        ).exists()

    @database_sync_to_async
    def save_message(self, user, thread_id, text):
        return Message.objects.create(
            thread_id=thread_id,
            sender=user,
            text=text
        )
