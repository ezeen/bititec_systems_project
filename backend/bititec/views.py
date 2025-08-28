from asyncio.log import logger
from django.core.cache import cache
import hashlib
import os
import time
import logging
import re
import secrets
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, filters, viewsets
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response

from .middleware import SecurityUtils
from .models import Accessory, AccessoryType, ChatGroup, ChatMessage, Client, ClientMachine, CustomUser, Delivery, LeaseAccInquiry, LeaseContract, LeasePartInquiry, LoginAttempt, MachineType, Machine, MeterReading, PartType, Part, KeyAudit, Quotation, Sale, SaleItem, SecurityEvent, Store, Call, ServiceCallToken, StoreInquiry, Transfer, TransferItem
from .serializers import AccessorySerializer, AccessoryTypeSerializer, CallSerializer, ChatGroupSerializer, ChatMessageSerializer, ClientMachineSerializer, ClientSerializer, CustomTokenObtainPairSerializer, DeliverySerializer, LeaseAccInquirySerializer, LeaseContractSerializer, LeasePartInquirySerializer, MachineSerializer, MachineTypeSerializer, MeterReadingSerializer, PartSerializer, PartTypeSerializer, QuotationSerializer, SaleSerializer, StoreInquirySerializer, TransferSerializer, UserSerializer, RegisterSerializer, StoreSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.views import APIView
from django.db.models import Q, Count, Max, Prefetch, Sum
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import update_session_auth_hash
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.hashers import check_password
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.middleware.csrf import get_token
from rest_framework import permissions, viewsets
from django.template.loader import render_to_string
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def get_salt(request):
    email = request.data.get('email', '').lower().strip()
    
    if not email:
        return Response({'error': 'Email is required'}, status=400)
    
    try:
        user = CustomUser.objects.get(email=email)
        salt = secrets.token_hex(32)
        
        # Store user info for later verification
        cache_key = f"login_salt_{email}_{salt}"
        cache.set(cache_key, {
            'created_at': timezone.now().isoformat(),
            'user_exists': True,
            'user_id': str(user.id)  # Store user ID instead of password hash
        }, 300)
        
        return Response({'salt': salt})
    
    except CustomUser.DoesNotExist:
        # Return dummy salt as before
        dummy_salt = secrets.token_hex(32)
        cache_key = f"login_salt_{email}_{dummy_salt}"
        cache.set(cache_key, {
            'created_at': timezone.now().isoformat(),
            'user_exists': False
        }, 300)
        
        return Response({'salt': dummy_salt})
    
def simple_iterative_hash(password, salt, iterations=10000):
    """Simple iterative hash matching frontend implementation"""
    hash_value = password + salt
    for _ in range(iterations):
        hash_value = hashlib.sha256(hash_value.encode()).hexdigest()
    return hash_value

def simple_iterative_hash(password, salt, iterations=10000):
    """Simple iterative hash matching frontend implementation"""
    hash_value = password + salt
    for _ in range(iterations):
        hash_value = hashlib.sha256(hash_value.encode()).hexdigest()
    return hash_value

