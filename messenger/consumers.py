import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Thread, Message
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        self.room_group_name = f'chat_{self.thread_id}'

        # Verify user belongs to thread and the thread matches the user's resort
        user = self.scope["user"]
        if not user.is_authenticated or not await self.is_valid_member(user, self.thread_id):
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = data.get('message', '')
        user = self.scope["user"]

        if message_text:
            # Save message to database
            msg_obj = await self.save_message(user, self.thread_id, message_text)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_text,
                    'sender': user.fullname or user.phone,
                    'sender_id': user.id,
                    'created_at': msg_obj.created_at.strftime('%H:%M')
                }
            )

    # Receive message from room group
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'sender_id': event['sender_id'],
            'created_at': event['created_at']
        }))

    @database_sync_to_async
    def is_valid_member(self, user, thread_id):
        # Must be participant of thread AND thread must belong to user's resort
        # AND user must NOT be a SuperAdmin/Owner in the staff chat context
        if user.role in [User.Role.SUPERADMIN, User.Role.OWNER]:
            return False
            
        return Thread.objects.filter(
            id=thread_id, 
            participants=user,
            resort=user.resort
        ).exists()

    @database_sync_to_async
    def save_message(self, user, thread_id, text):
        return Message.objects.create(
            thread_id=thread_id,
            sender=user,
            text=text
        )
