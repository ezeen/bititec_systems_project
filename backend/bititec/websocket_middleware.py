from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from jwt import decode as jwt_decode
from django.conf import settings
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from urllib.parse import parse_qs
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

@database_sync_to_async
def get_user_by_email(email):
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        logger.error(f"User with email {email} not found")
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT tokens
    """
    def __init__(self, inner):
        super().__init__(inner)

    async def __call__(self, scope, receive, send):
        # Close old database connections to prevent usage of timed out connections
        close_old_connections()

        # Only process websocket connections
        if scope["type"] != "websocket":
            scope["user"] = AnonymousUser()
            return await super().__call__(scope, receive, send)

        # Get the token from query string
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            try:
                # Validate the token
                UntypedToken(token)
                
                # Decode the token to get user info
                decoded_data = jwt_decode(
                    token,
                    settings.SECRET_KEY,
                    algorithms=["HS256"]
                )
                
                # Extract user email from token
                user_email = decoded_data.get("email")
                if user_email:
                    user = await get_user_by_email(user_email)
                    scope["user"] = user
                    logger.info(f"WebSocket authenticated user: {user_email}")
                else:
                    scope["user"] = AnonymousUser()
                    logger.warning("No email found in JWT token")
                    
            except (InvalidToken, TokenError) as e:
                logger.error(f"Invalid JWT token: {e}")
                scope["user"] = AnonymousUser()
            except Exception as e:
                logger.error(f"JWT token validation error: {e}")
                scope["user"] = AnonymousUser()
        else:
            logger.warning("No token provided in WebSocket connection")
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)

def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)