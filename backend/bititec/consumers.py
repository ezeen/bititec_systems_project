import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.groups = set()
        
        logger.info(f"WebSocket connection attempt from user: {getattr(self.user, 'email', 'Anonymous')}")
        
        # Check if user is authenticated
        if not self.user or not self.user.is_authenticated:
            logger.warning("WebSocket connection rejected: User not authenticated")
            await self.close(code=4001)  # Custom close code for authentication failure
            return
        
        logger.info(f"WebSocket connection accepted for user: {self.user.email}")
        
        # Accept the connection first
        await self.accept()
        
        try:
            # Add user to personal notification group
            self.notification_group_name = f'user_notifications_{self.user.id}'
            await self.channel_layer.group_add(
                self.notification_group_name,
                self.channel_name
            )
            self.groups.add(self.notification_group_name)
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': f'Connected to chat server',
                'user_id': str(self.user.id),
                'user_email': self.user.email,
                'timestamp': timezone.now().isoformat()
            }))
        except Exception as e:
            logger.error(f"Error during connection setup: {e}")
            await self.close(code=1011)  # Internal error

    async def disconnect(self, close_code):
        user_email = getattr(self.user, 'email', 'Unknown') if self.user else 'Unknown'
        logger.info(f"WebSocket disconnected for user: {user_email} with code: {close_code}")
        
        # Remove from all groups
        for group in list(self.groups):  # Create a copy to avoid modification during iteration
            try:
                await self.channel_layer.group_discard(group, self.channel_name)
                logger.debug(f"Removed user from group: {group}")
            except Exception as e:
                logger.error(f"Error removing user from group {group}: {e}")
        
        self.groups.clear()

    async def receive(self, text_data):
        if not self.user or not self.user.is_authenticated:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'User not authenticated'
            }))
            return

        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            logger.debug(f"Received message type: {message_type} from user: {self.user.email}")
            
            if message_type == 'join_chat_group':
                await self.handle_join_chat_group(text_data_json)
            elif message_type == 'leave_chat_group':
                await self.handle_leave_chat_group(text_data_json)
            elif message_type == 'ping':
                await self.handle_ping(text_data_json)
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received from user: {self.user.email}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Error processing message from user {self.user.email}: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Server error: {str(e)}'
            }))

    async def handle_join_chat_group(self, data):
        group_id = data.get('group_id')
        if not group_id:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'group_id is required'
            }))
            return

        # Verify user has access to this group
        has_access = await self.verify_group_access(group_id)
        if not has_access:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Access denied to chat group'
            }))
            return

        chat_group_name = f'chat_{group_id}'
        try:
            await self.channel_layer.group_add(chat_group_name, self.channel_name)
            self.groups.add(chat_group_name)
            
            logger.info(f"User {self.user.email} joined chat group {group_id}")
            
            await self.send(text_data=json.dumps({
                'type': 'group_joined',
                'group_id': group_id,
                'message': f'Successfully joined chat group'
            }))
        except Exception as e:
            logger.error(f"Error joining group {group_id}: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to join chat group'
            }))

    async def handle_leave_chat_group(self, data):
        group_id = data.get('group_id')
        if not group_id:
            return

        chat_group_name = f'chat_{group_id}'
        try:
            await self.channel_layer.group_discard(chat_group_name, self.channel_name)
            self.groups.discard(chat_group_name)
            
            logger.info(f"User {self.user.email} left chat group {group_id}")
            
            await self.send(text_data=json.dumps({
                'type': 'group_left',
                'group_id': group_id
            }))
        except Exception as e:
            logger.error(f"Error leaving group {group_id}: {e}")

    async def handle_ping(self, data):
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': data.get('timestamp'),
            'server_time': timezone.now().isoformat()
        }))

    @database_sync_to_async
    def verify_group_access(self, group_id):
        """Verify that the user has access to the specified chat group"""
        try:
            from .models import ChatGroup
            group = ChatGroup.objects.get(id=group_id)
            is_member = self.user in group.members.all()
            logger.debug(f"User {self.user.email} access to group {group_id}: {is_member}")
            return is_member
        except ChatGroup.DoesNotExist:
            logger.error(f"Chat group {group_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error verifying group access: {e}")
            return False

    # Event handlers for channel layer messages
    async def chat_notification(self, event):
        """Send notification to WebSocket"""
        try:
            await self.send(text_data=json.dumps(event))
        except Exception as e:
            logger.error(f"Error sending chat notification: {e}")

    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        try:
            await self.send(text_data=json.dumps(event))
        except Exception as e:
            logger.error(f"Error sending chat message: {e}")