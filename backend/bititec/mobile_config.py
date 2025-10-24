# mobile_config.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from django.utils.deprecation import MiddlewareMixin

class MobileJWTAuthentication(JWTAuthentication):
    """JWT authentication optimized for mobile"""
    
    def authenticate(self, request):
        header = self.get_header(request)
        
        if header is None:
            # Check for token in query params (for WebSocket)
            token = request.GET.get('token')
            if token:
                return self.authenticate_credentials(token)
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None

        return self.authenticate_credentials(raw_token)

class MobileRequestMiddleware(MiddlewareMixin):
    """Middleware to handle mobile-specific request headers"""
    
    def process_request(self, request):
        # Detect mobile clients
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        request.is_mobile = any(x in user_agent for x in ['expo', 'mobile', 'android', 'ios'])
        
        # Set timeout for mobile requests
        if request.is_mobile:
            request.META['HTTP_X_TIMEOUT'] = '120'  # 2 minutes for mobile