from decimal import Decimal
import os
import random
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.forms import ValidationError
from django.utils.translation import gettext_lazy as _
import uuid
from django.utils import timezone
from django.db.models import Sum
from django.conf import settings
from datetime import date
from dateutil.relativedelta import relativedelta

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'Director')
        extra_fields.setdefault('active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class Store(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_name = models.CharField(max_length=255)
    store_location = models.CharField(max_length=255)
    store_size = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.store_name} - {self.store_location}"

    def to_dict(self):
        return {
            'id': str(self.id),
            'storeName': self.store_name,
            'storeLocation': self.store_location,
            'storeSize': self.store_size,
            'createdAt': self.created_at.isoformat(),
            'updatedAt': self.updated_at.isoformat()
        }

    def copy_with(self, **kwargs):
        return Store.objects.create(
            store_name=kwargs.get('store_name', self.store_name),
            store_location=kwargs.get('store_location', self.store_location),
            store_size=kwargs.get('store_size', self.store_size)
        )
    
    @property
    def machines_count(self):
        return self.machines.count()

    @property
    def parts_count(self):
        return self.parts.count()

    @property
    def accessories_count(self):
        return self.accessories.count()

class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ROLE_CHOICES = (
        ('Director', 'Director'),
        ('Super Admin', 'Super Admin'),
        ('Technician Manager', 'Technician Manager'),
        ('Sales Manager', 'Sales Manager'),
        ('Inventory Manager', 'Inventory Manager'),
        ('Sales Member', 'Sales Member'),
        ('Technician', 'Technician'),
    )
    
    KEY_CHOICES = (
        ('inventory', 'Inventory'),
        ('sales', 'Sales'),
        ('calls', 'Calls'),
        ('leases', 'Leases'),
        ('clients', 'Clients'),
        ('inquiries', 'Inquiries'),
        ('purchase_orders', 'Purchase Orders'),
        ('quotation', 'Quotation'),
        ('transfers', 'Transfers'),
    )
    
    username = None
    email = models.EmailField(_('email address'), unique=True)
    firstname = models.CharField(_('first name'), max_length=100)
    lastname = models.CharField(_('last name'), max_length=100)
    phonenumber = models.CharField(_('phone number'), max_length=20, null=True, blank=True)
    role = models.CharField(_('role'), max_length=20, choices=ROLE_CHOICES, default='Technician')
    active = models.BooleanField(_('active'), default=False)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    stores = models.ManyToManyField(
        Store, 
        related_name='users',
        blank=True,
        help_text="Stores this user has access to"
    )

    # Security fields
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    security_token = models.CharField(max_length=255, null=True, blank=True)
    
    # Key-based permissions (replaces additional_permissions)
    keys = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="Permission keys with access levels: {'inventory': ['read', 'create'], 'sales': ['read', 'update', 'delete']}"
    )
    keys_granted_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='granted_keys'
    )
    keys_granted_at = models.DateTimeField(null=True, blank=True)
    keys_reason = models.TextField(blank=True, help_text="Reason for granting keys")
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['firstname', 'lastname', 'role']
    
    objects = CustomUserManager()
    
    def __str__(self):
        return self.email
    
    def has_permission(self, key, action, obj=None):
        """Check if user has permission for a specific key and action with store validation"""
        # First check role-based permissions
        role_permissions = self.get_role_permissions()
        if key in role_permissions and action in role_permissions[key]:
            # For role-based permissions, check store access if object has store
            if obj and hasattr(obj, 'store'):
                return self.check_store_access(obj.store)
            return True
            
        # Then check key-based permissions
        if self.has_key_access(key, action, obj):
            return True
                
        return False
    
    def get_role_permissions(self):
        """Get base permissions based on role"""
        role_permission_map = {
            'Director': {
                'sales': ['read', 'create', 'update', 'delete'],
                'inventory': ['read', 'create', 'update', 'delete'],
                'calls': ['read', 'create', 'update', 'delete'],
                'leases': ['read', 'create', 'update', 'delete'],
                'clients': ['read', 'create', 'update', 'delete'],
                'inquiries': ['read', 'create', 'update', 'delete'],
                'purchase_orders': ['read', 'create', 'update', 'delete', 'verify'],
                'quotation': ['read', 'create', 'update', 'delete'],
                'transfers': ['read', 'create', 'update', 'delete'],
            },
            'Super Admin': {
                'sales': ['read', 'create', 'update', 'delete'],
                'inventory': ['read', 'create', 'update', 'delete'],
                'calls': ['read', 'create', 'update', 'delete'],
                'leases': ['read', 'create', 'update', 'delete'],
                'clients': ['read', 'create', 'update', 'delete'],
                'inquiries': ['read', 'create', 'update', 'delete'],
                'purchase_orders': ['read', 'create', 'update', 'delete', 'verify'],
                'quotation': ['read', 'create', 'update', 'delete'],
                'transfers': ['read', 'create', 'update', 'delete'],
            },
            'Sales Manager': {
                'sales': ['read', 'create', 'update', 'delete'],
                'clients': ['read', 'create', 'update', 'delete'],
                'leases': ['read', 'create', 'update', 'delete'],
                'purchase_orders': ['read', 'create', 'update', 'verify'],
                'quotation': ['read', 'create', 'update'],
            },
            'Sales Member': {
                'sales': ['read', 'create', 'update'],
                'purchase_orders': ['read', 'create', 'update'],
                'quotation': ['read', 'create', 'update'],
            },
            'Inventory Manager': {
                'inventory': ['read', 'create', 'update', 'delete'],
                'inquiries': ['read', 'create', 'update', 'delete'],
                'transfers': ['read', 'create', 'update', 'delete'],
            },
            'Technician Manager': {
                'calls': ['read', 'create', 'update', 'delete']
            },
            'Technician': {
                'calls': ['read', 'create', 'update']
            }
        }
        return role_permission_map.get(self.role, {})
    
    def has_permission(self, key, action, obj=None):
        """Check if user has permission for a specific key and action"""
        # First check role-based permissions
        role_permissions = self.get_role_permissions()
        if key in role_permissions and action in role_permissions[key]:
            return True
            
        # Then check key-based permissions
        if self.has_key_access(key, action):
            # Check store access if object has store relationship
            if obj and hasattr(obj, 'store'):
                return self.check_store_access(obj.store)
            return True
            
        return False

    def check_store_access(self, store):
        """Check if user has access to a specific store"""
        if self.role in ['Director', 'Super Admin']:
            return True
        return store in self.stores.all()
    
    def get_all_permissions(self):
        """Get combined role and key permissions"""
        role_perms = self.get_role_permissions()
        key_perms = self.keys or {}  # Handle None case
        
        # Merge permissions
        all_perms = {}
        for key in ['inventory', 'sales', 'calls', 'leases', 'clients', 'inquiries']:
            combined_actions = set()
            
            # Add role permissions
            if key in role_perms:
                combined_actions.update(role_perms[key])
                
            # Add key permissions
            if key in key_perms:
                key_data = key_perms[key]
                if isinstance(key_data, list):
                    combined_actions.update(key_data)
                elif isinstance(key_data, dict):
                    combined_actions.update(key_data.get('actions', []))
                
            if combined_actions:
                all_perms[key] = list(combined_actions)
                
        return all_perms
    
    def has_key_access(self, key, action=None, obj=None):
        """Check if user has key-based access"""
        if not self.keys:
            return False
        
        key_data = self.keys.get(key)
        if not key_data:
            return False
        
        # Handle both old format (list) and new format (dict)
        if isinstance(key_data, list):
            actions = key_data
        elif isinstance(key_data, dict):
            actions = key_data.get('actions', [])
        else:
            return False
        
        # Check action permission
        if action and action not in actions:
            return False
        
        # Check store access if object has store
        if obj and hasattr(obj, 'store'):
            if isinstance(key_data, dict):
                allowed_store_ids = key_data.get('store_ids', [])
                if allowed_store_ids and str(obj.store.id) not in allowed_store_ids:
                    return False
        
        return True
    
    def grant_key_access(self, key, actions, granted_by_user, reason="", store_ids=None):
        """Grant key access with specific actions"""
        if self.keys is None:
            self.keys = {}
        
        # Validate actions
        valid_actions = ['read', 'create', 'update', 'delete']
        actions = [a for a in actions if a in valid_actions]
        
        self.keys[key] = {
            'actions': actions,
            'store_ids': store_ids or [],
            'granted_by': str(granted_by_user.id),
            'granted_at': timezone.now().isoformat(),
            'reason': reason
        }
        self.keys_granted_by = granted_by_user
        self.keys_granted_at = timezone.now()
        self.keys_reason = reason
        self.save(update_fields=['keys', 'keys_granted_by', 'keys_granted_at', 'keys_reason'])
        
        # Log security event
        SecurityEvent.objects.create(
            user=self,
            event_type='KEY_GRANTED',
            ip_address='system',
            details={
                'key': key,
                'actions': actions,
                'granted_by': str(granted_by_user.id),
                'reason': reason,
                'store_ids': store_ids or []

            }
        )

    def revoke_key_access(self, key, revoked_by_user):
        """Revoke key access"""
        if self.keys is None:
            self.keys = {}

        if self.keys and key in self.keys:
            del self.keys[key]
            # If keys becomes empty, you can either keep it as {} or set to None
            if not self.keys:
                self.keys = {}  # Keep as empty dict, or set to None if preferred
            self.save(update_fields=['keys'])
            
            # Log security event
            SecurityEvent.objects.create(
                user=self,
                event_type='KEY_REVOKED',
                ip_address='system',
                details={
                    'key': key,
                    'revoked_by': str(revoked_by_user.id)
                }
            )
    
    def is_locked(self):
        """Check if user account is currently locked"""
        if not self.locked_until:
            return False
        return timezone.now() < self.locked_until

    def lock_account(self, duration_minutes=30):
        """Lock the user account for specified duration"""
        self.locked_until = timezone.now() + timedelta(minutes=duration_minutes)
        self.save(update_fields=['locked_until'])
        
        # Log security event
        SecurityEvent.objects.create(
            user=self,
            event_type='ACCOUNT_LOCKED',
            ip_address='system',
            details={'locked_for_minutes': duration_minutes}
        )

    def unlock_account(self):
        """Unlock the user account"""
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['locked_until', 'failed_login_attempts'])

    def increment_failed_login(self):
        """Increment failed login attempts and lock if necessary"""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        
        # Lock account after 5 failed attempts for 30 minutes
        if self.failed_login_attempts >= 5:
            self.lock_account(30)
        
        self.save(update_fields=['failed_login_attempts', 'last_failed_login'])

    def reset_failed_login_attempts(self):
        """Reset failed login attempts after successful login"""
        self.failed_login_attempts = 0
        self.last_failed_login = None
        self.save(update_fields=['failed_login_attempts', 'last_failed_login'])

