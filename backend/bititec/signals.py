from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import ChatGroup

User = get_user_model()

# Global chat ID - use a consistent UUID
GLOBAL_CHAT_ID = "00000000-0000-0000-0000-000000000001"

def get_or_create_global_chat():
    """Get or create the global chat group"""
    try:
        # Try to get by ID first
        global_chat = ChatGroup.objects.get(id=GLOBAL_CHAT_ID)
    except ChatGroup.DoesNotExist:
        # If not exists, create it
        global_chat = ChatGroup.objects.create(
            id=GLOBAL_CHAT_ID,
            name="Global Chat"
        )
    return global_chat

@receiver(post_save, sender=User)
def add_user_to_global_chat(sender, instance, created, **kwargs):
    """Add new users to the global chat group"""
    if created:  # Only for newly created users
        global_chat = get_or_create_global_chat()
        global_chat.members.add(instance)