class SecureTokenObtainPairView(APIView):
    """Enhanced token obtain view with security measures"""
    permission_classes = [AllowAny]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        ip_address = self.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        email = request.data.get('email', '').lower().strip()
        salt = request.data.get('salt', '')

        # Fallback to plaintext password (deprecated, log warning)
        plaintext_password = request.data.get('password', '')

        # Validate required fields
        if not email:
            return Response({
                'error': 'Email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # DISABLED: IP blocking check
        # if SecurityUtils.is_ip_blocked(ip_address):
        #     return Response({
        #         'error': 'Your IP address has been temporarily blocked due to suspicious activity'
        #     }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # DISABLED: Rate limiting per IP
        # is_locked, attempts = SecurityUtils.increment_failed_attempts(
        #     ip_address, 'ip_login', max_attempts=10, lockout_duration=1800  # 30 minutes
        # )
        
        # if is_locked:
        #     SecurityUtils.block_ip(ip_address, 60)  # Block IP for 1 hour
        #     return Response({
        #         'error': 'Too many failed attempts from your IP address'
        #     }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Check if user exists and validate
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            # Log attempt for non-existent user
            self.log_login_attempt(ip_address, email, False, user_agent, 'User not found')
            time.sleep(0.5)
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if account is locked
        if user.is_locked():
            self.log_security_event(
                user, 'LOGIN_FAILED', ip_address, user_agent,
                {'reason': 'Account locked'}
            )
            return Response({
                'error': 'Account is temporarily locked due to multiple failed login attempts'
            }, status=status.HTTP_423_LOCKED)
        
        # Check account status
        if not user.active:
            self.log_login_attempt(ip_address, email, False, user_agent, 'Inactive account')
            return Response({
                'error': 'Account is not active. Please contact administrator.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Password validation - handle both hashed and plaintext
        if not check_password(plaintext_password, user.password):
            user.increment_failed_login()
            self.log_security_event(user, 'LOGIN_FAILED', ip_address, user_agent, {'reason': 'Invalid password'})
            time.sleep(0.5)
            return Response({'error': 'Invalid credentials'}, status=401)

        # DISABLED: Salt validation — prevent replay and fake accounts
        # cache_key = f"login_salt_{email}_{salt}"
        # salt_data = cache.get(cache_key)
        # if not salt_data:
        #     self.log_security_event(user, 'SECURITY_VIOLATION', ip_address, user_agent, {'reason': 'Missing or expired salt'})
        #     return Response({'error': 'Security validation failed.'}, status=401)
        # if not salt_data.get('user_exists', False):
        #     self.log_security_event(None, 'ENUMERATION_ATTEMPT', ip_address, user_agent, {'email': email})
        #     return Response({'error': 'Invalid credentials'}, status=401)

        # DISABLED: Remove used salt
        # cache.delete(cache_key)

        # All good – issue token
        try:
            refresh = RefreshToken.for_user(user)
            # user.reset_failed_login_attempts()
            # SecurityUtils.reset_failed_attempts(ip_address, 'ip_login')

            self.log_security_event(user, 'LOGIN_SUCCESS', ip_address, user_agent)

            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'firstname': user.firstname,
                    'lastname': user.lastname,
                    'role': user.role,
                    'active': user.active
                },
                'security': {
                    'session_id': self.generate_session_token(),
                    'login_time': timezone.now().isoformat(),
                    'authentication_method': 'plaintext'
                }
            }, status=200)

        except Exception as e:
            logger.error("Token generation error: %s", e)
            return Response({'error': 'Login failed.'}, status=500)
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
    
    def generate_session_token(self):
        """Generate a secure session token"""
        return SecurityUtils.generate_secure_token()
    
    def log_login_attempt(self, ip_address, email, success, user_agent, reason=None):
        """Log login attempt"""
        try:
            LoginAttempt.objects.create(
                ip_address=ip_address,
                email=email,
                success=success,
                user_agent=user_agent
            )
        except Exception as e:
            logger.error(f"Failed to log login attempt: {e}")
    
    def log_security_event(self, user, event_type, ip_address, user_agent, details=None):
        """Log security event"""
        try:
            SecurityEvent.objects.create(
                user=user,
                event_type=event_type,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details or {}
            )
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")


class UserListCreate(generics.ListCreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        role = self.request.query_params.get('role')
        if role:
            return CustomUser.objects.filter(role=role)
        return CustomUser.objects.all()


class UserRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'id'

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated()]
        elif self.request.method in ['PUT', 'PATCH']:
            return [IsAuthenticated()]  # Add custom logic in perform_update
        else:  # DELETE
            return [IsAuthenticated()]  # Add custom logic in perform_destroy

    def perform_update(self, serializer):
        # Allow Directors/Super Admins to edit any user, others only themselves
        if not (self.request.user.role in ['Director', 'Super Admin'] or 
                serializer.instance == self.request.user):
            raise PermissionDenied("You can only update your own profile")
        serializer.save()

    def perform_destroy(self, instance):
        # Only Directors/Super Admins can delete users
        if self.request.user.role not in ['Director', 'Super Admin']:
            raise PermissionDenied("You don't have permission to delete users")
        instance.delete()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Get current user with security context"""
    user = request.user
    
    # Check for suspicious activity
    ip_address = get_client_ip(request)
    
    # Add security context to response
    user_data = {
        'id': str(user.id),
        'email': user.email,
        'firstname': user.firstname,
        'lastname': user.lastname,
        'role': user.role,
        'active': user.active,
        'security': {
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'failed_attempts': user.failed_login_attempts,
            'is_locked': user.is_locked()
        }
    }
    
    return Response(user_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Enhanced password change with security logging"""
    user = request.user
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    if not current_password or not new_password:
        return Response(
            {'detail': 'Both current and new password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not user.check_password(current_password):
        # Log failed password change attempt
        SecurityEvent.objects.create(
            user=user,
            event_type='LOGIN_FAILED',
            ip_address=ip_address,
            user_agent=user_agent,
            details={'reason': 'Failed password change - wrong current password'}
        )
        return Response(
            {'detail': 'Current password is incorrect'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Set new password and save
    user.set_password(new_password)
    user.save()
    
    # Log successful password change
    SecurityEvent.objects.create(
        user=user,
        event_type='PASSWORD_CHANGED',
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    return Response({'detail': 'Password changed successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unlock_account(request):
    """Unlock user account (admin only)"""
    if request.user.role not in ['Director', 'Super Admin']:
        raise PermissionDenied("Only directors and super admins can unlock accounts")
    
    user_id = request.data.get('user_id')
    if not user_id:
        return Response(
            {'error': 'User ID is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        target_user = CustomUser.objects.get(id=user_id)
        target_user.unlock_account()
        
        # Log unlock event
        SecurityEvent.objects.create(
            user=target_user,
            event_type='ACCOUNT_UNLOCKED',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={'unlocked_by': str(request.user.id)}
        )
        
        return Response({'message': 'Account unlocked successfully'})
    
    except CustomUser.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )


def get_client_ip(request):
    """Utility function to get client IP"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

class UserByIdView(generics.RetrieveAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'user_id'

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            "user": UserSerializer(user, context=self.get_serializer_context()).data,
            "message": "User created successfully",
        }, status=status.HTTP_201_CREATED)

class IsDirectorOrSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['Director', 'Super Admin']

class IsInventoryManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'Inventory Manager'

class IsSalesRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['Sales Member', 'Sales Manager']

class IsTechnicianRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['Technician', 'Technician Manager']

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def validate_session(request):
    """Validate session token"""
    try:
        # Get session token from headers
        session_token = request.META.get('HTTP_X_SESSION_TOKEN')
        
        if not session_token:
            return Response({
                'valid': False,
                'error': 'No session token provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # You can add additional validation logic here
        # For now, if the user is authenticated (JWT token is valid), 
        # we'll consider the session valid
        
        user = request.user
        
        # Check if user is still active
        if not user.active:
            return Response({
                'valid': False,
                'error': 'User account is not active'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check if account is locked
        if user.is_locked():
            return Response({
                'valid': False,
                'error': 'Account is locked'
            }, status=status.HTTP_423_LOCKED)
        
        # Log session validation attempt
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        SecurityEvent.objects.create(
            user=user,
            event_type='SESSION_VALIDATED',
            ip_address=ip_address,
            user_agent=user_agent,
            details={'session_token': session_token[:10] + '...'}  # Log partial token for security
        )
        
        return Response({
            'valid': True,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'role': user.role,
                'active': user.active
            }
        })
        
    except Exception as e:
        logger.error(f"Session validation error: {e}")
        return Response({
            'valid': False,
            'error': 'Session validation failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def grant_key_access(request):
    """Grant key access to a user (Directors/Super Admins only)"""
    if request.user.role not in ['Director', 'Super Admin']:
        raise PermissionDenied("Only Directors and Super Admins can grant key access")
    
    user_id = request.data.get('user_id')
    key = request.data.get('key')
    actions = request.data.get('actions', [])
    reason = request.data.get('reason', '')
    
    if not all([user_id, key, actions]):
        return Response(
            {'error': 'user_id, key, and actions are required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate key
    valid_keys = ['inventory', 'sales', 'calls', 'leases', 'clients', 'inquiries']
    if key not in valid_keys:
        return Response(
            {'error': f'Invalid key. Must be one of: {valid_keys}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate actions
    valid_actions = ['read', 'create', 'update', 'delete']
    actions = [a for a in actions if a in valid_actions]
    if not actions:
        return Response(
            {'error': f'Invalid actions. Must include: {valid_actions}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = CustomUser.objects.get(id=user_id)
        
        # Grant key access
        user.grant_key_access(key, actions, request.user, reason)
        
        # Create audit record
        KeyAudit.objects.create(
            user=user,
            key=key,
            actions=actions,
            action_type='GRANTED',
            granted_by=request.user,
            reason=reason
        )
        
        return Response({
            'message': f'Key {key} with actions {actions} granted to {user.email}',
            'user_permissions': user.get_all_permissions()
        })
        
    except CustomUser.DoesNotExist:
        return Response(
            {'error': 'User not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_key_access(request):
    """Revoke key access from a user"""
    if request.user.role not in ['Director', 'Super Admin']:
        raise PermissionDenied("Only Directors and Super Admins can revoke key access")
    
    user_id = request.data.get('user_id')
    key = request.data.get('key')
    
    try:
        user = CustomUser.objects.get(id=user_id)
        
        if not user.has_key_access(key):
            return Response(
                {'error': f'User does not have {key} key access'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Store current actions for audit
        current_actions = user.keys.get(key, [])
        
        user.revoke_key_access(key, request.user)
        
        # Create audit record
        KeyAudit.objects.create(
            user=user,
            key=key,
            actions=current_actions,
            action_type='REVOKED',
            granted_by=request.user,
            reason='Key access revoked'
        )
        
        return Response({
            'message': f'Key {key} revoked from {user.email}',
            'user_permissions': user.get_all_permissions()
        })
        
    except CustomUser.DoesNotExist:
        return Response(
            {'error': 'User not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_key_audit(request, user_id):
    """Get key audit trail for a user"""
    if request.user.role not in ['Director', 'Super Admin']:
        raise PermissionDenied("Only Directors and Super Admins can view key audits")
    
    try:
        user = CustomUser.objects.get(id=user_id)
        audits = KeyAudit.objects.filter(user=user).select_related('granted_by')
        
        audit_data = [{
            'key': audit.key,
            'actions': audit.actions,
            'action_type': audit.action_type,
            'granted_by': audit.granted_by.email if audit.granted_by else None,
            'reason': audit.reason,
            'timestamp': audit.timestamp
        } for audit in audits]
        
        return Response({
            'user': user.email,
            'audit_trail': audit_data
        })
        
    except CustomUser.DoesNotExist:
        return Response(
            {'error': 'User not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Get current user with permissions"""
    user = request.user
    
    # Add permissions context to response
    user_data = {
        'id': str(user.id),
        'email': user.email,
        'firstname': user.firstname,
        'lastname': user.lastname,
        'role': user.role,
        'active': user.active,
        'keys': user.keys,
        'all_permissions': user.get_all_permissions(),
        'security': {
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'failed_attempts': user.failed_login_attempts,
            'is_locked': user.is_locked()
        }
    }
    
    return Response(user_data)

def post(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        "user": UserSerializer(user, context=self.get_serializer_context()).data,
        "message": "User created successfully",
    }, status=status.HTTP_201_CREATED)

class IsDirectorOrSuperAdminOrTechnicianManager(permissions.BasePermission):
    def has_permission(self, request, view):
        user_role = request.user.role.lower() if request.user.role else ''
        return user_role in ['director', 'super admin', 'technician manager']

class IsTechnicianOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        user_role = request.user.role.lower() if request.user.role else ''
        return user_role in ['director', 'super admin', 'technician manager', 'technician']

class IsInventoryManagerOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        user_role = request.user.role.lower() if request.user.role else ''
        return user_role in ['director', 'super admin', 'inventory manager', 'sales manager']

class StoreListCreate(generics.ListCreateAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

class StoreRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def destroy(self, request, *args, **kwargs):
        """
        Override destroy method to prevent deletion of stores with inventory
        """
        instance = self.get_object()
        
        # Check if store has any inventory (machines, parts, accessories)
        machines_count = instance.machines.count()
        parts_count = instance.parts.count()
        accessories_count = instance.accessories.count()
        
        if machines_count > 0 or parts_count > 0 or accessories_count > 0:
            error_message = f"Cannot delete store '{instance.store_name}'. Store contains "
            inventory_items = []
            
            if machines_count > 0:
                inventory_items.append(f"{machines_count} machine(s)")
            if parts_count > 0:
                inventory_items.append(f"{parts_count} part(s)")
            if accessories_count > 0:
                inventory_items.append(f"{accessories_count} accessory(ies)")
                
            error_message += ", ".join(inventory_items) + ". Please remove all inventory items before deleting the store."
            
            return Response(
                {"error": error_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # If no inventory, proceed with deletion
        return super().destroy(request, *args, **kwargs)

class AccessoryTypeListCreate(generics.ListCreateAPIView):
    queryset = AccessoryType.objects.all()
    serializer_class = AccessoryTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class AccessoryTypeRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = AccessoryType.objects.all()
    serializer_class = AccessoryTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class MachineTypeListCreate(generics.ListCreateAPIView):
    queryset = MachineType.objects.all()
    serializer_class = MachineTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class MachineTypeRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = MachineType.objects.all()
    serializer_class = MachineTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class PartTypeListCreate(generics.ListCreateAPIView):
    queryset = PartType.objects.all()
    serializer_class = PartTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class PartTypeRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = PartType.objects.all()
    serializer_class = PartTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class MachineViewSet(viewsets.ModelViewSet):
    serializer_class = MachineSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        # If expanding parts, include their store data
        expand = request.query_params.get('expand', '')
        if 'donated_parts' in expand or 'installed_parts' in expand:
            data = serializer.data
            if 'donated_parts' in expand:
                data['donated_parts'] = PartSerializer(
                    instance.donated_parts.all(),
                    many=True,
                    context={'request': request}
                ).data
            if 'installed_parts' in expand:
                data['installed_parts'] = PartSerializer(
                    instance.installed_parts.all(),
                    many=True,
                    context={'request': request}
                ).data
            return Response(data)
    
        return Response(serializer.data)
    
    def get_queryset(self):
        store_id = self.request.query_params.get('store')
        status = self.request.query_params.get('machine_status')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        queryset = Machine.objects.all()
        
        if store_id:
            queryset = queryset.filter(store=store_id)
        if status:
            queryset = queryset.filter(machine_status=status)
            
        if start_date and end_date:
            try:
                # Parse dates and ensure they are in datetime format
                start = parse_date(start_date)
                end = parse_date(end_date)
                
                if start and end:
                    if start > end:
                        raise ValidationError("End date must be after start date")
                    
                    # Create a query that explicitly filters by created_at date
                    queryset = queryset.filter(created_at__date__gte=start, created_at__date__lte=end)
                    
                    # Debug logging - check the exact SQL query 
                    sql_query = str(queryset.query)

                    sample_data = list(queryset[:5].values('id', 'created_at'))
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid date format. Use YYYY-MM-DD: {str(e)}"
                raise ValidationError(error_msg) from e

        return queryset.order_by('-created_at')
    
    def update(self, request, *args, **kwargs):
        # Handle partial updates properly
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, 
            data=request.data, 
            partial=True  # Ensure partial updates are allowed
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    
class PartViewSet(viewsets.ModelViewSet):
    serializer_class = PartSerializer  
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        part_status = self.request.query_params.get('part_status')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        queryset = Part.objects.prefetch_related(
            Prefetch('leasepartinquiry_set', 
                queryset=LeasePartInquiry.objects.select_related(
                    'lease__client', 'part'
                ).filter(lease__is_active=True)  # Only show active leases
            ),
            Prefetch('saleitem_set', 
                queryset=SaleItem.objects.select_related('sale__client')
            )
        )
        
        store_id = self.request.query_params.get('store')
        if store_id:
            queryset = queryset.filter(store=store_id)
        if part_status:  
            queryset = queryset.filter(part_status=part_status)
            
        if start_date and end_date:
            try:
                # Parse dates and ensure they are in datetime format
                start = parse_date(start_date)
                end = parse_date(end_date)
                
                if start and end:
                    if start > end:
                        raise ValidationError("End date must be after start date")
                    
                    # Using __date correctly for comparing date fields
                    queryset = queryset.filter(created_at__date__gte=start, created_at__date__lte=end)
                    
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid date format. Use YYYY-MM-DD: {str(e)}") from e

        return queryset.order_by('-created_at')
    
class AccessoryViewSet(viewsets.ModelViewSet):
    serializer_class = AccessorySerializer  
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    
    def get_queryset(self):
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        acc_status = self.request.query_params.get('acc_status')
        
        queryset = Accessory.objects.prefetch_related(
            Prefetch('leaseaccinquiry_set', 
                queryset=LeaseAccInquiry.objects.select_related(
                    'lease__client', 'accessory'
                ).filter(lease__is_active=True)  
            ),
            Prefetch('saleitem_set', 
                queryset=SaleItem.objects.select_related('sale__client')
            )
        )
        
        store_id = self.request.query_params.get('store')
        if store_id:
            queryset = queryset.filter(store=store_id)
        if acc_status:  
            queryset = queryset.filter(acc_status=acc_status)
            
        if start_date and end_date:
            try:
                # Parse dates and ensure they are in datetime format
                start = parse_date(start_date)
                end = parse_date(end_date)
                
                if start and end:
                    if start > end:
                        raise ValidationError("End date must be after start date")
                    
                    # Using __date correctly for comparing date fields
                    queryset = queryset.filter(created_at__date__gte=start, created_at__date__lte=end)
                    
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid date format. Use YYYY-MM-DD: {str(e)}") from e

        return queryset.order_by('-created_at')
    
class MachineListCreate(generics.ListCreateAPIView):
    queryset = Machine.objects.all().select_related('store')
    serializer_class = MachineSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['machine_name', 'machine_brand', 'serial_no', 'store__store_name']
    ordering_fields = ['machine_name', 'created_at', 'unit_value']

    def get_queryset(self):
        store_id = self.request.query_params.get('store')
        machine_status = self.request.query_params.get('machine_status')  # Add this line
        queryset = Machine.objects.all()
        
        if store_id:
            queryset = queryset.filter(store=store_id)
        if machine_status:  # Add status filtering
            queryset = queryset.filter(machine_status=machine_status)
            
        return queryset

class MachineRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Machine.objects.all().select_related('store')
    serializer_class = MachineSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class PartListCreate(generics.ListCreateAPIView):
    queryset = Part.objects.all().select_related('store')
    serializer_class = PartSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['part_name', 'part_brand', 'serial_no', 'store__store_name']
    ordering_fields = ['part_name', 'created_at', 'unit_value']

    def get_queryset(self):
        store_id = self.request.query_params.get('store')
        if store_id:
            return Part.objects.filter(store=store_id)
        return Part.objects.all()

class PartRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Part.objects.all().select_related('store')
    serializer_class = PartSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class AccessoryListCreate(generics.ListCreateAPIView):
    queryset = Accessory.objects.all().select_related('store')
    serializer_class = AccessorySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['acc_name', 'acc_brand', 'serial_no', 'store__store_name']
    ordering_fields = ['acc_name', 'created_at', 'unit_value']

    def get_queryset(self):
        store_id = self.request.query_params.get('store')
        if store_id:
            return Accessory.objects.filter(store=store_id)
        return Accessory.objects.all()

class AccessoryRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Accessory.objects.all().select_related('store')
    serializer_class = AccessorySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class ClientListCreate(generics.ListCreateAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['client_name', 'client_location']
    ordering_fields = ['client_name', 'created_at']

class ClientRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class StoreInquiryViewSet(viewsets.ModelViewSet):
    serializer_class = StoreInquirySerializer
    permission_classes = [IsAuthenticated]
    requested_by = UserSerializer(read_only=True)
    lease_part_inquiries = LeasePartInquirySerializer(many=True, read_only=True)
    lookup_field = 'pk'
        
    def get_queryset(self):
        queryset = StoreInquiry.objects.select_related(
            'requested_by', 'issued_by', 'service_call'
        ).prefetch_related('lease_part_inquiries__part')

        service_call = self.request.query_params.get('service_call')
        if service_call:
            return StoreInquiry.objects.filter(service_call=service_call)
        return StoreInquiry.objects.all()
    
    def get_permissions(self):
        """
        Override permissions based on action
        """
        if self.action in ['list', 'retrieve']:
            # Allow all authenticated users to view store inquiries
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['create']:
            # Allow technicians and above to create inquiries
            permission_classes = [permissions.IsAuthenticated, IsTechnicianOrAbove]
        elif self.action in ['update', 'partial_update', 'destroy']:
            # Restrict editing to inventory managers and above
            permission_classes = [permissions.IsAuthenticated, IsInventoryManagerOrAbove]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def update(self, request, *args, **kwargs):
        # Check specific permissions for store inquiry updates
        user = request.user
        user_role = user.role.lower() if user.role else ''
        allowed_roles = ['director', 'super admin', 'inventory manager', 'sales manager']
        
        if user_role not in allowed_roles:
            return Response(
                {'error': 'You do not have permission to update store inquiries'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = request.data.copy()
        
        if 'unit_price' in data:
            try:
                data['unit_price'] = Decimal(str(data['unit_price']))
            except (ValueError, TypeError, InvalidOperation) as e:
                return Response(
                    {'error': 'Invalid unit price format'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

class ClientMachineViewSet(viewsets.ModelViewSet):
    serializer_class = ClientMachineSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        client_name = self.request.query_params.get('client_name')
        client_location = self.request.query_params.get('client_location')
        
        if client_name and client_location:
            return ClientMachine.objects.filter(
                client_name=client_name,
                client_location=client_location
            )
        return ClientMachine.objects.all()

@method_decorator(csrf_exempt, name='dispatch')
class CallViewSet(viewsets.ModelViewSet):
    queryset = Call.objects.all()  
    serializer_class = CallSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        status = self.request.query_params.get('status')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        technician_id = self.request.query_params.get('technician')
        
        queryset = super().get_queryset().select_related(
            'client', 
            'item', 
            'item__store'
        ).prefetch_related('technician')

        # Role-based filtering for different actions
        user = self.request.user
        user_role = user.role.lower() if user.role else ''
        
        # Allow full access to these roles
        allowed_full_access_roles = ['director', 'super admin', 'technician manager']
        
        # For GET requests (viewing), allow all authenticated users to see calls
        if self.action in ['list', 'retrieve']:
            # All authenticated users can view service calls
            pass  # No filtering for view operations
        else:
            # For edit operations (POST, PUT, PATCH, DELETE), apply role restrictions
            if user_role not in allowed_full_access_roles:
                # If user is a technician, only show calls assigned to them for editing
                if user_role == 'technician':
                    queryset = queryset.filter(technician__id=user.id)
                else:
                    # For other roles, show no calls for editing or handle as needed
                    queryset = queryset.none()
        
        # Status filtering
        if status:
            status_mapping = {
                'open': 'Open',
                'pending': 'Pending',
                'in_progress': 'In Progress',
                'complete': 'Complete',
                'completed': 'Completed',
                'closed': 'Closed'
            }
            backend_status = status_mapping.get(status.lower(), status)
            queryset = queryset.filter(status=backend_status)

         # Technician filtering
        if technician_id:
            queryset = queryset.filter(technician__id=technician_id)

        # Date range filtering
        if start_date and end_date:
            try:
                start = parse_date(start_date)
                end = parse_date(end_date)
                
                if start and end:
                    if start > end:
                        raise ValidationError("End date must be after start date")
                    
                    queryset = queryset.filter(
                        created_at__date__gte=start,
                        created_at__date__lte=end
                    )
                    
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid date format. Use YYYY-MM-DD: {str(e)}") from e

        return queryset.order_by('-created_at')
    
    def get_permissions(self):
        """
        Override permissions based on action
        """
        if self.action in ['list', 'retrieve']:
            # Allow all authenticated users to view
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Restrict editing to specific roles
            permission_classes = [permissions.IsAuthenticated, IsDirectorOrSuperAdminOrTechnicianManager]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def update(self, request, *args, **kwargs):
        # Check if user has permission to edit this specific call
        instance = self.get_object()
        user = request.user
        user_role = user.role.lower() if user.role else ''
        
        allowed_full_access_roles = ['director', 'super admin', 'technician manager']
        
        # Check permissions for update
        if user_role not in allowed_full_access_roles:
            if user_role == 'technician':
                # Technicians can only edit calls assigned to them
                if not instance.technician.filter(id=user.id).exists():
                    return Response(
                        {'error': 'You can only edit service calls assigned to you'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                return Response(
                    {'error': 'You do not have permission to edit service calls'}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        
        old_status = instance.status

        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Check if both approvals are true after update
        updated_data = serializer.validated_data
        technician_approval = updated_data.get('technician_manager_approval', instance.technician_manager_approval)
        client_verification = updated_data.get('client_verification', instance.client_verification)
        
        if technician_approval and client_verification:
            updated_data['status'] = 'Closed'
        
        self.perform_update(serializer)
        
        # Add status change info to response
        instance.refresh_from_db()
        response_data = serializer.data
        response_data['status_changed'] = old_status != serializer.instance.status
        response_data['previous_status'] = old_status
        
        return Response(response_data)
    
    @action(detail=True, methods=['post'])
    def start_service(self, request, pk=None):
        """Start service call"""
        call = self.get_object()
        
        # Check permissions
        user = request.user
        user_role = user.role.lower() if user.role else ''
        allowed_roles = ['director', 'super admin', 'technician manager', 'technician']
        
        if user_role not in allowed_roles:
            return Response({'error': 'Permission denied'}, status=403)
        
        if user_role == 'technician' and not call.technician.filter(id=user.id).exists():
            return Response({'error': 'You can only start calls assigned to you'}, status=403)
        
        if call.status != 'Pending':
            return Response({'error': 'Service must be in Pending status to start'}, status=400)
        
        call.status = 'In Progress'
        call.start_time = timezone.now()
        call.save()
        
        serializer = self.get_serializer(call)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete_service(self, request, pk=None):
        """Complete service call"""
        call = self.get_object()
        
        # Check permissions
        user = request.user
        user_role = user.role.lower() if user.role else ''
        allowed_roles = ['director', 'super admin', 'technician manager', 'technician']
        
        if user_role not in allowed_roles:
            return Response({'error': 'Permission denied'}, status=403)
        
        if user_role == 'technician' and not call.technician.filter(id=user.id).exists():
            return Response({'error': 'You can only complete calls assigned to you'}, status=403)
        
        if call.status != 'In Progress':
            return Response({'error': 'Service must be in progress to complete'}, status=400)
        
        call.status = 'Completed'
        call.finish_time = timezone.now()
        call.save()
        
        serializer = self.get_serializer(call)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def create_access_token(self, request, pk=None):
        """
        Create a time-limited token for external users to access a specific service call
        """
        call = self.get_object()
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, status=400)
        
        # Create a new token with 1-hour expiration
        token = ServiceCallToken.objects.create(
            service_call=call,
            email=email,
            expires_at=timezone.now() + timezone.timedelta(hours=1)
        )
        
        # Return the token ID that will be used in the URL
        return Response({
            'token': str(token.id),
            'expires_at': token.expires_at
        })
        
    @action(detail=True, methods=['patch'])
    def update_approval(self, request, pk=None):
        """Dedicated endpoint for approval updates"""
        call = self.get_object()
        field = request.data.get('field')
        value = request.data.get('value')
        old_status = call.status
        
        # Check permissions for approval updates
        user = request.user
        user_role = user.role.lower() if user.role else ''
        
        if field == 'technician_manager_approval':
            # Only managers and above can approve
            if user_role not in ['director', 'super admin', 'technician manager']:
                return Response({'error': 'Permission denied for manager approval'}, status=403)
        
        if field in ['technician_manager_approval', 'client_verification']:
            setattr(call, field, value)
            call.save()  # This will trigger status update
            
        serializer = self.get_serializer(call)
        response_data = serializer.data
        response_data['status_changed'] = old_status != call.status
        response_data['previous_status'] = old_status
        
        return Response(response_data)
    
@method_decorator(csrf_exempt, name='dispatch')
class CallValidateTokenView(APIView):
    """
    Dedicated view for token validation - accessible without authentication
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # Explicitly disable authentication
    
    def options(self, request, *args, **kwargs):
        """Handle preflight CORS requests"""
        response = Response()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'X-Token-Validation, Content-Type, Authorization'
        response['Access-Control-Max-Age'] = '86400'
        return response
    
    def get(self, request, *args, **kwargs):
        """Validate a token and return the associated service call if valid"""
        token_id = request.query_params.get('token')
        
        if not token_id:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Validate UUID format
            if not re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$', token_id):
                return Response({'error': 'Invalid token format'}, status=status.HTTP_400_BAD_REQUEST)
            
            token = ServiceCallToken.objects.select_related('service_call').get(id=token_id)
        except ServiceCallToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=status.HTTP_404_NOT_FOUND)
        
        if not token.is_valid():
            return Response({
                'error': 'Token has expired or has been used',
                'expired': True
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Return the service call data
        call = token.service_call
        serializer = CallSerializer(call)
        data = serializer.data
        
        # Add token validation confirmation
        response_data = {
            'valid': True,
            'serviceCall': data,
            **data  # Flatten the data for easier access
        }
        
        response = Response(response_data)
        response['Access-Control-Allow-Origin'] = '*'
        return response


@method_decorator(csrf_exempt, name='dispatch')
class CallVerifyTokenView(APIView):
    """
    Dedicated view for service call verification - accessible without authentication
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # Explicitly disable authentication
    
    def options(self, request, *args, **kwargs):
        """Handle preflight CORS requests"""
        response = Response()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        response['Access-Control-Max-Age'] = '86400'
        return response
    
    def post(self, request, pk=None, *args, **kwargs):
        """Verify service call completion using token"""
        try:
            call = Call.objects.get(pk=pk)
        except Call.DoesNotExist:
            return Response({'error': 'Service call not found'}, status=status.HTTP_404_NOT_FOUND)
            
        token = request.data.get('token')
        
        if not token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            service_token = ServiceCallToken.objects.get(
                id=token,
                service_call=call,
                is_used=False,
                expires_at__gt=timezone.now()
            )

             # Store old status for comparison
            old_status = call.status
            
            # Update the service call
            call.client_verification = True
            
            # Check if both approvals are now True and auto-complete
            if call.client_verification and call.technician_manager_approval:
                call.status = 'Complete'
            
            call.save()
            
            # Mark token as used
            service_token.is_used = True
            service_token.save()
            
            # Return response with status update info
            response_data = {
                'status': 'verified',
                'service_call_status': call.status,
                'status_changed': old_status != call.status
            }
            
            response = Response(response_data)
            response['Access-Control-Allow-Origin'] = '*'
            return response
            
        except ServiceCallToken.DoesNotExist:
            return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

class LeaseContractViewSet(viewsets.ModelViewSet):
    serializer_class = LeaseContractSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def meter_readings(self, request, pk=None):
        lease = self.get_object()
        readings = lease.meter_readings.all().order_by('-month')
        serializer = MeterReadingSerializer(readings, many=True)
        return Response(serializer.data)
    
    def get_queryset(self):
        # Base queryset with proper relationships
        queryset = LeaseContract.objects.select_related('client', 'item', 'store').prefetch_related('meter_readings')
        
        # Handle search parameter
        search_term = self.request.query_params.get('search')
        if search_term:
            queryset = queryset.filter(
                Q(lease_no__icontains=search_term) |
                Q(client__client_name__icontains=search_term) |
                Q(item__machine_name__icontains=search_term)
            )
        
        # Handle filter parameter (active/inactive/expiring)
        filter_type = self.request.query_params.get('filter', 'active')
        
        if filter_type == 'active':
            queryset = queryset.filter(is_active=True)
        elif filter_type == 'inactive':
            queryset = queryset.filter(is_active=False)
        elif filter_type == 'expiring':
            from datetime import date, timedelta
            today = date.today()
            thirty_days_from_now = today + timedelta(days=30)
            queryset = queryset.filter(
                is_active=True,
                to_date__gte=today,
                to_date__lte=thirty_days_from_now
            )
        
        # Handle client filter
        client_id = self.request.query_params.get('client')
        if client_id:
            queryset = queryset.filter(client=client_id)
        
        return queryset.order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """Override list method to ensure proper response format"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            # If no pagination, return all results
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to fetch leases: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_destroy(self, instance):
        with transaction.atomic():
            # Return machine to store
            if instance.item:
                machine = instance.item
                machine.machine_status = 'Available'
                machine.save()
            
            # Delete lease
            instance.delete()

class LeaseAssignTechnician(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        client_id = request.data.get('client_id')
        technician_id = request.data.get('technician_id')

        if not client_id:
            return Response(
                {"error": "client_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update all leases for this client
        leases = LeaseContract.objects.filter(client_id=client_id)
        updated_count = leases.update(technician_id=technician_id)

        return Response({
            "status": "success",
            "updated_count": updated_count,
            "technician_id": technician_id
        })
    
class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Sale.objects.select_related('client').prefetch_related(
            'items__machine',
            'items__part',
            'items__accessory'
        )
        
        # Apply filters
        client_id = self.request.query_params.get('client')
        client_name = self.request.query_params.get('client_name')
        sale_type = self.request.query_params.get('type')
        
        if client_id:
            queryset = queryset.filter(client=client_id)
        if client_name:
            queryset = queryset.filter(
                Q(client__client_name__icontains=client_name) |
                Q(local_client_name__icontains=client_name)
            )
        if sale_type:
            # Filter through the items' sale_type
            queryset = queryset.filter(items__sale_type=sale_type).distinct()
            
        return queryset.order_by('-created_at')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create sale with proper VAT calculations"""
        print("=== SALE CREATION DEBUG ===")
        print("Request data:", request.data)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        print("Validated data:", serializer.validated_data)
        
        # Create the sale
        sale = serializer.save()
        
        print(f"Created sale totals:")
        print(f"- Subtotal (VAT-exclusive): {sale.subtotal}")
        print(f"- VAT Total: {sale.vat_total}")
        print(f"- Total Amount: {sale.total_amount}")
        print(f"- Add VAT: {sale.add_vat}")
        print(f"- VAT Rate: {sale.vat_rate}")
        
        # Print item details for debugging
        for item in sale.items.all():
            print(f"Item: {item.sale_type} - Unit Price: {item.unit_price}, Qty: {item.quantity}")
            print(f"  - Subtotal: {item.subtotal}")
            print(f"  - VAT Amount: {item.vat_amount}")
            print(f"  - Total Price: {item.total_price}")
        
        # Return the sale with calculated totals
        response_serializer = self.get_serializer(sale)
        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update sale and recalculate VAT"""
        partial = kwargs.pop('partial', True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Save the sale
        sale = serializer.save()
        
        # Recalculate totals after update
        sale.calculate_totals()
        sale.save()
        
        return Response(serializer.data)
    
    def perform_destroy(self, instance):
        """Return items to store before deleting sale"""
        with transaction.atomic():
            
            # Return items to store
            for item in instance.items.all():
                
                if item.machine:
                    machine = item.machine
                    machine.machine_status = 'Available'
                    machine.save()
                    
                elif item.part:
                    part = item.part
                    old_quantity = part.quantity
                    part.quantity += item.quantity
                    if part.quantity > 0 and part.part_status == 'Out of Stock':
                        part.part_status = 'Available'
                    part.save()
                    
                elif item.accessory:
                    accessory = item.accessory
                    old_quantity = accessory.quantity
                    accessory.quantity += item.quantity
                    if accessory.quantity > 0 and accessory.acc_status == 'Out of Stock':
                        accessory.acc_status = 'Available'
                    accessory.save()
                    
            # Delete the sale
            instance.delete()
    
class DeliveryViewSet(viewsets.ModelViewSet):
    queryset = Delivery.objects.all()
    serializer_class = DeliverySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['delivery_no', 'sale__sale_no', 'lease__lease_no']
    ordering_fields = ['delivery_date', 'created_at']

    def get_queryset(self):
        delivery_type = self.request.query_params.get('type')
        queryset = super().get_queryset()
        
        if delivery_type:
            queryset = queryset.filter(delivery_type=delivery_type)
            
        return queryset.select_related(
            'sale__client', 
            'lease__client', 
            'assigned_to'
        ).prefetch_related(
            'sale__items',
            'lease__part_inquiries',
            'lease__acc_inquiries'
        )

    @action(detail=False, methods=['post'])
    def create_delivery(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Handle sale or lease association
            delivery_type = serializer.validated_data['delivery_type']
            if delivery_type == 'Sale':
                if not serializer.validated_data.get('sale'):
                    return Response(
                        {"error": "Sale is required for sale deliveries"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            elif delivery_type == 'Lease':
                if not serializer.validated_data.get('lease'):
                    return Response(
                        {"error": "Lease is required for lease deliveries"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def delivery_types(self, request):
        return Response([
            {'value': 'Sale', 'label': 'Sale Delivery'},
            {'value': 'Lease', 'label': 'Lease Delivery'}
        ])
        
class ChatGroupViewSet(viewsets.ModelViewSet):
    queryset = ChatGroup.objects.all()
    serializer_class = ChatGroupSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Only return chat groups that the user is a member of"""
        user = self.request.user
        
        # Annotate with last message timestamp and unread count
        return ChatGroup.objects.filter(
            members=user
        ).annotate(
            last_message_time=Max('messages__created_at'),
            unread_count=Count(
                'messages', 
                filter=~Q(messages__read_by=user) & ~Q(messages__sender=user)
            )
        ).order_by('-last_message_time')
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get messages for a specific chat group"""
        try:
            group = self.get_queryset().get(pk=pk)
            
            # Get messages with prefetched read_by
            messages = ChatMessage.objects.filter(
                chat_group=group
            ).select_related('sender').prefetch_related('read_by')
            
            # Paginate results if needed
            page = self.paginate_queryset(messages)
            if page is not None:
                serializer = ChatMessageSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = ChatMessageSerializer(messages, many=True)
            return Response(serializer.data)
            
        except ChatGroup.DoesNotExist:
            return Response(
                {"error": "Chat group not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def global_chat(self, request):
        """Get the global chat group"""
        from .signals import GLOBAL_CHAT_ID, get_or_create_global_chat
        
        # Ensure global chat exists and user is a member
        global_chat = get_or_create_global_chat()
        
        # Make sure current user is a member
        if request.user not in global_chat.members.all():
            global_chat.members.add(request.user)
        
        # Annotate with unread count for this user
        queryset = ChatGroup.objects.filter(
            id=global_chat.id
        ).annotate(
            last_message_time=Max('messages__created_at'),
            unread_count=Count(
                'messages', 
                filter=~Q(messages__read_by=request.user) & ~Q(messages__sender=request.user)
            )
        )
        
        group = queryset.first()
        serializer = self.get_serializer(group)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark all messages in a group as read by the current user"""
        try:
            group = self.get_queryset().get(pk=pk)
            user = request.user

            unread_messages = ChatMessage.objects.filter(
                chat_group=group
            ).exclude(
                read_by=user
            )
            
            # Add user to read_by for all these messages
            for message in unread_messages:
                message.read_by.add(user)
            
            return Response({"status": "Messages marked as read"})
            
        except ChatGroup.DoesNotExist:
            return Response(
                {"error": "Chat group not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def create_or_get_direct_chat(self, request):
        """Create or get a direct chat between the current user and another user"""
        other_user_id = request.data.get('user_id')
        
        if not other_user_id:
            return Response(
                {"error": "user_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            other_user = CustomUser.objects.get(id=other_user_id)
            current_user = request.user
            
            # Check if a direct chat already exists
            existing_groups = ChatGroup.objects.annotate(
                member_count=Count('members')
            ).filter(
                member_count=2,
                members=current_user
            ).filter(
                members=other_user
            )
            
            if existing_groups.exists():
                group = existing_groups.first()
            else:
                # Create new direct chat
                group = ChatGroup.objects.create(
                    name=f"Chat with {other_user.firstname} {other_user.lastname}"
                )
                group.members.add(current_user, other_user)
                
            serializer = self.get_serializer(group)
            return Response(serializer.data)
            
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class ChatMessageViewSet(viewsets.ModelViewSet):
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Only return messages from groups the user is a member of"""
        user = self.request.user
        return ChatMessage.objects.filter(
            chat_group__members=user
        ).select_related('sender', 'chat_group')
    
    def perform_create(self, serializer):
        """Set the sender to the current user when creating a message"""
        serializer.save(sender=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a specific message as read"""
        try:
            message = self.get_queryset().get(pk=pk)
            user = request.user
            
            message.read_by.add(user)
            
            # Notify other users in the group
            channel_layer = get_channel_layer()
            
            for member in message.chat_group.members.exclude(id=user.id):
                notification_group = f'user_notifications_{member.id}'
                
                async_to_sync(channel_layer.group_send)(
                    notification_group,
                    {
                        'type': 'chat_notification',
                        'event': 'message_read',
                        'message_id': str(message.id),
                        'user_id': str(user.id),
                        'group_id': str(message.chat_group.id)
                    }
                )
            
            return Response({"status": "Message marked as read"})
            
        except ChatMessage.DoesNotExist:
            return Response(
                {"error": "Message not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class LeasePartInquiryViewSet(viewsets.ModelViewSet):
    serializer_class = LeasePartInquirySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = LeasePartInquiry.objects.select_related(
            'part', 'lease', 'store_inquiry'
        ).all()
        
        # Filter by lease if provided
        lease_id = self.request.query_params.get('lease')
        if lease_id:
            queryset = queryset.filter(lease=lease_id)
            
        # Filter by store_inquiry if provided
        store_inquiry_id = self.request.query_params.get('store_inquiry')
        if store_inquiry_id:
            queryset = queryset.filter(store_inquiry=store_inquiry_id)
            
        return queryset
    
    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            part = instance.part
            
            # Ensure sufficient stock
            if part.quantity < instance.quantity:
                raise serializer.ValidationError(
                    f"Insufficient stock. Only {part.quantity} units available."
                )
            
            # Update part inventory
            part.quantity -= instance.quantity
            part.save()
            
            # Update part status if needed
            if part.quantity == 0:
                part.part_status = 'Out of Stock'
                part.save()

    def perform_update(self, serializer):
        with transaction.atomic():
            old_instance = self.get_object()
            new_data = serializer.validated_data
            new_quantity = new_data.get('quantity', old_instance.quantity)
            new_part = new_data.get('part', old_instance.part)
            
            # Handle part change
            if old_instance.part != new_part:
                # Return original part to inventory
                old_part = old_instance.part
                old_part.quantity += old_instance.quantity
                old_part.save()
                
                # Deduct from new part
                if new_part.quantity < new_quantity:
                    raise serializer.ValidationError(
                        f"Insufficient stock for new part. Only {new_part.quantity} units available."
                    )
                new_part.quantity -= new_quantity
                new_part.save()
            else:
                # Same part, adjust quantity difference
                quantity_diff = new_quantity - old_instance.quantity
                if quantity_diff > 0:  # Increasing quantity
                    if old_instance.part.quantity < quantity_diff:
                        raise serializer.ValidationError(
                            f"Insufficient stock for increase. Only {old_instance.part.quantity} units available."
                        )
                    old_instance.part.quantity -= quantity_diff
                    old_instance.part.save()
                elif quantity_diff < 0:  # Decreasing quantity
                    old_instance.part.quantity += abs(quantity_diff)
                    old_instance.part.save()
            
            # Update the lease part inquiry
            serializer.save()

    def perform_destroy(self, instance):
        with transaction.atomic():
            # Return part to inventory
            part = instance.part
            part.quantity += instance.quantity
            
            # Update status if needed
            if part.quantity > 0 and part.part_status == 'Out of Stock':
                part.part_status = 'Available'
            
            part.save()
            instance.delete()

class LeaseAccInquiryViewSet(viewsets.ModelViewSet):
    serializer_class = LeaseAccInquirySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        lease_id = self.request.query_params.get('lease')
        if lease_id:
            return LeaseAccInquiry.objects.filter(lease=lease_id).select_related('accessory', 'lease')
        return LeaseAccInquiry.objects.all()
    
class MeterReadingViewSet(viewsets.ModelViewSet):
    queryset = MeterReading.objects.all()
    serializer_class = MeterReadingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['lease__lease_no', 'machine__serial_no']
    ordering_fields = ['month', 'created_at']

class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.all()
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        status = self.request.query_params.get('status')
        client_id = self.request.query_params.get('client_id')
        
        queryset = super().get_queryset()
        
        if status:
            queryset = queryset.filter(status=status)
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        
        return queryset.select_related('client', 'created_by').prefetch_related('items')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
class QuotationPDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        quotation = get_object_or_404(Quotation, pk=pk)
        
        # Render HTML template with context
        template = 'quotation_pdf.html'
        context = {'quotation': quotation}
        html = render_to_string(template, context)
        
        # Create PDF response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'filename="quotation_{quotation.quotation_no}.pdf"'
        
        # Generate PDF
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse('PDF generation error', status=500)
        return response
    
class TransferListCreate(generics.ListCreateAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        store_id = self.request.query_params.get('store_id')
        queryset = Transfer.objects.select_related(
            'from_store', 'to_store', 'created_by'
        ).prefetch_related(
            Prefetch('items', queryset=TransferItem.objects.select_related(
                'machine', 'part', 'accessory'
            ).prefetch_related(
                'machine__store',
                'part__store',
                'accessory__store'
            ))
        ).order_by('-created_at')
        
        if store_id:
            return queryset.filter(
                Q(from_store_id=store_id) | Q(to_store_id=store_id)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class TransferRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Prevent updates to completed transfers
        if instance.status == 'Completed':
            return Response(
                {'error': 'Cannot modify completed transfers'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        return super().update(request, *args, **kwargs)

class CompleteTransferView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Transfer.objects.all()
    serializer_class = TransferSerializer
    lookup_field = 'pk'

    def post(self, request, pk):
        transfer = self.get_object()
        logger.info(f"Starting transfer completion for: {transfer.id}")
        
        if transfer.status != 'Pending':
            logger.warning(f"Transfer {transfer.id} is not pending (status: {transfer.status})")
            return Response(
                {'error': 'Transfer is not in a pending state'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            with transaction.atomic():
                logger.info(f"Processing {transfer.items.count()} items")
                for i, item in enumerate(transfer.items.all()):
                    logger.info(f"Processing item {i+1}: {item.item_type} {item.id}")
                    
                    if item.item_type == 'Machine':
                        self.process_machine(item, transfer)
                    elif item.item_type == 'Part':
                        self.process_part(item, transfer)
                    elif item.item_type == 'Accessory':
                        self.process_accessory(item, transfer)
                
                transfer.status = 'Completed'
                transfer.save()
                logger.info(f"Transfer {transfer.id} completed successfully")
                
            return Response({'status': 'Transfer completed successfully'})
        
        except Exception as e:
            logger.exception(f"Failed to complete transfer {transfer.id}: {str(e)}")
            return Response(
                {'error': f'Failed to complete transfer: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def process_machine(self, item, transfer):
        logger.info(f"Processing machine: {item.machine.id}")
        machine = item.machine
        
        if machine.store != transfer.from_store:
            logger.error(f"Machine store mismatch: {machine.store.id} vs {transfer.from_store.id}")
            raise ValueError(f"Machine {machine.serial_no} is not in source store")
        
        if machine.machine_status != 'Available':
            logger.error(f"Machine not available: {machine.machine_status}")
            raise ValueError(f"Machine {machine.serial_no} is not available for transfer")
        
        logger.info(f"Moving machine {machine.id} to store {transfer.to_store.id}")
        machine.store = transfer.to_store
        machine.source_transfer = transfer
        machine.save()

    def process_part(self, item, transfer):
        logger.info(f"Processing part: {item.part.id}")
        part = item.part
        
        if part.part_status != 'Available':
            logger.error(f"Part not available: {part.part_status}")
            raise ValueError(f"Part {part.part_name} is not available for transfer")
        
        if part.quantity < item.quantity:
            logger.error(f"Insufficient quantity: {part.quantity} < {item.quantity}")
            raise ValueError(f"Insufficient quantity for part {part.part_name}")
        
        new_ref_no = f"{part.ref_no}-TR-{str(transfer.id)[:8]}"
        logger.info(f"Creating new part in store {transfer.to_store.id} with ref {new_ref_no}")
        
        Part.objects.create(
            ref_no=new_ref_no,
            store=transfer.to_store,
            part_name=part.part_name,
            part_brand=part.part_brand,
            part_type=part.part_type,
            unit_value=part.unit_value,
            intial_quantity=item.quantity,
            quantity=item.quantity,
            condition_description=part.condition_description,
            part_condition=part.part_condition,
            color_type=part.color_type,
            supplier_name=part.supplier_name,
            part_status='Available',
            source_transfer=transfer
        )
        
        logger.info(f"Deducting {item.quantity} from source part {part.id}")
        part.quantity -= item.quantity
        if part.quantity == 0:
            part.part_status = 'Out of Stock'
        part.save()

    def process_accessory(self, item, transfer):
        logger.info(f"Processing accessory: {item.accessory.id}")
        accessory = item.accessory
        
        if accessory.acc_status != 'Available':
            logger.error(f"Accessory not available: {accessory.acc_status}")
            raise ValueError(f"Accessory {accessory.acc_name} is not available for transfer")
        
        if accessory.quantity < item.quantity:
            logger.error(f"Insufficient quantity: {accessory.quantity} < {item.quantity}")
            raise ValueError(f"Insufficient quantity for accessory {accessory.acc_name}")
        
        new_ref_no = f"{accessory.ref_no}-TR-{str(transfer.id)[:8]}"
        logger.info(f"Creating new accessory in store {transfer.to_store.id} with ref {new_ref_no}")
        
        Accessory.objects.create(
            ref_no=new_ref_no,
            store=transfer.to_store,
            acc_name=accessory.acc_name,
            acc_brand=accessory.acc_brand,
            acc_type=accessory.acc_type,
            unit_value=accessory.unit_value,
            intial_quantity=item.quantity,
            quantity=item.quantity,
            condition_description=accessory.condition_description,
            acc_condition=accessory.acc_condition,
            color_type=accessory.color_type,
            supplier_name=accessory.supplier_name,
            acc_status='Available',
            source_transfer=transfer
        )
        
        logger.info(f"Deducting {item.quantity} from source accessory {accessory.id}")
        accessory.quantity -= item.quantity
        if accessory.quantity == 0:
            accessory.acc_status = 'Out of Stock'
        accessory.save()

class PartMovementView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, machine_id, part_id):
        machine = get_object_or_404(Machine, pk=machine_id)
        part = get_object_or_404(Part, pk=part_id)

        # Validate part belongs to this machine
        if part.origin_machine != machine:
            return Response(
                {"error": "Part not originally from this machine"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update part status
        part.current_machine = None
        part.installed_date = None
        part.part_status = 'Available'
        part.save()

        return Response({"status": "Part removed successfully"})

class PartInstallationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, machine_id, part_id):
        machine = get_object_or_404(Machine, pk=machine_id)
        part = get_object_or_404(Part, pk=part_id)

        # Update part status
        part.current_machine = machine
        part.installed_date = timezone.now().date()
        part.part_status = 'Installed'
        part.save()

        return Response({"status": "Part installed successfully"})