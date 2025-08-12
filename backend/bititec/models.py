import os
import random
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
import uuid
from django.utils import timezone
from django.db.models import Sum
from django.conf import settings

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
    
    username = None
    email = models.EmailField(_('email address'), unique=True)
    firstname = models.CharField(_('first name'), max_length=100)
    lastname = models.CharField(_('last name'), max_length=100)
    phonenumber = models.CharField(_('phone number'), max_length=20, null=True, blank=True)
    role = models.CharField(_('role'), max_length=20, choices=ROLE_CHOICES, default='Technician')
    active = models.BooleanField(_('active'), default=False)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)

    # Security fields
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    security_token = models.CharField(max_length=255, null=True, blank=True)  # For additional security
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['firstname', 'lastname', 'role']
    
    objects = CustomUserManager()
    
    def __str__(self):
        return self.email
    
    def is_locked(self):
        """Check if account is currently locked"""
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False
    
    def lock_account(self, duration_minutes=30):
        """Lock account for specified duration"""
        self.locked_until = timezone.now() + timedelta(minutes=duration_minutes)
        self.save(update_fields=['locked_until'])
    
    def unlock_account(self):
        """Unlock account and reset failed attempts"""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_failed_login = None
        self.save(update_fields=['failed_login_attempts', 'locked_until', 'last_failed_login'])
    
    def increment_failed_login(self):
        """Increment failed login attempts and lock if necessary"""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        
        if self.failed_login_attempts >= 3:
            # Lock for 30 minutes after 3 failed attempts
            self.lock_account(30)
        elif self.failed_login_attempts >= 5:
            # Lock for 1 hour after 5 failed attempts
            self.lock_account(60)
        elif self.failed_login_attempts >= 10:
            # Lock for 24 hours after 10 failed attempts
            self.lock_account(1440)
            
        self.save(update_fields=['failed_login_attempts', 'last_failed_login'])
    
    def reset_failed_login_attempts(self):
        """Reset failed login attempts on successful login"""
        if self.failed_login_attempts > 0:
            self.failed_login_attempts = 0
            self.last_failed_login = None
            self.save(update_fields=['failed_login_attempts', 'last_failed_login'])
    
    
    def save(self, *args, **kwargs):
        # Format phone number to Kenya format if provided
        if self.phonenumber:
            # Remove any spaces, dashes, or other non-digit characters except +
            phone = ''.join(filter(lambda x: x.isdigit() or x == '+', str(self.phonenumber)))
            
            # Handle different input formats
            if phone.startswith('0'):
                # Convert 0712345678 to +254712345678
                phone = '+254' + phone[1:]
            elif phone.startswith('254'):
                # Convert 254712345678 to +254712345678
                phone = '+' + phone
            elif phone.startswith('7') or phone.startswith('1'):
                # Convert 712345678 to +254712345678
                phone = '+254' + phone
            elif not phone.startswith('+254'):
                # If it doesn't match any pattern, assume it needs +254
                phone = '+254' + phone.lstrip('+')
            
            self.phonenumber = phone
        
        super().save(*args, **kwargs)
    
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

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
        ('Leased', 'Leased'),
        ('Out of Stock', 'Out of Stock'),
        ('Sold', 'Sold'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    machine_name = models.CharField(max_length=255)
    machine_brand = models.CharField(max_length=255)
    machine_type = models.CharField(max_length=255)
    serial_no = models.CharField(max_length=255, unique=True)
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

    def __str__(self):
        return f"{self.machine_name} - {self.serial_no}"

    @property
    def store_name(self):
        return self.store.store_name

    @property
    def store_id(self):
        return str(self.store.id)

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
    ref_no = models.CharField(max_length=255, unique=True)  
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

    def __str__(self):
        return f"{self.part_name} - {self.ref_no}"

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
                        'store_name': item.transfer.from_store.store_name
                    },
                    'to_store': {
                        'id': str(item.transfer.to_store.id),
                        'store_name': item.transfer.to_store.store_name
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
                        'store_name': item.transfer.from_store.store_name
                    },
                    'to_store': {
                        'id': str(item.transfer.to_store.id),
                        'store_name': item.transfer.to_store.store_name
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
    ref_no = models.CharField(max_length=255, unique=True)
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

    def __str__(self):
        return f"{self.acc_name} - {self.ref_no}"

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
                        'store_name': item.transfer.from_store.store_name
                    },
                    'to_store': {
                        'id': str(item.transfer.to_store.id),
                        'store_name': item.transfer.to_store.store_name
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
                        'store_name': item.transfer.from_store.store_name
                    },
                    'to_store': {
                        'id': str(item.transfer.to_store.id),
                        'store_name': item.transfer.to_store.store_name
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

class Call(models.Model):
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),  
        ('Closed', 'Closed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technician = models.ManyToManyField(CustomUser, related_name='calls')
    contract_type = models.CharField(max_length=100)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, null=True, blank=True)
    reported_by = models.CharField(max_length=255)
    reported_date = models.DateTimeField(default=timezone.now)
    item = models.ForeignKey(Machine, on_delete=models.PROTECT, null=True, blank=True)
    fault_reported = models.TextField()
    action_taken = models.TextField(blank=True, default='')
    meter_reading = models.PositiveIntegerField(default=0)
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
    
class StoreInquiry(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Issued', 'Issued'),
        ('Rejected', 'Rejected')
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='store_inquiries')
    part_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    requested_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT)
    requested_at = models.DateTimeField(auto_now_add=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    add_vat = models.BooleanField(default=False)
    is_issued = models.BooleanField(default=False)
    issued_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_inquiries')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    notes = models.TextField(blank=True)

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
    technician = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_leases', limit_choices_to={'role__in': ['Technician', 'Technician Manager']})

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
    unit_price = models.PositiveIntegerField()
    total_price = models.PositiveIntegerField()
    custom_item = models.JSONField(null=True, blank=True)

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)
        
        # Update inventory
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

    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='Internal')
    local_client_name = models.CharField(max_length=255, blank=True, null=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale_no = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, null=True, blank=True)
    sale_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    add_vat = models.BooleanField(default=False)
    store_inquiry = models.ForeignKey(StoreInquiry, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.sale_no:
            self.sale_no = self.generate_sale_number()
        super().save(*args, **kwargs)

    def generate_sale_number(self):
        now = timezone.now()
        random_num = random.randint(10000, 99999)
        return f"SN-{now.month:02d}/{now.strftime('%y')}/{random_num}"
    
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
    store_inquiry = models.ForeignKey(StoreInquiry, on_delete=models.CASCADE, related_name='lease_part_inquiries', null=True, blank=True)
    part = models.ForeignKey(Part, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    vat = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

class LeaseAccInquiry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name='acc_inquiries')
    accessory = models.ForeignKey(Accessory, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    vat = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

class MeterReading(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey(LeaseContract, on_delete=models.CASCADE, related_name='meter_readings')
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    month = models.DateField()  # Stores first day of the month
    meter_reading = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('lease', 'month')  # Prevent duplicate entries
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