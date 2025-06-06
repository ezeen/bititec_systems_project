import os
import random
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

# models.py update to add profile image
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
    phonenumber = models.PositiveIntegerField(_('phone number'))
    role = models.CharField(_('role'), max_length=20, choices=ROLE_CHOICES, default='Technician')
    active = models.BooleanField(_('active'), default=False)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['firstname', 'lastname', 'phonenumber', 'role']
    
    objects = CustomUserManager()
    
    def __str__(self):
        return self.email
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    color = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class PartType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    color = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    
class AccessoryType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    color = models.CharField(max_length=255)

    def __str__(self):
        return self.name

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
    description = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    machine_condition = models.CharField(max_length=20, choices=MACHINE_CONDITION_CHOICES)
    color_type = models.CharField(max_length=100)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='machines')
    supplier_name = models.CharField(max_length=255)
    machine_status = models.CharField(max_length=20, choices=MACHINE_STATUS_CHOICES)
    is_transfer = models.BooleanField(default=False)

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
    description = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    part_condition = models.CharField(max_length=20, choices=PART_CONDITION_CHOICES)
    color_type = models.CharField(max_length=100)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='parts')
    supplier_name = models.CharField(max_length=255)
    part_status = models.CharField(max_length=20, choices=PART_STATUS_CHOICES)
    is_transfer = models.BooleanField(default=False)

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
        result = SaleItem.objects.filter(part=self).aggregate(total=Sum('Initial_quantity'))
        return result['total'] or 0
    
    def available_quantity(self):
        """Get the quantity available"""
        return self.intial_quantity - self.leased_quantity() - self.sold_quantity()

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
    description = models.JSONField(default=list)
    created_at = models.DateTimeField(default=timezone.now)
    acc_condition = models.CharField(max_length=20, choices=ACCESSORY_CONDITION_CHOICES)
    color_type = models.CharField(max_length=100)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name='accessories')
    supplier_name = models.CharField(max_length=255)
    acc_status = models.CharField(max_length=20, choices=ACCESSORY_STATUS_CHOICES)
    is_transfer = models.BooleanField(default=False)

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

    class Meta:
        ordering = ['-created_at']

class ClientMachine(models.Model):
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
        ('Complete', 'Complete'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technician = models.ManyToManyField(CustomUser, related_name='calls')
    contract_type = models.CharField(max_length=100)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, null=True, blank=True)
    reported_by = models.CharField(max_length=255)
    reported_date = models.DateTimeField(default=timezone.now)
    item = models.ForeignKey(Machine, on_delete=models.PROTECT, null=True, blank=True)
    fault_reported = models.TextField()
    action_taken = models.JSONField(default=list)
    meter_reading = models.PositiveIntegerField(default=0)
    parts_required = models.JSONField(default=list)
    parts_used = models.JSONField(default=list)
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

    def __str__(self):
        if self.client:
            return f"{self.ticket_no} - {self.client.client_name}"
        else:
            return f"{self.ticket_no} - {self.client_name} ({self.client_location})"

    def save(self, *args, **kwargs):
        if not self.ticket_no:
            self.ticket_no = self.generate_ticket_number()
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
            return self.sale.client.client_name if self.sale else 'Unknown'
        return self.lease.client.client_name if self.lease else 'Unknown'

    @property
    def client_location(self):
        if self.delivery_type == 'Sale':
            return self.sale.client.client_location if self.sale else 'Unknown'
        return self.lease.client.client_location if self.lease else 'Unknown'

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
    store_inquiry = models.ForeignKey(StoreInquiry, on_delete=models.CASCADE, related_name='lease_part_inquiries')
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