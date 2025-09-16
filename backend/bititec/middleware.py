import json
import time
import hashlib
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .models import LoginAttempt, SecurityEvent
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware(MiddlewareMixin):
    """Enhanced security middleware"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Get client IP
        ip = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Check for suspicious patterns
        if self.is_suspicious_request(request, ip, user_agent):
            return JsonResponse({
                'error': 'Request blocked for security reasons'
            }, status=429)
        
        # Rate limiting for login endpoint
        if request.path == '/api/token/' and request.method == 'POST':
            if self.is_rate_limited(ip):
                return JsonResponse({
                    'error': 'Too many login attempts. Please try again later.'
                }, status=429)
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def is_rate_limited(self, ip):
        """Check if IP is rate limited"""
        cache_key = f"login_attempts_{ip}"
        attempts = cache.get(cache_key, 0)
        
        # Allow 5 attempts per 15 minutes per IP
        if attempts >= 5:
            return True
        
        # Increment attempts
        cache.set(cache_key, attempts + 1, 900)  # 15 minutes
        return False
    
    def is_suspicious_request(self, request, ip, user_agent):
        """Detect suspicious request patterns"""
        suspicious_patterns = [
            'sqlmap',
            'nikto',
            'nmap',
            'burp',
            'scanner',
            'bot',
            'crawler',
        ]
        
        # Check user agent
        user_agent_lower = user_agent.lower()
        for pattern in suspicious_patterns:
            if pattern in user_agent_lower:
                self.log_security_event(request, 'SUSPICIOUS_ACTIVITY', {
                    'reason': f'Suspicious user agent: {pattern}',
                    'user_agent': user_agent
                })
                return True
        
        # Check for common attack paths
        suspicious_paths = [
            '/admin',
            '/wp-admin',
            '/phpMyAdmin',
            '/.env',
            '/config',
        ]

        if request.path.startswith('/admin/'):
            return False
        
        for path in suspicious_paths:
            if path in request.path:
                self.log_security_event(request, 'SUSPICIOUS_ACTIVITY', {
                    'reason': f'Access to suspicious path: {path}'
                })
                return True
        
        return False
    
    def log_security_event(self, request, event_type, details=None):
        """Log security events"""
        try:
            SecurityEvent.objects.create(
                event_type=event_type,
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details=details or {}
            )
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")

class APISecurityMiddleware(MiddlewareMixin):
    """API-specific security measures"""
    
    def process_request(self, request):
        # Only apply to API endpoints
        if not request.path.startswith('/api/'):
            return None
        
        # Check for required security headers
        if not self.has_required_headers(request):
            return JsonResponse({
                'error': 'Missing required security headers'
            }, status=400)
        
        # Validate request signature (implement your own logic)
        if not self.validate_request_signature(request):
            return JsonResponse({
                'error': 'Invalid request signature'
            }, status=401)
        
        return None
    
    def has_required_headers(self, request):
        """Check for required security headers"""
        required_headers = [
            'HTTP_USER_AGENT',
            'HTTP_ACCEPT',
        ]
        
        for header in required_headers:
            if not request.META.get(header):
                return False
        return True
    
    def validate_request_signature(self, request):
        """Validate request signature - implement your own logic"""
        # This is a placeholder - implement your signature validation
        # For now, we'll just return True
        return True
    
    def process_response(self, request, response):
        """Add security headers to API responses"""
        if request.path.startswith('/api/'):
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response

class RequestFingerprintingMiddleware(MiddlewareMixin):
    """Generate unique fingerprints for requests"""
    
    def process_request(self, request):
        # Generate request fingerprint
        fingerprint_data = {
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            'accept_encoding': request.META.get('HTTP_ACCEPT_ENCODING', ''),
            'ip': self.get_client_ip(request),
        }
        
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_data, sort_keys=True).encode()
        ).hexdigest()
        
        request.fingerprint = fingerprint
        return None
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

# utils.py - Security utilities
import secrets
import string
from django.core.cache import cache
from django.conf import settings

class SecurityUtils:
    @staticmethod
    def generate_secure_token(length=32):
        """Generate a secure random token"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def is_ip_blocked(ip_address):
        """Check if IP is in blocklist"""
        cache_key = f"blocked_ip_{ip_address}"
        return cache.get(cache_key, False)
    
    @staticmethod
    def block_ip(ip_address, duration_minutes=60):
        """Block IP for specified duration"""
        cache_key = f"blocked_ip_{ip_address}"
        cache.set(cache_key, True, duration_minutes * 60)
    
    @staticmethod
    def get_failed_attempts_count(identifier, attempt_type='login'):
        """Get failed attempts count for identifier"""
        cache_key = f"{attempt_type}_attempts_{identifier}"
        return cache.get(cache_key, 0)
    
    @staticmethod
    def increment_failed_attempts(identifier, attempt_type='login', max_attempts=5, lockout_duration=900):
        """Increment failed attempts and return if locked out"""
        cache_key = f"{attempt_type}_attempts_{identifier}"
        attempts = cache.get(cache_key, 0) + 1
        
        if attempts >= max_attempts:
            # Lock out for specified duration
            cache.set(cache_key, attempts, lockout_duration)
            return True, attempts
        else:
            # Set shorter expiry for ongoing attempts
            cache.set(cache_key, attempts, 300)  # 5 minutes
            return False, attempts
    
    @staticmethod
    def reset_failed_attempts(identifier, attempt_type='login'):
        """Reset failed attempts counter"""
        cache_key = f"{attempt_type}_attempts_{identifier}"
        cache.delete(cache_key)

class MobileUploadMiddleware:
    """Middleware to optimize requests for mobile uploads"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Pre-process mobile upload requests
        if self.is_upload_request(request) and self.is_mobile_request(request):
            # Increase timeout for mobile uploads
            request.META['HTTP_X_UPLOAD_TIMEOUT'] = '120'  # 2 minutes
            
            # Set mobile-friendly content length limit
            request.META['CONTENT_LENGTH_LIMIT'] = str(8 * 1024 * 1024)  # 8MB
        
        response = self.get_response(request)
        
        # Post-process mobile responses
        if self.is_mobile_request(request):
            # Add mobile-friendly headers
            response['X-Mobile-Optimized'] = 'true'
            response['Cache-Control'] = 'no-cache, no-store'  # Prevent caching issues on mobile
        
        return response
    
    def is_upload_request(self, request):
        """Check if this is an upload request"""
        return (
            request.method == 'POST' and
            request.content_type and
            request.content_type.startswith('multipart/form-data')
        )
    
    def is_mobile_request(self, request):
        """Detect mobile requests"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        mobile_indicators = ['mobile', 'android', 'iphone', 'ipad']
        return any(indicator in user_agent for indicator in mobile_indicators)