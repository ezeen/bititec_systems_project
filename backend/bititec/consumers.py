import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.groups = set()  # Track groups user has joined
        
        # Add user to personal notification group
        if self.user.is_authenticated:
            self.notification_group_name = f'user_notifications_{self.user.id}'
            await self.channel_layer.group_add(
                self.notification_group_name,
                self.channel_name
            )
            self.groups.add(self.notification_group_name)
        
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to chat server'
        }))

    async def disconnect(self, close_code):
        # Remove from all groups
        for group in self.groups:
            await self.channel_layer.group_discard(
                group,
                self.channel_name
            )
        self.groups.clear()

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'join_chat_group':
                group_id = text_data_json.get('group_id')
                if group_id:
                    self.chat_group_name = f'chat_{group_id}'
                    await self.channel_layer.group_add(
                        self.chat_group_name,
                        self.channel_name
                    )
                    self.groups.add(self.chat_group_name)
                    
                    # Send confirmation
                    await self.send(text_data=json.dumps({
                        'type': 'group_joined',
                        'group_id': group_id
                    }))
                    
            elif message_type == 'leave_chat_group':
                group_id = text_data_json.get('group_id')
                if group_id:
                    chat_group_name = f'chat_{group_id}'
                    await self.channel_layer.group_discard(
                        chat_group_name,
                        self.channel_name
                    )
                    self.groups.discard(chat_group_name)
                    
                    # Send confirmation
                    await self.send(text_data=json.dumps({
                        'type': 'group_left',
                        'group_id': group_id
                    }))
                    
            elif message_type == 'ping':
                # Respond to keep-alive messages
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': text_data_json.get('timestamp')
                }))
        
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error: {str(e)}'
            }))

    async def chat_notification(self, event):
        # Send notification to WebSocket
        await self.send(text_data=json.dumps(event))

    async def chat_message(self, event):
        # Send chat message to WebSocket
        await self.send(text_data=json.dumps(event))