# Key audit model (replaces PermissionAudit)
class KeyAudit(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    key = models.CharField(max_length=20)
    actions = models.JSONField(default=list)
    action_type = models.CharField(max_length=20, choices=[
        ('GRANTED', 'Granted'),
        ('REVOKED', 'Revoked'),
        ('MODIFIED', 'Modified')
    ])
    granted_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='key_actions'
    )
    reason = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']

class LoginAttempt(models.Model):
    """Track login attempts from different IPs"""
    ip_address = models.GenericIPAddressField()
    email = models.EmailField(null=True, blank=True)
    success = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']

class SecurityEvent(models.Model):
    """Log security events"""
    EVENT_TYPES = [
        ('LOGIN_SUCCESS', 'Login Success'),
        ('LOGIN_FAILED', 'Login Failed'),
        ('ACCOUNT_LOCKED', 'Account Locked'),
        ('SUSPICIOUS_ACTIVITY', 'Suspicious Activity'),
        ('PASSWORD_CHANGED', 'Password Changed'),
        ('MULTIPLE_FAILED_ATTEMPTS', 'Multiple Failed Attempts'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']

class Device(models.Model):
    DEVICE_TYPE_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='devices')
    push_token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES)
    device_name = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'push_token']

    def __str__(self):
        return f"{self.user.email} - {self.device_type}"

class MachineType(models.Model):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    color = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image1 = models.ImageField(upload_to='machine_types/', blank=True, null=True)
    image2 = models.ImageField(upload_to='machine_types/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.brand}"

    class Meta:
        ordering = ['-created_at']

class PartType(models.Model):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    color = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image1 = models.ImageField(upload_to='part_types/', blank=True, null=True)
    image2 = models.ImageField(upload_to='part_types/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.brand}"

    class Meta:
        ordering = ['-created_at']

class AccessoryType(models.Model):
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    color = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image1 = models.ImageField(upload_to='accessory_types/', blank=True, null=True)
    image2 = models.ImageField(upload_to='accessory_types/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.brand}"

    class Meta:
        ordering = ['-created_at']

class Client(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_name = models.CharField(max_length=255)
    client_location = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['client_name', 'client_location']

    def __str__(self):
        return f"{self.client_name} - {self.client_location}"

class Machine(models.Model):
    MACHINE_CONDITION_CHOICES = [
        ('New', 'New'),
        ('Used', 'Used'),
        ('Refurbished', 'Refurbished'),
    ]
    
    MACHINE_STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Maintenance', 'Maintenance'),
        ('Leased', 'Leased'),
        ('Out of Stock', 'Out of Stock'),
        ('Sold', 'Sold'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine_name = models.CharField(max_length=255)
    machine_brand = models.CharField(max_length=255)
    machine_type = models.CharField(max_length=255)
    serial_no = models.CharField(max_length=255, unique=True, blank=True)
    unit_value = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    condition_description = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    machine_condition = models.CharField(max_length=20, choices=MACHINE_CONDITION_CHOICES)
    color_type = models.CharField(max_length=100)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='machines')
    supplier_name = models.CharField(max_length=255)
    machine_status = models.CharField(max_length=20, choices=MACHINE_STATUS_CHOICES)
    is_transfer = models.BooleanField(default=False)
    source_transfer = models.ForeignKey('Transfer', on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_machines')
    qr_code = models.ImageField(upload_to='qr_codes/machines/', blank=True, null=True)
    auto_generated_serial = models.BooleanField(default=False, help_text='Whether serial number was auto-generated')

    def __str__(self):
        return f"{self.machine_name} - {self.serial_no}"

    @property
    def store_name(self):
        return self.store.store_name

    @property
    def store_id(self):
        return str(self.store.id)

    def save(self, *args, **kwargs):
        from .utils import generate_unique_serial, generate_qr_code
        
        # Auto-generate serial number if not provided
        if not self.serial_no:
            self.serial_no = generate_unique_serial(
                prefix='M-',
                length=8,
                model_class=Machine,
                field_name='serial_no'
            )
            self.auto_generated_serial = True
        
        # Save the instance first
        super().save(*args, **kwargs)
        
        # Generate QR code if it doesn't exist
        if self.serial_no and not self.qr_code:
            try:
                qr_path = generate_qr_code(self.serial_no, f'machine_{self.id}')
                self.qr_code = qr_path
                # Update only qr_code field to avoid recursion
                Machine.objects.filter(pk=self.pk).update(qr_code=qr_path)
            except Exception as e:
                # Log error but don't fail the save
                import logging
                logging.error(f"Failed to generate QR code for machine {self.id}: {e}")

    class Meta:
        ordering = ['-created_at']

class Part(models.Model):
    PART_CONDITION_CHOICES = [
        ('New', 'New'),
        ('Used', 'Used'),
        ('Refurbished', 'Refurbished'),
    ]
    
    PART_STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Reserved', 'Reserved'),
        ('Out of Stock', 'Out of Stock'),
        ('Maintenance', 'Maintenance'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    part_name = models.CharField(max_length=255)  
    part_brand = models.CharField(max_length=255)  
    part_type = models.CharField(max_length=255)  
    ref_no = models.CharField(max_length=255, unique=True, blank=True)  
    unit_value = models.PositiveIntegerField()
    intial_quantity = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    condition_description = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    part_condition = models.CharField(max_length=20, choices=PART_CONDITION_CHOICES)
    color_type = models.CharField(max_length=100)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='parts')
    supplier_name = models.CharField(max_length=255)
    part_status = models.CharField(max_length=20, choices=PART_STATUS_CHOICES)
    is_transfer = models.BooleanField(default=False)
    source_transfer = models.ForeignKey('Transfer', on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_parts')
    origin_machine = models.ForeignKey(
        Machine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='donated_parts',
        help_text="Machine this part was originally removed from"
    )
    current_machine = models.ForeignKey(
        Machine,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='installed_parts',
        help_text="Machine this part is currently installed in"
    )
    removed_date = models.DateField(null=True, blank=True)
    installed_date = models.DateField(null=True, blank=True)
    qr_code = models.ImageField(upload_to='qr_codes/parts/', blank=True, null=True)
    auto_generated_ref = models.BooleanField(default=False, help_text='Whether reference number was auto-generated')

    def __str__(self):
        return f"{self.part_name} - {self.ref_no}"
    
    def save(self, *args, **kwargs):
        from .utils import generate_unique_ref, generate_qr_code
        
        # Auto-generate ref number if not provided
        if not self.ref_no:
            self.ref_no = generate_unique_ref(
                prefix='P-',
                length=8,
                model_class=Part,
                field_name='ref_no'
            )
            self.auto_generated_ref = True
        
        # Save the instance first
        super().save(*args, **kwargs)
        
        # Generate QR code if it doesn't exist
        if self.ref_no and not self.qr_code:
            try:
                qr_path = generate_qr_code(self.ref_no, f'part_{self.id}')
                self.qr_code = qr_path
                # Update only qr_code field to avoid recursion
                Part.objects.filter(pk=self.pk).update(qr_code=qr_path)
            except Exception as e:
                # Log error but don't fail the save
                import logging
                logging.error(f"Failed to generate QR code for part {self.id}: {e}")

    @property
    def store_name(self):
        return self.store.store_name

    @property
    def store_id(self):
        return str(self.store.id)
    
    def leased_quantity(self):
        """Get the total quantity of this part that is leased"""
        result = self.leasepartinquiry_set.aggregate(total=Sum('initial_quantity'))
        return result['total'] or 0
    
    def sold_quantity(self):
        """Get the total quantity of this part that is sold"""
        result = SaleItem.objects.filter(part=self).aggregate(total=Sum('initial_quantity'))
        return result['total'] or 0
    
    def available_quantity(self):
        """Get the quantity available"""
        return self.intial_quantity - self.leased_quantity() - self.sold_quantity()
    
    @property
    def transferred_quantity(self):
        """Calculate total quantity transferred out from this part"""
        return TransferItem.objects.filter(
            part=self,
            transfer__status='Completed',
            transfer__from_store=self.store
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def received_quantity(self):
        """Calculate total quantity received through transfers"""
        return TransferItem.objects.filter(
            part__ref_no__startswith=self.ref_no.split('-TR-')[0],  # Original ref_no before transfer
            transfer__status='Completed',
            transfer__to_store=self.store
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def transfer_history(self):
        """Get all transfers involving this part"""
        from django.db.models import Q
        
        # Get transfers where this part was transferred out
        outgoing = TransferItem.objects.filter(
            part=self,
            transfer__from_store=self.store
        ).select_related('transfer', 'transfer__from_store', 'transfer__to_store')
        
        # Get transfers where similar parts were transferred in (based on ref_no pattern)
        incoming = TransferItem.objects.filter(
            part__ref_no__startswith=self.ref_no.split('-TR-')[0],
            transfer__to_store=self.store
        ).select_related('transfer', 'transfer__from_store', 'transfer__to_store')
        
        history = []
        
        for item in outgoing:
            history.append({
                'id': f"out_{item.id}",
                'transfer': {
                    'id': str(item.transfer.id),
                    'from_store': {
                        'id': str(item.transfer.from_store.id),
                        'storeName': item.transfer.from_store.store_name,  # Use storeName to match frontend
                        'storeLocation': item.transfer.from_store.store_location  # Use storeLocation to match frontend
                    },
                    'to_store': {
                        'id': str(item.transfer.to_store.id),
                        'storeName': item.transfer.to_store.store_name,  # Use storeName to match frontend
                        'storeLocation': item.transfer.to_store.store_location  # Use storeLocation to match frontend
                    },
                    'created_at': item.transfer.created_at.isoformat(),
                    'status': item.transfer.status,
                    'notes': item.transfer.notes
                },
                'quantity': item.quantity,
                'transfer_type': 'outgoing',
                'status': item.transfer.status
            })
            
        for item in incoming:
            history.append({
                'id': f"in_{item.id}",
                'transfer': {
                    'id': str(item.transfer.id),
                    'from_store': {
                        'id': str(item.transfer.from_store.id),
                        'storeName': item.transfer.from_store.store_name,  # Use storeName to match frontend
                        'storeLocation': item.transfer.from_store.store_location  # Use storeLocation to match frontend
                    },
                    'to_store': {
                        'id': str(item.transfer.to_store.id),
                        'storeName': item.transfer.to_store.store_name,  # Use storeName to match frontend
                        'storeLocation': item.transfer.to_store.store_location  # Use storeLocation to match frontend
                    },
                    'created_at': item.transfer.created_at.isoformat(),
                    'status': item.transfer.status,
                    'notes': item.transfer.notes
                },
                'quantity': item.quantity,
                'transfer_type': 'incoming',
                'status': item.transfer.status
            })
        
        # Sort by created_at date
        history.sort(key=lambda x: x['transfer']['created_at'], reverse=True)
        return history

    class Meta:
        ordering = ['-created_at']

class Accessory(models.Model):
    ACCESSORY_CONDITION_CHOICES = [
        ('New', 'New'),
        ('Used', 'Used'),
        ('Refurbished', 'Refurbished'),
    ]
    
    ACCESSORY_STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Reserved', 'Reserved'),
        ('Out of Stock', 'Out of Stock'),
        ('Maintenance', 'Maintenance'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    acc_name = models.CharField(max_length=255)
    acc_brand = models.CharField(max_length=255)
    acc_type = models.CharField(max_length=255)
    ref_no = models.CharField(max_length=255, unique=True, blank=True)
    unit_value = models.PositiveIntegerField()
    intial_quantity = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    condition_description = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    acc_condition = models.CharField(max_length=20, choices=ACCESSORY_CONDITION_CHOICES)
    color_type = models.CharField(max_length=100)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='accessories')
    supplier_name = models.CharField(max_length=255)
    acc_status = models.CharField(max_length=20, choices=ACCESSORY_STATUS_CHOICES)
    is_transfer = models.BooleanField(default=False)
    source_transfer = models.ForeignKey('Transfer', on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_accessories')
    qr_code = models.ImageField(upload_to='qr_codes/accessories/', blank=True, null=True)
    auto_generated_ref = models.BooleanField(default=False, help_text='Whether reference number was auto-generated')

    def __str__(self):
        return f"{self.acc_name} - {self.ref_no}"
    
    def save(self, *args, **kwargs):
        from .utils import generate_unique_ref, generate_qr_code
        
        # Auto-generate ref number if not provided
        if not self.ref_no:
            self.ref_no = generate_unique_ref(
                prefix='A-',
                length=8,
                model_class=Accessory,
                field_name='ref_no'
            )
            self.auto_generated_ref = True
        
        # Save the instance first
        super().save(*args, **kwargs)
        
        # Generate QR code if it doesn't exist
        if self.ref_no and not self.qr_code:
            try:
                qr_path = generate_qr_code(self.ref_no, f'accessory_{self.id}')
                self.qr_code = qr_path
                # Update only qr_code field to avoid recursion
                Accessory.objects.filter(pk=self.pk).update(qr_code=qr_path)
            except Exception as e:
                # Log error but don't fail the save
                import logging
                logging.error(f"Failed to generate QR code for accessory {self.id}: {e}")

    @property
    def store_name(self):
        return self.store.store_name

    @property
    def store_id(self):
        return str(self.store.id)
    
    def leased_quantity(self):
        """Get the total quantity of this part that is leased"""
        result = self.leaseaccinquiry_set.aggregate(total=Sum('initial_quantity'))
        return result['total'] or 0
    
    def sold_quantity(self):
        """Get the total quantity of this part that is sold"""
        result = SaleItem.objects.filter(accessory=self).aggregate(total=Sum('Initial_quantity'))
        return result['total'] or 0
    
    def available_quantity(self):
        """Get the quantity available"""
        return self.intial_quantity - self.leased_quantity() - self.sold_quantity()
    
    @property
    def transferred_quantity(self):
        """Calculate total quantity transferred out from this accessory"""
        return TransferItem.objects.filter(
            accessory=self,
            transfer__status='Completed',
            transfer__from_store=self.store
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def received_quantity(self):
        """Calculate total quantity received through transfers"""
        return TransferItem.objects.filter(
            accessory__ref_no__startswith=self.ref_no.split('-TR-')[0],  # Original ref_no before transfer
            transfer__status='Completed',
            transfer__to_store=self.store
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def transfer_history(self):
        """Get all transfers involving this accessory"""
        from django.db.models import Q
        
        # Get transfers where this accessory was transferred out
        outgoing = TransferItem.objects.filter(
            accessory=self,
            transfer__from_store=self.store
        ).select_related('transfer', 'transfer__from_store', 'transfer__to_store')
        
        # Get transfers where similar accessories were transferred in (based on ref_no pattern)
        incoming = TransferItem.objects.filter(
            accessory__ref_no__startswith=self.ref_no.split('-TR-')[0],
            transfer__to_store=self.store
        ).select_related('transfer', 'transfer__from_store', 'transfer__to_store')
        
        history = []
        
        for item in outgoing:
            history.append({
                'id': f"out_{item.id}",
                'transfer': {
                    'id': str(item.transfer.id),
                    'from_store': {
                        'id': str(item.transfer.from_store.id),
                        'storeName': item.transfer.from_store.store_name,  # Use storeName to match frontend
                        'storeLocation': item.transfer.from_store.store_location  # Use storeLocation to match frontend
                    },
                    'to_store': {
                        'id': str(item.transfer.to_store.id),
                        'storeName': item.transfer.to_store.store_name,  # Use storeName to match frontend
                        'storeLocation': item.transfer.to_store.store_location  # Use storeLocation to match frontend
                    },
                    'created_at': item.transfer.created_at.isoformat(),
                    'status': item.transfer.status,
                    'notes': item.transfer.notes,
                    'created_by': {
                        'firstname': item.transfer.created_by.firstname,
                        'lastname': item.transfer.created_by.lastname
                    } if item.transfer.created_by else None
                },
                'quantity': item.quantity,
                'transfer_type': 'outgoing',
                'status': item.transfer.status
            })
            
        for item in incoming:
            history.append({
                'id': f"in_{item.id}",
                'transfer': {
                    'id': str(item.transfer.id),
                    'from_store': {
                        'id': str(item.transfer.from_store.id),
                        'storeName': item.transfer.from_store.store_name,  # Use storeName to match frontend
                        'storeLocation': item.transfer.from_store.store_location  # Use storeLocation to match frontend
                    },
                    'to_store': {
                        'id': str(item.transfer.to_store.id),
                        'storeName': item.transfer.to_store.store_name,  # Use storeName to match frontend
                        'storeLocation': item.transfer.to_store.store_location  # Use storeLocation to match frontend
                    },
                    'created_at': item.transfer.created_at.isoformat(),
                    'status': item.transfer.status,
                    'notes': item.transfer.notes,
                    'created_by': {
                        'firstname': item.transfer.created_by.firstname,
                        'lastname': item.transfer.created_by.lastname
                    } if item.transfer.created_by else None
                },
                'quantity': item.quantity,
                'transfer_type': 'incoming',
                'status': item.transfer.status
            })
        
        # Sort by created_at date
        history.sort(key=lambda x: x['transfer']['created_at'], reverse=True)
        return history

    class Meta:
        ordering = ['-created_at']

class ClientMachine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_name = models.CharField(max_length=255)
    client_location = models.CharField(max_length=255)
    machine_name = models.CharField(max_length=255)
    machine_brand = models.CharField(max_length=255)
    serial_no = models.CharField(max_length=255, unique=True)
    machine_type = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class LeaseServiceSchedule(models.Model):
    FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi-annual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('custom', 'Custom'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey('LeaseContract', on_delete=models.CASCADE, related_name='service_schedules')
    service_type = models.CharField(max_length=50, choices=[  # Remove Call.SERVICE_TYPE_CHOICES reference
        ('Network Support', 'Network Support'),
        ('Hardware & Software Support', 'Hardware & Software Support'),
        ('Installation', 'Installation'),
        ('Scheduled Maintenance', 'Scheduled Maintenance'),
    ])
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    frequency_months = models.PositiveIntegerField(default=1)
    start_date = models.DateField()
    end_date = models.DateField()
    default_technicians = models.ManyToManyField(CustomUser, related_name='assigned_schedules', blank=True)
    lpo = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.lease.lease_no} - {self.service_type} - {self.frequency}"
    
    def generate_next_service_calls(self):
        """Generate service calls for the upcoming period"""
        from datetime import date
        from dateutil.relativedelta import relativedelta
        
        today = date.today()
        if today > self.end_date or not self.is_active:
            return []
        
        # Find the last generated service call for this schedule
        last_call = Call.objects.filter(  # Now Call is defined
            lease_service_schedule=self
        ).order_by('-reported_date').first()
        
        # Determine where to start generating from
        if last_call:
            start_from = last_call.reported_date.date() + relativedelta(months=self.frequency_months)
        else:
            start_from = self.start_date
        
        generated_calls = []
        current_date = start_from
        
        # Generate calls until we reach today or the end date
        while current_date <= self.end_date and current_date <= today:
            # Check if call already exists for this period
            existing_call = Call.objects.filter(  # Now Call is defined
                lease_service_schedule=self,
                reported_date__year=current_date.year,
                reported_date__month=current_date.month
            ).exists()
            
            if not existing_call:
                # Create the service call
                call = Call.objects.create(  # Now Call is defined
                    contract_type='Lease',
                    service_type=self.service_type,
                    lease=self.lease,
                    lease_service_schedule=self,
                    client=self.lease.client,
                    client_name=self.lease.client.client_name,
                    client_location=self.lease.client.client_location,
                    item=self.lease.item,
                    department=self.lease.department,
                    fault_reported=f"Scheduled {self.service_type} maintenance for {current_date.strftime('%B %Y')}",
                    reported_by="System",
                    reported_date=current_date,
                    lpo=self.lpo,
                    status='Open'
                )
                
                # Assign default technicians
                if self.default_technicians.exists():
                    call.technician.set(self.default_technicians.all())
                    call.status = 'Pending'
                    call.save()
                
                generated_calls.append(call)
            
            # Move to next period
            current_date += relativedelta(months=self.frequency_months)
        
        return generated_calls

class Call(models.Model):
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),  
        ('Closed', 'Closed'),
    ]

    SERVICE_TYPE_CHOICES = [
        ('Network Support', 'Network Support'),
        ('Hardware & Software Support', 'Hardware & Software Support'),
        ('Installation', 'Installation'),
        ('Scheduled Maintenance', 'Scheduled Maintenance'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technician = models.ManyToManyField(CustomUser, related_name='calls')
    contract_type = models.CharField(max_length=100)
    service_type = models.CharField(max_length=50, choices=SERVICE_TYPE_CHOICES, default='Hardware & Software Support')
    lpo = models.TextField(blank=True, default='')  
    client = models.ForeignKey(Client, on_delete=models.PROTECT, null=True, blank=True)
    reported_by = models.CharField(max_length=255)
    reported_date = models.DateTimeField(default=timezone.now)
    item = models.ForeignKey(Machine, on_delete=models.PROTECT, null=True, blank=True)
    fault_reported = models.TextField()
    action_taken = models.TextField(blank=True, default='')
    meter_reading = models.PositiveIntegerField(default=0)
    color_meter_reading = models.PositiveIntegerField(default=0)
    mono_meter_reading = models.PositiveIntegerField(default=0)
    parts_required = models.TextField(blank=True, default='')  
    parts_used = models.TextField(blank=True, default='')
    comments = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    department = models.CharField(max_length=100)
    is_checked = models.BooleanField(default=False)
    director_comment = models.TextField(blank=True)
    ticket_no = models.CharField(max_length=50, unique=True)
    spare_description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    client_verification = models.BooleanField(default=False)
    technician_manager_approval = models.BooleanField(default=False)
    client_name = models.CharField(max_length=255, blank=True)
    client_location = models.CharField(max_length=255, blank=True)
    client_machine = models.ForeignKey(ClientMachine, on_delete=models.PROTECT, null=True, blank=True)
    walk_in_machine_name = models.CharField(max_length=255, blank=True)
    walk_in_machine_type = models.CharField(max_length=255, blank=True)
    walk_in_serial_no = models.CharField(max_length=255, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)  
    finish_time = models.DateTimeField(null=True, blank=True)
    lease = models.ForeignKey(
        'LeaseContract', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='service_calls',
        help_text="Associated lease contract if this is a lease service call"
    )
    images = models.JSONField(
        default=list,
        blank=True,
        help_text="List of image URLs for this service call"
    )
    lease_service_schedule = models.ForeignKey(
        LeaseServiceSchedule, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='generated_calls'
    )

    def __str__(self):
        if self.client:
            return f"{self.ticket_no} - {self.client.client_name}"
        else:
            return f"{self.ticket_no} - {self.client_name} ({self.client_location})"

    def check_and_update_status(self):
        """
        Updated status logic
        """
        if self.client_verification and self.technician_manager_approval:
            self.status = 'Closed'
        # Only update status if it's not already in progress/completed
        elif self.status not in ['In Progress', 'Completed']:
            if self.technician.exists():
                self.status = 'Pending'
            else:
                self.status = 'Open'

    def save(self, *args, **kwargs):
        if not self.ticket_no:
            self.ticket_no = self.generate_ticket_number()
        
        self.check_and_update_status()
        super().save(*args, **kwargs)

    def generate_ticket_number(self):
        now = timezone.now()
        random_num = random.randint(10000, 99999)
        return f"TN-{now.month:02d}/{now.strftime('%y')}/{random_num}"
    
class StorePartInquiry(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Issued', 'Issued'),
        ('Rejected', 'Rejected')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='part_store_inquiries')  # Fixed: unique related_name
    part_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    requested_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT)
    requested_at = models.DateTimeField(auto_now_add=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    add_vat = models.BooleanField(default=False)
    is_issued = models.BooleanField(default=False)
    issued_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_part_inquiries')  # Fixed: unique related_name
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True)
    lease = models.ForeignKey(
        'LeaseContract', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='store_part_inquiries',
        help_text="Associated lease for billing this part request"
    )

    class Meta:
        ordering = ['-requested_at']

class StoreAccessoryInquiry(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Issued', 'Issued'),
        ('Rejected', 'Rejected')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='accessory_store_inquiries')  # Fixed: unique related_name
    acc_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    requested_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT)
    requested_at = models.DateTimeField(auto_now_add=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    add_vat = models.BooleanField(default=False)
    is_issued = models.BooleanField(default=False)
    issued_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_accessory_inquiries')  # Fixed: unique related_name
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True)
    lease = models.ForeignKey(
        'LeaseContract', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='store_accessory_inquiries',
        help_text="Associated lease for billing this accessory request"
    )

    class Meta:
        ordering = ['-requested_at']
    
class ServiceCallToken(models.Model):
    """
    Model to store tokens for external viewing of service calls
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_call = models.ForeignKey('Call', on_delete=models.CASCADE, related_name='tokens')
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    def is_valid(self):
        """Check if the token is valid (not expired and not used)"""
        return not self.is_used and timezone.now() < self.expires_at
    
    def save(self, *args, **kwargs):
        # Set expiration time to 1 hour from creation if not set
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=1)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Token for {self.service_call.ticket_no} - {self.email}"

class LeaseContract(models.Model):
    CONTRACT_TYPE_CHOICES = [
        ('Lease', 'Lease'),
        ('Rental', 'Rental'),
        ('Maintenance', 'Maintenance'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('Paid', 'Paid'),
        ('Partial', 'Partial'),
        ('Unpaid', 'Unpaid'),
        ('Overdue', 'Overdue'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    department = models.CharField(max_length=100)
    item = models.ForeignKey(Machine, on_delete=models.PROTECT)
    from_date = models.DateField()
    to_date = models.DateField()
    add_vat = models.BooleanField(default=False)
    add_myq = models.BooleanField(default=False)
    billed_myq = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    contract_type = models.CharField(max_length=20, choices=CONTRACT_TYPE_CHOICES)
    lease_no = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    store = models.ForeignKey(Store, on_delete=models.PROTECT)
    account_handler = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='handled_leases',
        help_text="User responsible for managing this lease account"
    )
    technician = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_leases', 
        limit_choices_to={'role__in': ['Technician', 'Technician Manager']},
        help_text="Technician assigned for maintenance/support"
    )
    
    # Initial counter readings (for used machines)
    initial_mono_counter = models.PositiveIntegerField(
        default=0,
        help_text="Initial monochrome counter reading when lease started (for used machines)"
    )
    initial_color_counter = models.PositiveIntegerField(
        default=0,
        null=True,
        blank=True,
        help_text="Initial color counter reading when lease started (for used color machines)"
    )
    
    # Per-copy rates
    monochrome_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Rate per monochrome/B&W copy"
    )
    color_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Rate per color copy (for color machines only)"
    )
    
    # Payment tracking
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remaining_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Unpaid')
    payment_notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.lease_no} - {self.client.client_name}"

    def save(self, *args, **kwargs):
        if not self.lease_no:
            self.lease_no = self.generate_lease_number()
        super().save(*args, **kwargs)

    def generate_lease_number(self):
        now = timezone.now()
        random_num = random.randint(10000, 99999)
        return f"LN-{now.month:02d}/{now.strftime('%y')}/{random_num}"

    def calculate_month_bill(self, meter_reading):
        """
        Calculate bill for a specific month based on meter reading.
        For the first reading in the lease, uses initial counters if available,
        otherwise treats it as the baseline (no billing).
        For subsequent readings, calculates based on the previous reading.
        Returns dict with breakdown of charges.
        """
        if not meter_reading:
            return {
                'base_amount': 0,
                'vat_amount': 0,
                'myq_amount': 0,
                'total_amount': 0,
                'color_copies': 0,
                'mono_copies': 0,
                'is_baseline': False,
                'has_previous': False
            }
        
        # Find previous reading for this lease (chronologically before this one)
        previous_reading = MeterReading.objects.filter(
            lease=self,
            month__lt=meter_reading.month
        ).order_by('-month').first()
        
        # Check if this is the first reading ever for this lease
        is_first_reading = not previous_reading
        
        # Initialize variables
        base_amount = 0
        color_copies_billed = 0
        mono_copies_billed = 0
        is_baseline = False
        
        if self.item.color_type == 'Color':
            # Color machine: calculate both color and mono copies
            current_color = meter_reading.color_meter_reading or 0
            current_mono = meter_reading.mono_meter_reading or 0
            
            if is_first_reading:
                # First reading - check if we have initial counters
                if self.initial_mono_counter > 0 or self.initial_color_counter > 0:
                    # We have initial counters, use them for billing
                    color_copies_billed = max(0, current_color - (self.initial_color_counter or 0))
                    mono_copies_billed = max(0, current_mono - self.initial_mono_counter)
                else:
                    # No initial counters - treat this as baseline (no billing)
                    is_baseline = True
                    color_copies_billed = 0
                    mono_copies_billed = 0
            else:
                # Subsequent readings - subtract from previous month
                previous_color = previous_reading.color_meter_reading or 0
                previous_mono = previous_reading.mono_meter_reading or 0
                
                color_copies_billed = max(0, current_color - previous_color)
                mono_copies_billed = max(0, current_mono - previous_mono)
            
            if not is_baseline:
                base_amount = (float(self.color_rate) * color_copies_billed) + \
                            (float(self.monochrome_rate) * mono_copies_billed)
        else:
            # Monochrome machine: only mono copies
            current_mono = meter_reading.mono_meter_reading or meter_reading.meter_reading or 0
            
            if is_first_reading:
                # First reading - check if we have initial counter
                if self.initial_mono_counter > 0:
                    # We have initial counter, use it for billing
                    mono_copies_billed = max(0, current_mono - self.initial_mono_counter)
                else:
                    # No initial counter - treat this as baseline (no billing)
                    is_baseline = True
                    mono_copies_billed = 0
            else:
                # Subsequent readings - subtract from previous month
                previous_mono = previous_reading.mono_meter_reading or previous_reading.meter_reading or 0
                mono_copies_billed = max(0, current_mono - previous_mono)
            
            if not is_baseline:
                base_amount = float(self.monochrome_rate) * mono_copies_billed
        
        # Calculate MyQ charges (if subscription type and not baseline)
        myq_amount = 0
        if self.add_myq and not is_baseline:
            myq_payment = self.myq_payments.first()
            if myq_payment and myq_payment.payment_type == 'subscription':
                if self.item.color_type == 'Color':
                    myq_amount = (float(myq_payment.color_rate) * color_copies_billed) + \
                                (float(myq_payment.monochrome_rate) * mono_copies_billed)
                else:
                    myq_amount = float(myq_payment.monochrome_rate) * mono_copies_billed
        
        # Calculate VAT on base + MyQ subscription
        subtotal = base_amount + myq_amount
        vat_amount = float(subtotal * Decimal('0.16')) if self.add_vat else 0
        
        total_amount = subtotal + vat_amount
        
        return {
            'base_amount': base_amount,
            'myq_amount': myq_amount,
            'vat_amount': vat_amount,
            'total_amount': total_amount,
            'color_copies': color_copies_billed,
            'mono_copies': mono_copies_billed,
            'is_baseline': is_baseline,
            'has_previous': not is_first_reading
        }

    def update_payment_status(self):
        """Update payment status based on amounts - now checks all monthly bills"""
        # Calculate total unpaid amount across all meter readings
        total_billed = 0
        for reading in self.meter_readings.all():
            bill = self.calculate_month_bill(reading)
            total_billed += bill['total_amount']
        
        # Add one-off MyQ payment if applicable and not paid
        if self.add_myq and not self.billed_myq:
            myq_payment = self.myq_payments.first()
            if myq_payment and myq_payment.payment_type == 'one_off':
                total_billed += float(myq_payment.one_off_amount)
        
        if self.amount_paid >= total_billed and total_billed > 0:
            self.payment_status = 'Paid'
            self.remaining_balance = 0
        elif self.amount_paid > 0:
            self.payment_status = 'Partial'
            self.remaining_balance = total_billed - float(self.amount_paid)
        else:
            self.payment_status = 'Unpaid'
            self.remaining_balance = total_billed

class LeasePayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Mobile Money', 'Mobile Money'),
        ('Check', 'Check'),
        ('Card', 'Card'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('monthly_bill', 'Monthly Bill'),
        ('myq_one_off', 'MyQ One-Off Payment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='monthly_bill')
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)
    
    # Link to specific meter reading if this is a monthly bill payment
    meter_reading = models.ForeignKey(
        'MeterReading', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='payments'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"Payment {self.reference_number} - {self.amount}"

    class Meta:
        ordering = ['-payment_date', '-created_at']

class MyQPayment(models.Model):
    MYQ_PAYMENT_TYPE_CHOICES = [
        ('one_off', 'One-Off Payment'),
        ('subscription', 'Subscription'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey(
        'LeaseContract', 
        on_delete=models.CASCADE, 
        related_name='myq_payments'
    )
    payment_type = models.CharField(
        max_length=20, 
        choices=MYQ_PAYMENT_TYPE_CHOICES,
        default='subscription'
    )
    # For one-off payments
    one_off_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        null=True,
        blank=True
    )
    # For subscription payments - rates per copy
    color_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        null=True,
        blank=True,
        help_text="MyQ rate per color copy (for color machines)"
    )
    monochrome_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        null=True,
        blank=True,
        help_text="MyQ rate per monochrome copy"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"MyQ Payment - {self.get_payment_type_display()} - Lease {self.lease.lease_no}"

    class Meta:
        ordering = ['-created_at']
    
class LeaseMachineSwap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name='machine_swaps')
    old_machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name='swapped_from_leases')
    new_machine = models.ForeignKey(Machine, on_delete=models.PROTECT, related_name='swapped_to_leases')
    swap_reason = models.TextField()
    swapped_at = models.DateTimeField(auto_now_add=True)
    swapped_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='machine_swaps_performed'
    )

    def __str__(self):
        return f"{self.lease.lease_no} - {self.old_machine.serial_no} → {self.new_machine.serial_no}"

    class Meta:
        ordering = ['-swapped_at']

class SaleItem(models.Model):
    SALE_TYPE_CHOICES = [
        ('Machine', 'Machine'),
        ('Part', 'Part'),
        ('Accessory', 'Accessory'),
    ]
    
    sale = models.ForeignKey('Sale', on_delete=models.CASCADE, related_name='items')
    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES)
    machine = models.ForeignKey(Machine, on_delete=models.PROTECT, null=True, blank=True)
    part = models.ForeignKey(Part, on_delete=models.PROTECT, null=True, blank=True, related_name='sale_items')
    accessory = models.ForeignKey(Accessory, on_delete=models.PROTECT, null=True, blank=True, related_name='sale_accessories')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # VAT-exclusive unit price
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)  # unit_price * quantity (VAT-exclusive)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # VAT amount for this item
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)  # subtotal + vat_amount
    custom_item = models.JSONField(null=True, blank=True)

    def calculate_totals(self, apply_vat=False, vat_rate=0.16):
        """Calculate subtotal, VAT, and total price - ONLY for calculations, doesn't save"""
        # Subtotal is always VAT-exclusive: unit_price * quantity
        calculated_subtotal = self.unit_price * self.quantity
        
        # VAT amount calculation
        if apply_vat:
            calculated_vat_amount = calculated_subtotal * Decimal(str(vat_rate))
        else:
            calculated_vat_amount = Decimal('0')
            
        # Total price
        calculated_total_price = calculated_subtotal + calculated_vat_amount
        
        return calculated_subtotal, calculated_vat_amount, calculated_total_price

    def save(self, *args, **kwargs):
        # Validate quantity before saving
        if self.quantity < 1:
            raise ValidationError("Quantity must be at least 1.")
        
        # Check if this is a new instance (not an update)
        is_new = self.pk is None
        
        # Calculate subtotal (VAT-exclusive)
        self.subtotal = self.unit_price * self.quantity
        
        # Don't calculate VAT here - let the Sale model handle it
        # Just ensure we have default values
        if not hasattr(self, 'vat_amount') or self.vat_amount is None:
            self.vat_amount = Decimal('0')
        if not hasattr(self, 'total_price') or self.total_price is None:
            self.total_price = self.subtotal
        
        # Check stock before saving (only for new instances)
        if is_new:
            if self.sale_type == 'Part' and self.part:
                if self.part.quantity < self.quantity:
                    raise ValidationError("Insufficient stock")
            elif self.sale_type == 'Accessory' and self.accessory:
                if self.accessory.quantity < self.quantity:
                    raise ValidationError("Insufficient stock")
        
        # Save the sale item
        super().save(*args, **kwargs)
        
        # Update inventory ONLY for new instances (prevent double deduction)
        if is_new:
            if self.sale_type == 'Machine' and self.machine:
                self.machine.machine_status = 'Sold'
                self.machine.save()
            elif self.sale_type == 'Part' and self.part:
                self.part.quantity -= self.quantity
                if self.part.quantity <= 0:
                    self.part.part_status = 'Out of Stock'
                self.part.save()
            elif self.sale_type == 'Accessory' and self.accessory:
                self.accessory.quantity -= self.quantity
                if self.accessory.quantity <= 0:
                    self.accessory.acc_status = 'Out of Stock'
                self.accessory.save()

class Sale(models.Model):
    SALE_TYPE_CHOICES = [
        ('Internal', 'Internal'),
        ('Local', 'Local'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('Paid', 'Paid'),
        ('Partial', 'Partial'),
        ('Credit', 'Credit'),
        ('Overdue', 'Overdue'),
    ]

    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='Internal')
    local_client_name = models.CharField(max_length=255, blank=True, null=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale_no = models.CharField(max_length=50, unique=True)
    lpo = models.TextField(blank=True, default='')  
    client = models.ForeignKey(Client, on_delete=models.PROTECT, null=True, blank=True)
    sale_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    add_vat = models.BooleanField(default=False)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.16)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Payment fields
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Credit')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField(null=True, blank=True)
    payment_notes = models.TextField(blank=True)
    
    store_part_inquiry = models.ForeignKey(StorePartInquiry, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    store_acc_inquiry = models.ForeignKey(StoreAccessoryInquiry, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')

    def calculate_totals(self):
        """Recalculate all totals for this sale"""
        # Reset totals
        self.subtotal = Decimal('0')
        self.vat_total = Decimal('0')
        
        # Calculate totals from all items
        for item in self.items.all():
            item_subtotal = item.unit_price * item.quantity
            
            if self.add_vat:
                item_vat = item_subtotal * Decimal(str(self.vat_rate))
            else:
                item_vat = Decimal('0')
            
            item_total = item_subtotal + item_vat
            
            item.subtotal = item_subtotal
            item.vat_amount = item_vat
            item.total_price = item_total
            
            SaleItem.objects.filter(id=item.id).update(
                subtotal=item_subtotal,
                vat_amount=item_vat,
                total_price=item_total
            )
            
            self.subtotal += item_subtotal
            self.vat_total += item_vat
        
        self.total_amount = self.subtotal + self.vat_total
        
        # Update remaining balance
        self.remaining_balance = self.total_amount - self.amount_paid
        
        # Update payment status based on amounts
        self.update_payment_status()

    def update_payment_status(self):
        """Update payment status based on amount paid and due date"""
        if self.amount_paid >= self.total_amount:
            self.payment_status = 'Paid'
            self.remaining_balance = Decimal('0')
        elif self.amount_paid > 0:
            self.payment_status = 'Partial'
        else:
            self.payment_status = 'Credit'
        
        # Check if overdue
        if self.due_date and self.remaining_balance > 0 and timezone.now().date() > self.due_date:
            self.payment_status = 'Overdue'

    def save(self, *args, **kwargs):
        if not self.sale_no:
            self.sale_no = self.generate_sale_number()
        
        # Calculate remaining balance before saving
        if self.total_amount and self.amount_paid:
            self.remaining_balance = self.total_amount - self.amount_paid
        
        super().save(*args, **kwargs)

    def generate_sale_number(self):
        now = timezone.now()
        random_num = random.randint(10000, 99999)
        return f"SN-{now.month:02d}/{now.strftime('%y')}/{random_num}"

    @property
    def is_overdue(self):
        """Check if payment is overdue"""
        if self.due_date and self.remaining_balance > 0:
            return timezone.now().date() > self.due_date
        return False

class Payment(models.Model):
    """Track individual payments for a sale"""
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Check', 'Check'),
        ('Mobile Money', 'Mobile Money'),
        ('Card', 'Card'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Cash')
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update sale's amount_paid and payment status
        self.sale.amount_paid = self.sale.payments.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        self.sale.update_payment_status()
        self.sale.save()

    def delete(self, *args, **kwargs):
        sale = self.sale
        super().delete(*args, **kwargs)
        # Recalculate sale's amount_paid after deletion
        sale.amount_paid = sale.payments.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        sale.update_payment_status()
        sale.save()
    
class Delivery(models.Model):
    DELIVERY_TYPE_CHOICES = [
        ('Sale', 'Sale'),
        ('Lease', 'Lease'),
    ]
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('In Transit', 'In Transit'),
        ('Delivered', 'Delivered'),
        ('Failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lpo = models.TextField(blank=True, default='')
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_TYPE_CHOICES, default='Sale')
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='deliveries', null=True, blank=True)
    lease = models.ForeignKey(LeaseContract, on_delete=models.PROTECT, related_name='deliveries', null=True, blank=True)
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='delivery_tasks')
    delivery_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    delivery_notes = models.TextField(blank=True)
    customer_signature = models.BooleanField(default=False)
    delivery_no = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.delivery_no} - {self.get_delivery_type_display()}"

    def save(self, *args, **kwargs):
        if not self.delivery_no:
            self.delivery_no = self.generate_delivery_number()
        super().save(*args, **kwargs)

    def generate_delivery_number(self):
        now = timezone.now()
        random_num = random.randint(10000, 99999)
        return f"DN-{now.month:02d}/{now.strftime('%y')}/{random_num}"

    @property
    def client_name(self):
        if self.delivery_type == 'Sale':
            # Handle Sale with null client
            if self.sale:
                if self.sale.client:
                    return self.sale.client.client_name
                elif self.sale.local_client_name:
                    return self.sale.local_client_name
            return 'Unknown'
        else:  # Lease
            if self.lease and self.lease.client:
                return self.lease.client.client_name
            return 'Unknown'

    @property
    def client_location(self):
        if self.delivery_type == 'Sale':
            if self.sale and self.sale.client:
                return self.sale.client.client_location
            return 'Unknown'
        else:  # Lease
            if self.lease and self.lease.client:
                return self.lease.client.client_location
            return 'Unknown'

    @property
    def total_items(self):
        if self.delivery_type == 'Sale':
            return self.sale.items.count() if self.sale else 0
        return self.lease.part_inquiries.count() + self.lease.acc_inquiries.count() if self.lease else 0

    # In Delivery model's total_amount property
    @property
    def total_amount(self):
        if self.delivery_type == 'Sale':
            return sum(item.total_price for item in self.sale.items.all()) if self.sale else 0
        # Calculate lease total from inquiries
        if self.lease:
            part_total = self.lease.part_inquiries.aggregate(
                total=Sum('amount')
            )['total'] or 0
            acc_total = self.lease.acc_inquiries.aggregate(
                total=Sum('amount')
            )['total'] or 0
            return part_total + acc_total
        return 0

def message_file_path(instance, filename):
    """Generate a unique filepath for uploaded chat files"""
    # Get the file extension
    ext = filename.split('.')[-1]
    # Generate a unique filename
    filename = f"{uuid.uuid4().hex}.{ext}"
    # Return the upload path
    return os.path.join('chat_files', filename)
    
class ChatGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    members = models.ManyToManyField(CustomUser, related_name='chat_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ChatMessage(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default='text')
    content = models.TextField()
    file = models.FileField(upload_to=message_file_path, blank=True, null=True)
    file_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(CustomUser, related_name='read_messages', blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.email}: {self.content[:30]}..."
    
    def save(self, *args, **kwargs):
        # Generate the file URL if a file is uploaded
        if self.file and not self.file_url:
            self.file_url = self.file.url
        super().save(*args, **kwargs)

class LeasePartInquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name='part_inquiries')
    store_part_inquiry = models.ForeignKey(StorePartInquiry, on_delete=models.CASCADE, related_name='lease_part_inquiries', null=True, blank=True)
    part = models.ForeignKey(Part, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_amount = models.DecimalField(max_digits=10, decimal_places=2)  # Base unit amount without VAT
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)  # unit_amount * quantity
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.16'))
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # VAT amount
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)  # Final total with VAT
    apply_vat = models.BooleanField(default=False)
    date = models.DateField()
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_type = models.CharField(
        max_length=20, 
        choices=[('full', 'Full Payment'), ('partial', 'Partial Payment'), ('credit', 'Credit')],
        default='credit'
    )
    initial_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remaining_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(
        max_length=20,
        choices=[('Paid', 'Paid'), ('Partial', 'Partial'), ('Unpaid', 'Unpaid'), ('Overdue', 'Overdue')],
        default='Unpaid'
    )
    due_date = models.DateField(null=True, blank=True)
    payment_notes = models.TextField(blank=True, null=True)

    def calculate_totals(self):
        """Calculate subtotal, VAT, and total amount"""
        self.subtotal = self.unit_amount * self.quantity
        
        if self.apply_vat:
            self.vat_amount = self.subtotal * self.vat_rate
        else:
            self.vat_amount = Decimal('0')
            
        self.total_amount = self.subtotal + self.vat_amount

    def update_payment_status(self):
        """Update payment status based on amount paid"""
        from datetime import date
        
        if self.amount_paid >= self.total_amount:
            self.payment_status = 'Paid'
            self.remaining_balance = Decimal('0')
        elif self.amount_paid > 0:
            self.payment_status = 'Partial'
            self.remaining_balance = self.total_amount - self.amount_paid
        else:
            self.payment_status = 'Unpaid'
            self.remaining_balance = self.total_amount
        
        # Check if overdue
        if self.remaining_balance > 0 and self.due_date and self.due_date < date.today():
            self.payment_status = 'Overdue'
        
        self.save()

    def save(self, *args, **kwargs):
        self.calculate_totals()
        
        # Calculate remaining balance on creation
        if not self.pk:
            if self.payment_type == 'full':
                self.amount_paid = self.total_amount
                self.remaining_balance = Decimal('0')
                self.payment_status = 'Paid'
            elif self.payment_type == 'partial':
                self.amount_paid = self.initial_payment
                self.remaining_balance = self.total_amount - self.initial_payment
                self.payment_status = 'Partial'
            else:  # credit
                self.amount_paid = Decimal('0')
                self.remaining_balance = self.total_amount
                self.payment_status = 'Unpaid'
        
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-date']

class LeaseAccInquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name='acc_inquiries')
    store_acc_inquiry = models.ForeignKey(StoreAccessoryInquiry, on_delete=models.CASCADE, related_name='lease_acc_inquiries', null=True, blank=True)
    accessory = models.ForeignKey(Accessory, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_amount = models.DecimalField(max_digits=10, decimal_places=2)  # Price per unit
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)  # unit_amount * quantity
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal('0.16'))
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # VAT amount
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)  # Final total with VAT
    apply_vat = models.BooleanField(default=False)
    date = models.DateField()
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_type = models.CharField(
        max_length=20, 
        choices=[('full', 'Full Payment'), ('partial', 'Partial Payment'), ('credit', 'Credit')],
        default='credit'
    )
    initial_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remaining_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(
        max_length=20,
        choices=[('Paid', 'Paid'), ('Partial', 'Partial'), ('Unpaid', 'Unpaid'), ('Overdue', 'Overdue')],
        default='Unpaid'
    )
    due_date = models.DateField(null=True, blank=True)
    payment_notes = models.TextField(blank=True, null=True)

    def calculate_totals(self):
        """Calculate subtotal, VAT, and total amount"""
        self.subtotal = self.unit_amount * self.quantity
        
        if self.apply_vat:
            self.vat_amount = self.subtotal * self.vat_rate
        else:
            self.vat_amount = Decimal('0')
            
        self.total_amount = self.subtotal + self.vat_amount

    def save(self, *args, **kwargs):
        self.calculate_totals()
        
        # Calculate remaining balance on creation
        if not self.pk:
            if self.payment_type == 'full':
                self.amount_paid = self.total_amount
                self.remaining_balance = Decimal('0')
                self.payment_status = 'Paid'
            elif self.payment_type == 'partial':
                self.amount_paid = self.initial_payment
                self.remaining_balance = self.total_amount - self.initial_payment
                self.payment_status = 'Partial'
            else:  # credit
                self.amount_paid = Decimal('0')
                self.remaining_balance = self.total_amount
                self.payment_status = 'Unpaid'
        
        super().save(*args, **kwargs)

    def update_payment_status(self):
        """Update payment status based on amount paid"""
        from datetime import date
        
        if self.amount_paid >= self.total_amount:
            self.payment_status = 'Paid'
            self.remaining_balance = Decimal('0')
        elif self.amount_paid > 0:
            self.payment_status = 'Partial'
            self.remaining_balance = self.total_amount - self.amount_paid
        else:
            self.payment_status = 'Unpaid'
            self.remaining_balance = self.total_amount
        
        # Check if overdue
        if self.remaining_balance > 0 and self.due_date and self.due_date < date.today():
            self.payment_status = 'Overdue'
        
        self.save()

    class Meta:
        ordering = ['-date']

class LeasePartInquiryPayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Mobile Money', 'Mobile Money'),
        ('Check', 'Check'),
        ('Card', 'Card'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inquiry = models.ForeignKey(
        LeasePartInquiry, 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Cash')
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='part_inquiry_payments_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"Payment of {self.amount} for {self.inquiry.part.part_name}"


class LeaseAccInquiryPayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Mobile Money', 'Mobile Money'),
        ('Check', 'Check'),
        ('Card', 'Card'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inquiry = models.ForeignKey(
        LeaseAccInquiry, 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Cash')
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateField()
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='acc_inquiry_payments_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"Payment of {self.amount} for {self.inquiry.accessory.acc_name}"

class MeterReading(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name='meter_readings')
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    month = models.DateField()  
    meter_reading = models.PositiveIntegerField()
    color_meter_reading = models.PositiveIntegerField(null=True, blank=True)
    mono_meter_reading = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('lease', 'month') 
        ordering = ['-month']

    def __str__(self):
        return f"{self.lease.lease_no} - {self.month.strftime('%b %Y')}"
    
class Quotation(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Sent', 'Sent'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
        ('Expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation_no = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, null=True, blank=True)
    client_name = models.CharField(max_length=255, blank=True)
    client_location = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    valid_until = models.DateField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=16)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    include_vat = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if not self.quotation_no:
            self.quotation_no = self.generate_quotation_number()
        super().save(*args, **kwargs)

    def generate_quotation_number(self):
        now = timezone.now()
        random_num = random.randint(10000, 99999)
        return f"QUO-{now.month:02d}/{now.strftime('%y')}/{random_num}"

class QuotationItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('MachineType', 'Machine Type'),
        ('PartType', 'Part Type'),
        ('AccessoryType', 'Accessory Type'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    item_id = models.UUIDField()
    item_name = models.CharField(max_length=255)
    item_brand = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class Transfer(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='outgoing_transfers')
    to_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='incoming_transfers')
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True, null=True)

class TransferItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('Machine', 'Machine'),
        ('Part', 'Part'),
        ('Accessory', 'Accessory'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, null=True, blank=True)
    part = models.ForeignKey(Part, on_delete=models.CASCADE, null=True, blank=True)
    accessory = models.ForeignKey(Accessory, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    initial_quantity = models.PositiveIntegerField(default=0)  # Original quantity at transfer time

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Approved by Sales Manager', 'Approved by Sales Manager'),
        ('Rejected by Sales Manager', 'Rejected by Sales Manager'),
        ('Approved by Director', 'Approved by Director'),
        ('Rejected by Director', 'Rejected by Director'),
        ('Ordered', 'Ordered'),
        ('Cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.CharField(max_length=255)
    supplier_address = models.TextField(blank=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='created_purchase_orders')
    verified_by_sales_manager = models.ForeignKey(
        CustomUser, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        related_name='verified_sales_purchase_orders'
    )
    verified_by_director = models.ForeignKey(
        CustomUser, 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        related_name='verified_director_purchase_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    required_by_date = models.DateField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=2, default=16)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    include_vat = models.BooleanField(default=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Draft')
    notes = models.TextField(blank=True)
    uploaded_pdf = models.FileField(upload_to='purchase_orders/', null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.po_number:
            self.po_number = self.generate_po_number()
        super().save(*args, **kwargs)

    def generate_po_number(self):
        now = timezone.now()
        random_num = random.randint(10000, 99999)
        return f"PO-{now.month:02d}/{now.strftime('%y')}/{random_num}"

    def can_verify(self, user):
        """Check if user can verify this PO based on their role and current status"""
        if self.status == 'Submitted':
            if user.role == 'Sales Manager':
                return True
        elif self.status == 'Approved by Sales Manager':
            if user.role == 'Director':
                return True
        return False

class PurchaseOrderItem(models.Model):
    ITEM_TYPE_CHOICES = [
        ('MachineType', 'Machine Type'),
        ('PartType', 'Part Type'),
        ('AccessoryType', 'Accessory Type'),
        ('Custom', 'Custom Item'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    item_id = models.UUIDField(null=True, blank=True)
    item_name = models.CharField(max_length=255)
    item_brand = models.CharField(max_length=255, blank=True)
    item_code = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
