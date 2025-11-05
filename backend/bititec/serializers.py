from decimal import Decimal
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Accessory, AccessoryType, ChatGroup, ChatMessage, Client, ClientMachine, CustomUser, Delivery, LeaseAccInquiry, LeaseAccInquiryPayment, LeaseContract, LeaseMachineSwap, LeasePartInquiry, LeasePartInquiryPayment, LeasePayment, LeaseServiceSchedule, MachineType, Machine, MeterReading, MyQPayment, PartType, Part, Payment, PurchaseOrder, PurchaseOrderItem, Quotation, QuotationItem, Sale, SaleItem, Store, Call, StorePartInquiry, StoreAccessoryInquiry, Transfer, TransferItem
from django.db.models import Sum
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.db import transaction

class StoreSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    storeName = serializers.CharField(source='store_name')
    storeLocation = serializers.CharField(source='store_location')
    storeSize = serializers.IntegerField(source='store_size')
    machines_count = serializers.SerializerMethodField()
    partsCount = serializers.IntegerField(source='parts_count', read_only=True)
    accessoriesCount = serializers.IntegerField(source='accessories_count', read_only=True)

    class Meta:
        model = Store
        fields = [
            'id', 'storeName', 'storeLocation', 'storeSize',
            'machines_count', 'partsCount', 'accessoriesCount'
        ]
        extra_kwargs = {
            'store_name': {'write_only': True},
            'store_location': {'write_only': True},
            'store_size': {'write_only': True}
        }

    def create(self, validated_data):
        return Store.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.store_name = validated_data.get('store_name', instance.store_name)
        instance.store_location = validated_data.get('store_location', instance.store_location)
        instance.store_size = validated_data.get('store_size', instance.store_size)
        instance.save()
        return instance
    
    def get_machines_count(self, obj):
        return obj.machines.count()

class UserSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    profile_image = serializers.ImageField(read_only=True)
    phonenumber = serializers.CharField(
        required=False, 
        allow_null=True,
        allow_blank=True,
        max_length=20
    )
    stores = StoreSerializer(many=True, read_only=True)
    store_ids = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        source='stores',
        many=True,
        write_only=True,
        required=False
    )
    is_locked = serializers.SerializerMethodField()
    failed_login_attempts = serializers.IntegerField(read_only=True)
    locked_until = serializers.DateTimeField(read_only=True)
    last_failed_login = serializers.DateTimeField(read_only=True)
    keys = serializers.DictField(read_only=True)
    all_permissions = serializers.SerializerMethodField()

    def get_is_locked(self, obj):
        return obj.is_locked()
    
    def get_all_permissions(self, obj):
        return obj.get_all_permissions()

    def validate_phonenumber(self, value):
        """Validate phone number format"""
        if not value:
            return value
            
        phone = ''.join(filter(lambda x: x.isdigit() or x == '+', str(value)))
        
        if phone and not (phone.startswith('+254') or phone.startswith('254') or 
                         phone.startswith('0') or phone.startswith('7') or phone.startswith('1')):
            raise serializers.ValidationError("Invalid phone number format for Kenya")
        
        return value
    
    def to_representation(self, instance):
        """Customize the serialized output"""
        data = super().to_representation(instance)
        
        # Handle profile image URL
        if instance.profile_image and instance.profile_image.name:
            try:
                request = self.context.get('request')
                if request:
                    data['profile_image'] = request.build_absolute_uri(instance.profile_image.url)
                else:
                    data['profile_image'] = instance.profile_image.url
            except ValueError:
                data['profile_image'] = None
        else:
            data['profile_image'] = None
            
        # Ensure phone number formatting
        if instance.phonenumber:
            data['phonenumber'] = instance.phonenumber
        else:
            data['phonenumber'] = ''
            
        return data
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'firstname', 'lastname',
            'phonenumber', 'role', 'active', 'profile_image', 'is_locked',
            'failed_login_attempts', 'locked_until', 'last_failed_login',
            'keys', 'all_permissions', 'stores', 'store_ids'
        ]
        extra_kwargs = {'password': {'write_only': True}, 'role': {'read_only': True}}
        
class RegisterSerializer(serializers.ModelSerializer):
    store_ids = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        source='stores',
        many=True,
        write_only=True,
        required=False
    )
    phonenumber = serializers.CharField(
        required=False, 
        allow_blank=True,
        max_length=20
    )
    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'firstname', 'lastname', 'phonenumber', 'role', 'store_ids']
        extra_kwargs = {'password': {'write_only': True}}

    def validate_phonenumber(self, value):
        """Validate phone number format for registration"""
        if not value:  # Allow empty values during registration
            return value
            
        # Remove spaces and other formatting
        phone = ''.join(filter(lambda x: x.isdigit() or x == '+', str(value)))
        
        # Basic validation for Kenya phone numbers
        if phone and not (phone.startswith('+254') or phone.startswith('254') or 
                         phone.startswith('0') or phone.startswith('7') or phone.startswith('1')):
            raise serializers.ValidationError("Invalid phone number format for Kenya")
        
        return value

    def create(self, validated_data):
        stores = validated_data.pop('stores', [])

        validated_data['active'] = validated_data['role'] in ['Director', 'Super Admin']
        user = CustomUser.objects.create_user(**validated_data)

        if stores:
            user.stores.set(stores)

        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['email'] = self.user.email
        data['role'] = self.user.role
        data['active'] = self.user.active
        data['keys'] = self.user.keys
        data['all_permissions'] = self.user.get_all_permissions()
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = user.role
        token['keys'] = user.keys
        return token
    
class EnhancedUserSerializer(serializers.ModelSerializer):
    keys = serializers.DictField(read_only=True)
    all_permissions = serializers.SerializerMethodField()
    key_audit = serializers.SerializerMethodField()

    def get_all_permissions(self, obj):
        return obj.get_all_permissions()
    
    def get_key_audit(self, obj):
        if self.context['request'].user.role in ['Director', 'Super Admin']:
            return {
                'granted_by': obj.keys_granted_by.email if obj.keys_granted_by else None,
                'granted_at': obj.keys_granted_at,
                'reason': obj.keys_reason
            }
        return None

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'firstname', 'lastname', 'phonenumber', 'role', 
            'active', 'profile_image', 'is_locked', 'failed_login_attempts', 
            'locked_until', 'last_failed_login', 'keys', 
            'all_permissions', 'key_audit'
        ]
    
class BaseTypeSerializer(serializers.ModelSerializer):
    image1_url = serializers.SerializerMethodField()
    image2_url = serializers.SerializerMethodField()

    class Meta:
        abstract = True
        fields = [
            'id', 'name', 'type', 'brand', 'color', 'description',
            'image1', 'image2', 'image1_url', 'image2_url',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def get_image1_url(self, obj):
        if obj.image1:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image1.url) if request else obj.image1.url
        return None

    def get_image2_url(self, obj):
        if obj.image2:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.image2.url) if request else obj.image2.url
        return None

    def update(self, instance, validated_data):
        image1 = validated_data.pop('image1', None)
        image2 = validated_data.pop('image2', None)

        if image1 is not None:
            if instance.image1:
                instance.image1.delete()
            instance.image1 = image1
        if image2 is not None:
            if instance.image2:
                instance.image2.delete()
            instance.image2 = image2

        # Update remaining fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

class AccessoryTypeSerializer(BaseTypeSerializer):
    class Meta(BaseTypeSerializer.Meta):
        model = AccessoryType

class MachineTypeSerializer(BaseTypeSerializer):
    class Meta(BaseTypeSerializer.Meta):
        model = MachineType

class PartTypeSerializer(BaseTypeSerializer):
    class Meta(BaseTypeSerializer.Meta):
        model = PartType

class MachineSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.store_name', read_only=True)
    store_id = serializers.UUIDField(source='store.id', read_only=True)
    store = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        write_only=True,
        required=True
    )
    source_transfer = serializers.PrimaryKeyRelatedField(read_only=True)
    donated_parts = serializers.SerializerMethodField()
    installed_parts = serializers.SerializerMethodField()
    qr_code_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Machine
        fields = [
            'id', 'machine_name', 'machine_brand', 'machine_type', 'serial_no', 'unit_value',
            'quantity', 'condition_description', 'created_at', 'machine_condition', 'color_type',
            'store',  'store_id', 'store_name', 'supplier_name', 'machine_status', 'is_transfer', 
            'source_transfer', 'donated_parts', 'installed_parts', 'qr_code', 'qr_code_url', 
            'auto_generated_serial'
        ]
        extra_kwargs = {
            'created_at': {'read_only': True},
            'qr_code': {'read_only': True},
            'auto_generated_serial': {'read_only': True},
            'serial_no': {'required': False}
        }

    def validate(self, data):
        # Only require store during creation
        if self.instance is None and 'store' not in data:
            raise serializers.ValidationError({"store": "This field is required."})
        return data

    def create(self, validated_data):
        return Machine.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
    def get_qr_code_url(self, obj):
        """Get full URL for QR code image"""
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None
    
    def get_donated_parts(self, obj):
        parts = Part.objects.filter(origin_machine=obj)
        return PartSerializer(parts, many=True).data

    def get_installed_parts(self, obj):
        parts = Part.objects.filter(current_machine=obj)
        return PartSerializer(parts, many=True).data

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'client_name', 'client_location', 'created_at']
        read_only_fields = ['created_at']
    
class BasicPartSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.store_name', read_only=True)
    store_id = serializers.UUIDField(source='store.id', read_only=True)
    class Meta:
        model = Part
        fields = ['id', 'part_name', 'ref_no', 'store_name', 'store_id']  

class BasicAccessorySerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.store_name', read_only=True)
    store_id = serializers.UUIDField(source='store.id', read_only=True)
    class Meta:
        model = Accessory
        fields = ['id', 'acc_name', 'ref_no', 'store_name', 'store_id']  

class MeterReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeterReading
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        # Check if reading for this month already exists
        if MeterReading.objects.filter(
            lease=data['lease'],
            month=data['month']
        ).exists():
            raise serializers.ValidationError("Meter reading for this month already exists")
        return data
    
class LeaseMachineSwapSerializer(serializers.ModelSerializer):
    old_machine_name = serializers.CharField(source='old_machine.machine_name', read_only=True)
    old_machine_serial = serializers.CharField(source='old_machine.serial_no', read_only=True)
    new_machine_name = serializers.CharField(source='new_machine.machine_name', read_only=True)
    new_machine_serial = serializers.CharField(source='new_machine.serial_no', read_only=True)
    swapped_by_name = serializers.CharField(source='swapped_by.get_full_name', read_only=True)
    
    lease = serializers.PrimaryKeyRelatedField(
        queryset=LeaseContract.objects.all(),
        write_only=True
    )
    old_machine = serializers.PrimaryKeyRelatedField(
        queryset=Machine.objects.all(),
        write_only=True
    )
    new_machine = serializers.PrimaryKeyRelatedField(
        queryset=Machine.objects.all(),
        write_only=True
    )
    
    class Meta:
        model = LeaseMachineSwap
        fields = [
            'id', 'lease', 'old_machine', 'new_machine', 'swap_reason', 
            'swapped_at', 'swapped_by', 'old_machine_name', 'old_machine_serial',
            'new_machine_name', 'new_machine_serial', 'swapped_by_name'
        ]
        extra_kwargs = {
            'swapped_at': {'read_only': True},
            'swapped_by': {'read_only': True},
        }
    
    def create(self, validated_data):
        validated_data['swapped_by'] = self.context['request'].user
        return super().create(validated_data)
    
class LeasePaymentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    amount = serializers.FloatField()  
    
    class Meta:
        model = LeasePayment
        fields = [
            'id', 'lease', 'amount', 'payment_method', 'reference_number',
            'payment_date', 'notes', 'created_at', 'created_by', 'created_by_name'
        ]
        read_only_fields = ['created_at', 'created_by']
    
    def to_representation(self, instance):
        """Override to ensure amount is returned as float"""
        representation = super().to_representation(instance)
        if representation.get('amount') is not None:
            representation['amount'] = float(representation['amount'])
        return representation
    
class MyQPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyQPayment
        fields = [
            'id', 'lease', 'payment_type', 'one_off_amount', 
            'color_rate', 'monochrome_rate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
class LeaseContractSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.client_name', read_only=True)
    client_location = serializers.CharField(source='client.client_location', read_only=True)
    item_name = serializers.CharField(source='item.machine_name', read_only=True)
    serial_no = serializers.CharField(source='item.serial_no', read_only=True)
    store_name = serializers.CharField(source='store.store_name', read_only=True)
    item = MachineSerializer(read_only=True)

    client_id = serializers.PrimaryKeyRelatedField(
        source='client',
        queryset=Client.objects.all(),
        write_only=True,
        required=False
    )
    
    item_id = serializers.PrimaryKeyRelatedField(
        source='item',
        queryset=Machine.objects.all(),
        write_only=True,
        required=False
    )
    client = ClientSerializer(read_only=True)
    meter_readings = MeterReadingSerializer(many=True, read_only=True)
    missing_readings = serializers.SerializerMethodField()
    
    # Account handler serializer fields
    account_handler = UserSerializer(read_only=True)
    account_handler_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(is_active=True),
        write_only=True,
        source='account_handler',
        required=False,
        allow_null=True
    )
    account_handler_name = serializers.CharField(source='account_handler.get_full_name', read_only=True)
    account_handler_email = serializers.CharField(source='account_handler.email', read_only=True)
    
    # Technician serializer fields (keep for backward compatibility)
    technician = UserSerializer(read_only=True)
    technician_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(
            role__in=['Technician', 'Technician Manager']
        ),
        write_only=True,
        source='technician',
        required=False,
        allow_null=True
    )
    machine_swaps = LeaseMachineSwapSerializer(many=True, read_only=True)
    
    # Payment fields - use FloatField for frontend compatibility
    payments = LeasePaymentSerializer(many=True, read_only=True)
    payments_count = serializers.IntegerField(source='payments.count', read_only=True)
    myq_payments = MyQPaymentSerializer(many=True, read_only=True)
    myq_payment_data = serializers.JSONField(
        write_only=True, 
        required=False,
        default=None  # or default=dict
    )

    monochrome_rate = serializers.FloatField(default=1.50)
    color_rate = serializers.FloatField(default=4.50)
    amount_paid = serializers.FloatField(default=0)
    remaining_balance = serializers.FloatField(default=0)
    total_billed = serializers.SerializerMethodField()
    
    class Meta:
        model = LeaseContract
        fields = [
            'id', 'client', 'client_name', 'client_location', 'department', 
            'item', 'item_id', 'item_name', 'client_id',
            'serial_no', 'store', 'store_name', 'from_date', 'to_date', 'add_vat', 'add_myq',
            'billed_myq', 'is_active', 'contract_type', 'lease_no', 'created_at', 'client', 
            'meter_readings', 'missing_readings', 'technician', 'technician_id',
            'account_handler', 'account_handler_id', 'account_handler_name', 'account_handler_email',
            'machine_swaps', 'myq_payments', 'myq_payment_data',
            'monochrome_rate', 'color_rate', 'amount_paid', 'remaining_balance',
            'payment_status', 'payment_notes', 'payments', 'payments_count', 'total_billed',
            'initial_mono_counter', 'initial_color_counter', 
        ]
        extra_kwargs = {
            'created_at': {'read_only': True},
            'lease_no': {'read_only': True},
            'department': {'required': False},
            'contract_type': {'required': False},
            'from_date': {'required': False},
            'to_date': {'required': False},
            'store': {'required': False},
        }
    
    def get_total_amount(self, obj):
        return float(obj.calculate_total_amount())

    def get_missing_readings(self, obj):
        months_missing = []
        current_date = timezone.now().date()
        start_date = obj.from_date
        
        while start_date <= current_date:
            if not obj.meter_readings.filter(month__month=start_date.month, 
                                           month__year=start_date.year).exists():
                months_missing.append(start_date.strftime('%Y-%m'))
            start_date += relativedelta(months=1)
            
        return months_missing

    def to_representation(self, instance):
        """Override to ensure decimal fields are returned as floats"""
        representation = super().to_representation(instance)
        
        # Convert decimal fields to floats for frontend compatibility
        decimal_fields = ['monthly_rate', 'amount_paid', 'remaining_balance', 'initial_payment']
        for field in decimal_fields:
            if field in representation and representation[field] is not None:
                representation[field] = float(representation[field])
        
        return representation
    
    def get_total_billed(self, obj):
        """Calculate total amount billed across all meter readings"""
        total = 0
        for reading in obj.meter_readings.all():
            bill = obj.calculate_month_bill(reading)
            total += bill['total_amount']
        
        # Add one-off MyQ if not yet paid
        if obj.add_myq and not obj.billed_myq:
            myq_payment = obj.myq_payments.first()
            if myq_payment and myq_payment.payment_type == 'one_off':
                total += float(myq_payment.one_off_amount)
        
        return float(total)
    
    def create(self, validated_data):
        myq_payment_data = validated_data.pop('myq_payment_data', None)
        
        with transaction.atomic():
            lease = super().create(validated_data)
            
            # Create MyQ payment record if MyQ is enabled
            if lease.add_myq and myq_payment_data:
                MyQPayment.objects.create(
                    lease=lease,
                    payment_type=myq_payment_data.get('payment_type', 'subscription'),
                    one_off_amount=myq_payment_data.get('one_off_amount', 0),
                    color_rate=myq_payment_data.get('color_rate', 0),
                    monochrome_rate=myq_payment_data.get('monochrome_rate', 0)
                )
            
            return lease
        
    def update(self, instance, validated_data):
        # Track if machine is changing
        original_machine = instance.item
        new_machine = validated_data.get('item', instance.item)
        
        # Track lease active status change
        original_active = instance.is_active
        new_active = validated_data.get('is_active', instance.is_active)
        
        with transaction.atomic():
            # Handle machine change
            if original_machine != new_machine:
                # Return original machine to store
                original_machine.machine_status = 'Available'
                original_machine.save()
                
            # Only assign new machine if lease is still active
            if new_active:
                new_machine.machine_status = 'Leased'
                new_machine.save()
            
            # Handle lease termination/reinstatement
            if original_active != new_active:
                if not new_active:  # Terminating lease
                    instance.item.machine_status = 'Available'
                else:  # Reinstating lease
                    instance.item.machine_status = 'Leased'
                instance.item.save()
            
            # Update lease fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
                
            instance.save()
            
            return instance
        
    def update(self, instance, validated_data):
        myq_payment_data = validated_data.pop('myq_payment_data', None)
        
        with transaction.atomic():
            lease = super().update(instance, validated_data)
            
            # Update or create MyQ payment
            if lease.add_myq and myq_payment_data:
                myq_payment, created = MyQPayment.objects.get_or_create(
                    lease=lease,
                    defaults={
                        'payment_type': myq_payment_data.get('payment_type', 'subscription'),
                        'one_off_amount': myq_payment_data.get('one_off_amount', 0),
                        'color_rate': myq_payment_data.get('color_rate', 0),
                        'monochrome_rate': myq_payment_data.get('monochrome_rate', 0)
                    }
                )
                if not created:
                    myq_payment.payment_type = myq_payment_data.get('payment_type', myq_payment.payment_type)
                    myq_payment.one_off_amount = myq_payment_data.get('one_off_amount', myq_payment.one_off_amount)
                    myq_payment.color_rate = myq_payment_data.get('color_rate', myq_payment.color_rate)
                    myq_payment.monochrome_rate = myq_payment_data.get('monochrome_rate', myq_payment.monochrome_rate)
                    myq_payment.save()
            elif not lease.add_myq:
                # Remove MyQ payment if MyQ is disabled
                MyQPayment.objects.filter(lease=lease).delete()
            
            return lease
    
class LeaseServiceScheduleSerializer(serializers.ModelSerializer):
    lease_no = serializers.CharField(source='lease.lease_no', read_only=True)
    client_name = serializers.CharField(source='lease.client.client_name', read_only=True)
    item_name = serializers.CharField(source='lease.item.machine_name', read_only=True)
    serial_no = serializers.CharField(source='lease.item.serial_no', read_only=True)
    default_technicians = UserSerializer(many=True, read_only=True)
    default_technician_ids = serializers.PrimaryKeyRelatedField(
        source='default_technicians',
        many=True,
        queryset=CustomUser.objects.all(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = LeaseServiceSchedule
        fields = [
            'id', 'lease', 'lease_no', 'client_name', 'item_name', 'serial_no',
            'service_type', 'frequency', 'frequency_months', 'start_date', 
            'end_date', 'default_technicians', 'default_technician_ids', 
            'lpo', 'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']

class LeasePartInquiryPaymentSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = LeasePartInquiryPayment
        fields = [
            'id', 'inquiry', 'amount', 'payment_method', 
            'reference_number', 'payment_date', 'notes', 
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']

class LeasePartInquirySerializer(serializers.ModelSerializer):
    part = BasicPartSerializer(read_only=True)
    lease = LeaseContractSerializer(read_only=True)
    part_id = serializers.PrimaryKeyRelatedField(queryset=Part.objects.all(), write_only=True, source='part')
    lease_id = serializers.PrimaryKeyRelatedField(
        queryset=LeaseContract.objects.all(),
        write_only=True,
        source='lease'
    )
    store_part_inquiry_id = serializers.PrimaryKeyRelatedField(
        queryset=StorePartInquiry.objects.all(),
        write_only=True,
        source='store_part_inquiry',
        required=False,
    )
    payments = LeasePartInquiryPaymentSerializer(many=True, read_only=True)
    payments_count = serializers.SerializerMethodField()

    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    vat_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    vat_rate = serializers.DecimalField(
        max_digits=5, 
        decimal_places=4, 
        default=Decimal('0.16')
    )
    
    class Meta:
        model = LeasePartInquiry
        fields = [
            'id', 'lease', 'part', 'quantity', 'unit_amount', 'subtotal',
            'vat_rate', 'vat_amount', 'total_amount', 'apply_vat', 'date', 
            'is_paid', 'created_at', 'updated_at', 'part_id', 'lease_id', 
            'store_part_inquiry_id', 'payment_type', 'initial_payment',
            'amount_paid', 'remaining_balance', 'payment_status', 
            'due_date', 'payment_notes', 'payments', 'payments_count'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'subtotal', 'vat_amount', 
            'total_amount', 'amount_paid', 'remaining_balance', 'payment_status'
        ]
    
    def get_payments_count(self, obj):
        return obj.payments.count()

class PartSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.storeName', read_only=True)
    store_location = serializers.CharField(source='store.storeLocation', read_only=True)
    store_id = serializers.UUIDField(source='store.id', read_only=True)
    store = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        write_only=True,
        required=True
    )
    sold_items = serializers.SerializerMethodField()
    lease_inquiries = LeasePartInquirySerializer(
        many=True, 
        read_only=True,
        source='leasepartinquiry_set'  # Match the reverse relation name
    )
    leased_quantity = serializers.SerializerMethodField()
    sold_quantity = serializers.SerializerMethodField()
    source_transfer = serializers.PrimaryKeyRelatedField(read_only=True)
    transferred_quantity = serializers.ReadOnlyField()
    received_quantity = serializers.ReadOnlyField()
    transfer_history = serializers.ReadOnlyField()
    origin_machine = serializers.SerializerMethodField()
    current_machine = serializers.SerializerMethodField()
    origin_machine_id = serializers.PrimaryKeyRelatedField(
        queryset=Machine.objects.all(),
        source='origin_machine',
        write_only=True,
        required=False,
        allow_null=True
    )
    current_machine_id = serializers.PrimaryKeyRelatedField(
        queryset=Machine.objects.all(),
        source='current_machine',
        write_only=True,
        required=False,
        allow_null=True
    )
    qr_code_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Part
        fields = [
            'id', 'part_name', 'part_brand', 'part_type', 'ref_no', 'unit_value', 'intial_quantity', 'quantity', 'condition_description', 
            'created_at', 'part_condition', 'color_type', 'store', 'store_id', 'store_name', 'supplier_name', 'part_status', 'is_transfer', 
            'leased_quantity', 'sold_quantity', 'transferred_quantity', 'received_quantity', 'transfer_history', 'lease_inquiries', 'sold_items', 
            'source_transfer', 'origin_machine', 'current_machine', 'origin_machine_id', 'current_machine_id', 'removed_date', 'installed_date', 
            'store_location', 'qr_code', 'qr_code_url', 'auto_generated_ref'
        ]
        extra_kwargs = {
            'store': {'write_only': True},
            'created_at': {'read_only': True},
            'qr_code': {'read_only': True},
            'auto_generated_ref': {'read_only': True},
            'ref_no': {'required': False}
        }

    def validate_serial_no(self, value):
        if self.instance and self.instance.ref_no == value:
            return value
        if Part.objects.filter(serial_no=value).exists():
            raise serializers.ValidationError("A part with this reference number already exists.")
        return value

    def create(self, validated_data):
        return Part.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
    def get_leased_quantity(self, obj):
        return obj.leasepartinquiry_set.aggregate(
            total=Sum('quantity')
        )['total'] or 0

    def get_sold_quantity(self, obj):
        return SaleItem.objects.filter(part=obj).aggregate(
            total=Sum('quantity')
        )['total'] or 0
    
    def get_sold_items(self, obj):
        sale_items = obj.sale_items.select_related('sale__client').all()
        return [{
            'id': item.id,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price,
            'sale': {
                'id': item.sale.id,
                'sale_date': item.sale.sale_date,
                'client': {
                    'client_name': item.sale.client.client_name if item.sale.client else 'N/A',
                    'client_location': item.sale.client.client_location if item.sale.client else 'N/A'
                } if item.sale else None  # Handle case where sale is None (though unlikely)
            }
        } for item in sale_items if item.sale]
    
    def get_qr_code_url(self, obj):
        """Get full URL for QR code image"""
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None
    
    def get_origin_machine(self, obj):
        if obj.origin_machine:
            return {
                'id': str(obj.origin_machine.id),
                'serial_no': obj.origin_machine.serial_no,
                'name': obj.origin_machine.machine_name
            }
        return None

    def get_current_machine(self, obj):
        if obj.current_machine:
            return {
                'id': str(obj.current_machine.id),
                'serial_no': obj.current_machine.serial_no,
                'name': obj.current_machine.machine_name
            }
        return None
        
class LeaseAccInquirySerializer(serializers.ModelSerializer):
    accessory = BasicAccessorySerializer(read_only=True)
    lease = LeaseContractSerializer(read_only=True)
    accessory_id = serializers.PrimaryKeyRelatedField(queryset=Accessory.objects.all(), write_only=True, source='accessory')

    store_acc_inquiry_id = serializers.PrimaryKeyRelatedField(
        queryset=StorePartInquiry.objects.all(),
        write_only=True,
        source='store_acc_inquiry',
        required=False,
    )

    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    vat_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = LeaseAccInquiry
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
class AccessorySerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.store_name', read_only=True)
    store_id = serializers.UUIDField(source='store.id', read_only=True)
    store = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        write_only=True,
        required=True
    )
    leased_quantity = serializers.SerializerMethodField()
    sold_quantity = serializers.SerializerMethodField()
    lease_inquiries = LeaseAccInquirySerializer(
        many=True,
        read_only=True,
        source='leaseaccinquiry_set'
    )
    sold_items = serializers.SerializerMethodField()
    source_transfer = serializers.PrimaryKeyRelatedField(read_only=True)
    transferred_quantity = serializers.ReadOnlyField()
    received_quantity = serializers.ReadOnlyField()
    transfer_history = serializers.ReadOnlyField()
    qr_code_url = serializers.SerializerMethodField()


    class Meta:
        model = Accessory
        fields = [
            'id',
            'acc_name',
            'acc_brand',
            'acc_type',
            'ref_no',
            'unit_value',
            'intial_quantity',
            'quantity',
            'condition_description',
            'created_at',
            'acc_condition',
            'color_type',
            'store',
            'store_id',
            'store_name',
            'supplier_name',
            'acc_status',
            'is_transfer',
            'leased_quantity', 
            'sold_quantity',
            'lease_inquiries', 
            'transferred_quantity', 'received_quantity', 'transfer_history',
            'sold_items',
            'source_transfer',
            'qr_code', 'qr_code_url', 'auto_generated_ref'
        ]
        extra_kwargs = {
            'store': {'write_only': True},
            'created_at': {'read_only': True},
            'qr_code': {'read_only': True},
            'auto_generated_ref': {'read_only': True},
            'ref_no': {'required': False}
        }

    def validate_serial_no(self, value):
        if self.instance and self.instance.ref_no == value:
            return value
        if Accessory.objects.filter(serial_no=value).exists():
            raise serializers.ValidationError("An accessory with this reference number already exists.")
        return value

    def create(self, validated_data):
        return Accessory.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    
    def get_qr_code_url(self, obj):
        """Get full URL for QR code image"""
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None
    
    def get_leased_quantity(self, obj):
        return obj.leaseaccinquiry_set.aggregate(
            total=Sum('quantity')
        )['total'] or 0

    def get_sold_quantity(self, obj):
        return SaleItem.objects.filter(accessory=obj).aggregate(
            total=Sum('quantity')
        )['total'] or 0
    
    def get_sold_items(self, obj):
        sale_items = obj.sale_accessories.select_related('sale__client').all()
        return [{
            'id': item.id,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'total_price': item.total_price,
            'sale': {
                'id': item.sale.id,
                'sale_date': item.sale.sale_date,
                'client': {
                    'client_name': item.sale.client.client_name if item.sale.client else 'N/A',
                    'client_location': item.sale.client.client_location if item.sale.client else 'N/A'
                } if item.sale else None  # Handle case where sale is None (though unlikely)
            }
        } for item in sale_items if item.sale]

class CallSerializer(serializers.ModelSerializer):
    client_name_display = serializers.CharField(source='client.client_name', read_only=True)
    client_location_display = serializers.CharField(source='client.client_location', read_only=True)
    item_name = serializers.SerializerMethodField()
    serial_no = serializers.SerializerMethodField()
    store_name = serializers.SerializerMethodField()
    service_type = serializers.ChoiceField(choices=Call.SERVICE_TYPE_CHOICES)
    
    # Nested objects (these need to be proper serializers)
    client = ClientSerializer(read_only=True)
    item = MachineSerializer(read_only=True)
    technician = UserSerializer(many=True, read_only=True)
    
    # For write operations - Made these optional and allow null
    client_id = serializers.PrimaryKeyRelatedField(
        source='client',
        queryset=Client.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    item_id = serializers.PrimaryKeyRelatedField(
        source='item',
        queryset=Machine.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    technician_ids = serializers.PrimaryKeyRelatedField(
        source='technician',
        many=True,
        queryset=CustomUser.objects.all(),
        write_only=True
    )
    
    # Walk-in specific fields - these should be writable
    client_name = serializers.CharField(required=False, allow_blank=True)
    client_location = serializers.CharField(required=False, allow_blank=True)
    walk_in_machine = serializers.JSONField(write_only=True, required=False)
    
    reported_date = serializers.DateTimeField(format="%Y-%m-%d", required=False)

    action_taken = serializers.CharField(required=False, allow_blank=True)
    parts_required = serializers.CharField(required=False, allow_blank=True)
    parts_used = serializers.CharField(required=False, allow_blank=True)
    start_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M", required=False, allow_null=True)
    finish_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M", required=False, allow_null=True)
    image_urls = serializers.SerializerMethodField(read_only=True)
    images = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        allow_empty=True,
    )
    lease_service_schedule = LeaseServiceScheduleSerializer(read_only=True)
    lease_service_schedule_id = serializers.PrimaryKeyRelatedField(
        source='lease_service_schedule',
        queryset=LeaseServiceSchedule.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    lease = LeaseContractSerializer(read_only=True)
    lease_id = serializers.PrimaryKeyRelatedField(
        source='lease',
        queryset=LeaseContract.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Call
        fields = [
            'id', 'technician', 'technician_ids', 'contract_type', 'service_type',
            'client', 'client_id', 'client_name', 'client_name_display', 
            'client_location', 'client_location_display',
            'reported_by', 'reported_date', 'color_meter_reading', 'mono_meter_reading',
            'item', 'item_id', 'item_name', 'serial_no', 'store_name',
            'fault_reported', 'action_taken', 'meter_reading', 'parts_required', 'parts_used',
            'comments', 'status', 'department', 'is_checked', 'director_comment', 'ticket_no',
            'spare_description', 'created_at', 'walk_in_machine',
            'walk_in_machine_name', 'walk_in_machine_type', 'walk_in_serial_no', 'technician_manager_approval', 'client_verification',
            'finish_time', 'start_time', 'lpo', 'images', 'image_urls', 'lease', 'lease_id',
            'lease_service_schedule', 'lease_service_schedule_id'
        ]
        extra_kwargs = {
            'created_at': {'read_only': True},
            'ticket_no': {'read_only': True},
        }

    def get_image_urls(self, obj):
        return obj.images

    def create(self, validated_data):
        # Handle walk-in machine data
        walk_in_machine = validated_data.pop('walk_in_machine', None)
        technicians = validated_data.pop('technician', [])
        
        # Extract client info for walk-ins
        if validated_data.get('contract_type') == 'WalkIn':
            validated_data['client_name'] = validated_data.get('client_name', '')
            validated_data['client_location'] = validated_data.get('client_location', '')
        
        if walk_in_machine:
            validated_data['walk_in_machine_name'] = walk_in_machine.get('machineName', '')
            validated_data['walk_in_machine_type'] = walk_in_machine.get('machineType', '')
            validated_data['walk_in_serial_no'] = walk_in_machine.get('serialNo', '')
        
        call = Call.objects.create(**validated_data)
        if technicians:
            call.technician.set(technicians)
            call.status = 'Pending'
        else:
            call.status = 'Open'
        
        call.save()
        return call
    
    def update(self, instance, validated_data):
        # Handle walk-in machine data
        walk_in_machine = validated_data.pop('walk_in_machine', None)
        if walk_in_machine:
            validated_data['walk_in_machine_name'] = walk_in_machine.get('machineName', '')
            validated_data['walk_in_machine_type'] = walk_in_machine.get('machineType', '')
            validated_data['walk_in_serial_no'] = walk_in_machine.get('serialNo', '')
        
        # Handle technician IDs
        technicians = validated_data.pop('technician', None)
        if technicians is not None:
            instance.technician.set(technicians)

        old_client_verification = instance.client_verification
        old_technician_approval = instance.technician_manager_approval
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Check if either approval field was updated and auto-complete if both are True
        client_verification_changed = (
            'client_verification' in validated_data and 
            validated_data['client_verification'] != old_client_verification
        )
        technician_approval_changed = (
            'technician_manager_approval' in validated_data and 
            validated_data['technician_manager_approval'] != old_technician_approval
        )
        
        if client_verification_changed or technician_approval_changed:
            # Check if both approvals are now True and update status
            if instance.client_verification and instance.technician_manager_approval:
                instance.status = 'Closed'
        
        instance.save()
        return instance

    def to_internal_value(self, data):
        # Handle ID field mappings for non-walk-in calls
        if data.get('contract_type') != 'WalkIn':
            data['client_id'] = data.get('client_id') or data.get('client', {}).get('id')
            data['item_id'] = data.get('item_id') or data.get('item', {}).get('id')
            data['technician_ids'] = data.get('technician_ids') or [t.get('id') for t in data.get('technician', [])]
        return super().to_internal_value(data)
    
    def to_representation(self, instance):
        data = super().to_representation(instance)

        data['images'] = instance.images if instance.images else []
        
        # For walk-in calls, use the stored walk-in data if client is None
        if instance.contract_type == 'WalkIn' and not instance.client:
            data['client_name'] = instance.client_name or ''
            data['client_location'] = instance.client_location or ''

        # Ensure technician is always a list
        if 'technician' in data and data['technician'] is not None:
            if not isinstance(data['technician'], list):
                data['technician'] = [data['technician']]
        else:
            data['technician'] = []
        
        return data
    
    def validate(self, data):
        contract_type = data.get('contract_type')
        
        if contract_type == 'WalkIn':
            # For WalkIn, client and item are not required
            data['client'] = None
            data['item'] = None
            
            # Validate walk-in specific fields
            client_name = data.get('client_name', '').strip()
            
            if not client_name:
                raise serializers.ValidationError("Client name is required for Walk-In calls")
            
            
            return data
            
        # For non-WalkIn calls, require client and item
        if not data.get('client'):
            raise serializers.ValidationError("Client is required for non-Walk-In calls")
        if not data.get('item'):
            raise serializers.ValidationError("Machine selection is required for non-Walk-In calls")
            
        return data
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # For walk-in calls, show the stored client info
        if instance.contract_type == 'WalkIn':
            data.update({
                'client_name': instance.client_name or '',
                'client_location': instance.client_location or '',
                'item_name': instance.walk_in_machine_name or '',
                'serial_no': instance.walk_in_serial_no or ''
            })
            
        return data
    
    def get_client_name_display(self, obj):
        if obj.client:
            return obj.client.client_name
        return obj.client_name or ""
    
    def get_client_location_display(self, obj):
        if obj.client:
            return obj.client.client_location
        return obj.client_location or ""
    
    def get_item_name(self, obj):
        if obj.item:
            return obj.item.machine_name
        return obj.walk_in_machine_name or ""

    def get_serial_no(self, obj):
        if obj.item:
            return obj.item.serial_no
        return obj.walk_in_serial_no or ""

    def get_store_name(self, obj):
        if obj.item and obj.item.store:
            return obj.item.store.store_name
        return ""
    
    def get_image_urls(self, obj):
        """Return the images list"""
        return obj.images if obj.images else []
    
class StorePartInquirySerializer(serializers.ModelSerializer):
    requested_by = UserSerializer(read_only=True)
    lease_part_inquiries = LeasePartInquirySerializer(many=True, read_only=True)
    lease = LeaseContractSerializer(read_only=True)
    lease_id = serializers.PrimaryKeyRelatedField(
        queryset=LeaseContract.objects.all(),
        write_only=True,
        source='lease',
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = StorePartInquiry
        fields = [
            'id', 'service_call', 'part_name', 'quantity', 'requested_by', 
            'requested_at', 'unit_price', 'add_vat', 'is_issued', 'issued_by', 
            'status', 'notes', 'lease_part_inquiries', 'lease', 'lease_id'
        ]
        read_only_fields = ['requested_at', 'issued_by', 'status']

    def create(self, validated_data):
        # Auto-populate lease if not provided
        if not validated_data.get('lease'):
            service_call = validated_data.get('service_call')
            if service_call:
                # Check if service call has a lease
                if service_call.lease:
                    validated_data['lease'] = service_call.lease
                # Otherwise, if it's a Lease contract with a machine, find the active lease
                elif service_call.contract_type == 'Lease' and service_call.item:
                    from .models import LeaseContract
                    active_lease = LeaseContract.objects.filter(
                        item=service_call.item,
                        is_active=True
                    ).first()
                    if active_lease:
                        validated_data['lease'] = active_lease
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Handle status update based on is_issued
        is_issued = validated_data.get('is_issued', instance.is_issued)
        
        if is_issued and not instance.is_issued:
            # First time being issued
            validated_data['status'] = 'Issued'
            validated_data['issued_by'] = self.context['request'].user
        elif not is_issued and instance.is_issued:
            # Being un-issued
            validated_data['status'] = 'Pending'
            # Don't clear issued_by to maintain audit trail
        
        return super().update(instance, validated_data)
    
class StoreAccessoryInquirySerializer(serializers.ModelSerializer):
    requested_by = UserSerializer(read_only=True)
    lease_acc_inquiries = LeaseAccInquirySerializer(many=True, read_only=True)
    lease = LeaseContractSerializer(read_only=True)
    lease_id = serializers.PrimaryKeyRelatedField(
        queryset=LeaseContract.objects.all(),
        write_only=True,
        source='lease',
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = StoreAccessoryInquiry  
        fields = [
            'id', 'service_call', 'acc_name', 'quantity', 'requested_by', 
            'requested_at', 'unit_price', 'add_vat', 'is_issued', 'issued_by', 
            'status', 'notes', 'lease_acc_inquiries', 'lease', 'lease_id'  
        ]
        read_only_fields = ['requested_at', 'issued_by', 'status']

    def update(self, instance, validated_data):
        # Handle status update based on is_issued
        is_issued = validated_data.get('is_issued', instance.is_issued)
        
        if is_issued and not instance.is_issued:
            # First time being issued
            validated_data['status'] = 'Issued'
            validated_data['issued_by'] = self.context['request'].user
        elif not is_issued and instance.is_issued:
            # Being un-issued
            validated_data['status'] = 'Pending'
            # Don't clear issued_by to maintain audit trail
        
        return super().update(instance, validated_data)
    
class ClientMachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientMachine
        fields = '__all__'

class SaleItemSerializer(serializers.ModelSerializer):
    machine = MachineSerializer(read_only=True)
    part = PartSerializer(read_only=True)
    accessory = AccessorySerializer(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    vat_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    custom_item = serializers.JSONField(required=False, allow_null=True)
    
    machine_id = serializers.PrimaryKeyRelatedField(
        queryset=Machine.objects.all(),
        write_only=True,
        required=False,
        source='machine'
    )
    part_id = serializers.PrimaryKeyRelatedField(
        queryset=Part.objects.all(),
        write_only=True,
        required=False,
        source='part'
    )
    accessory_id = serializers.PrimaryKeyRelatedField(
        queryset=Accessory.objects.all(),
        write_only=True,
        required=False,
        source='accessory'
    )

    class Meta:
        model = SaleItem
        fields = [
            'id', 'sale_type', 'machine', 'part', 'accessory', 
            'machine_id', 'part_id', 'accessory_id',
            'quantity', 'unit_price', 'subtotal', 'vat_amount', 'total_price', 
            'custom_item'
        ]
        read_only_fields = ['subtotal', 'vat_amount', 'total_price']

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

class PaymentSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'sale', 'payment_date', 'amount', 'payment_method', 
            'reference_number', 'notes', 'created_at', 'created_by'
        ]
        read_only_fields = ['created_at']
    
    def get_created_by(self, obj):
        """Return created_by user details"""
        if obj.created_by:
            return {
                'firstname': obj.created_by.firstname,
                'lastname': obj.created_by.lastname
            }
        return None

class SaleSerializer(serializers.ModelSerializer):
    sale_type = serializers.ChoiceField(choices=Sale.SALE_TYPE_CHOICES)
    client_name = serializers.CharField(write_only=True, required=False)
    client_location = serializers.CharField(write_only=True, required=False)
    items = SaleItemSerializer(many=True, required=True)
    payments = PaymentSerializer(many=True, read_only=True)
    
    # Read-only calculated fields
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    vat_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment_status = serializers.CharField(read_only=True)
    is_overdue = serializers.ReadOnlyField()
    
    items_count = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()
    payments_count = serializers.SerializerMethodField()
    
    # Payment fields for creation/update - UPDATED
    initial_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, write_only=True)
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES, required=False, write_only=True)
    payment_reference = serializers.CharField(
        max_length=100, 
        required=False, 
        allow_blank=True,  # ADDED: Allow blank values
        write_only=True
    )
    
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(),
        write_only=True,
        required=False,
        source='client'  
    )

    store_part_inquiry_id = serializers.PrimaryKeyRelatedField(
        queryset=StorePartInquiry.objects.all(),
        write_only=True,
        required=False,
        source='store_part_inquiry'
    )
    
    store_acc_inquiry_id = serializers.PrimaryKeyRelatedField(
        queryset=StoreAccessoryInquiry.objects.all(),
        write_only=True,
        required=False,
        source='store_acc_inquiry'
    )
    
    class Meta:
        model = Sale
        fields = [
            'id', 'sale_no', 'client', 'client_id', 'items', 'add_vat', 'vat_rate',
            'client_name', 'client_location', 'sale_date', 'notes', 'created_at',
            'subtotal', 'vat_total', 'total_amount', 'items_count', 'sale_type', 'lpo',
            'store_part_inquiry_id', 'store_acc_inquiry_id', 'payments', 'payments_count',
            'payment_status', 'amount_paid', 'remaining_balance', 'due_date', 
            'payment_notes', 'is_overdue', 'initial_payment', 'payment_method', 'payment_reference'
        ]
        read_only_fields = [
            'sale_no', 'created_at', 'subtotal', 'vat_total', 'total_amount',
            'amount_paid', 'remaining_balance', 'payment_status'
        ]

    def get_client(self, obj):
        if obj.client:
            return {
                'id': str(obj.client.id),
                'client_name': obj.client.client_name,
                'client_location': obj.client.client_location
            }
        elif obj.local_client_name:
            return {
                'client_name': obj.local_client_name,
                'client_location': getattr(obj, 'local_client_location', '')
            }
        return None
    
    def get_items_count(self, obj):
        return obj.items.count()
    
    def get_payments_count(self, obj):
        return obj.payments.count()

    def validate(self, data):
        sale_type = data.get('sale_type')
        client = data.get('client')  
        client_name = data.get('client_name')
        client_location = data.get('client_location')
        items = data.get('items', [])
        initial_payment = data.get('initial_payment')
        due_date = data.get('due_date')
        payment_method = data.get('payment_method')
        payment_reference = data.get('payment_reference', '').strip()

        # For Internal Sales: Require existing client
        if sale_type == 'Internal':
            if not client:
                raise serializers.ValidationError({
                    "client_id": "Client selection is required for internal sales."
                })

        # For Local Sales: Require client_name
        elif sale_type == 'Local':
            if not client and (not client_name or not client_location):
                raise serializers.ValidationError({
                    "client": "Either select existing client or provide new client details",
                    "client_name": "Required if no client selected",
                    "client_location": "Required if no client selected"
                })

        # Validate initial payment
        if initial_payment is not None and initial_payment < 0:
            raise serializers.ValidationError({
                "initial_payment": "Initial payment cannot be negative"
            })

        # ADDED: Validate payment reference for non-cash methods (optional but recommended)
        # Remove this block if you don't want any validation for payment_reference
        if initial_payment and initial_payment > 0:
            if payment_method and payment_method not in ['Cash', 'Credit'] and not payment_reference:
                # Optional warning - you can remove this if reference should be completely optional
                pass  # Just a placeholder - reference is optional

        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        sale_type = validated_data.get('sale_type')
        client = validated_data.get('client')
        
        # Extract payment data
        initial_payment = validated_data.pop('initial_payment', None)
        payment_method = validated_data.pop('payment_method', 'Cash')
        payment_reference = validated_data.pop('payment_reference', '')

        # Handle client based on sale type
        if sale_type == 'Internal':
            if not client:
                raise serializers.ValidationError({"client_id": "Client selection is required for internal sales."})
            
        elif sale_type == 'Local' and not client:
            client_name = validated_data.pop('client_name')
            client_location = validated_data.pop('client_location', '')

            client, _ = Client.objects.get_or_create(
                client_name=client_name,
                client_location=client_location,
                defaults={'client_name': client_name, 'client_location': client_location}
            )
            validated_data['client'] = client

        # Create the sale
        sale = Sale.objects.create(**validated_data)

        # Add sale items
        for item_data in items_data:
            custom_data = {}
            if item_data.get('custom_item'):
                custom_data = {
                    'name': item_data['custom_item']['name'],
                    'type': item_data['sale_type'],
                    'reference_no': item_data['custom_item'].get('reference_no', '')
                }
            
            item_create_data = {
                'sale': sale,
                'sale_type': item_data['sale_type'],
                'quantity': item_data['quantity'],
                'unit_price': item_data['unit_price'],
                'custom_item': custom_data if custom_data else None,
            }
            
            if item_data.get('machine'):
                item_create_data['machine'] = item_data['machine']
            elif item_data.get('part'):
                item_create_data['part'] = item_data['part']
            elif item_data.get('accessory'):
                item_create_data['accessory'] = item_data['accessory']
            
            SaleItem.objects.create(**item_create_data)
        
        # Calculate totals
        sale.calculate_totals()
        sale.save()
        
        # Create initial payment if provided
        if initial_payment is not None and initial_payment > 0:
            Payment.objects.create(
                sale=sale,
                amount=initial_payment,
                payment_method=payment_method,
                reference_number=payment_reference,  # Can be blank now
                payment_date=sale.sale_date,
                created_by=self.context['request'].user if self.context.get('request') else None
            )
        
        return sale
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        
        # Remove payment fields from update (they should be handled separately)
        validated_data.pop('initial_payment', None)
        validated_data.pop('payment_method', None)
        validated_data.pop('payment_reference', None)
        
        # Update sale fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update items (simplified for brevity - same logic as before)
        existing_items = {item.id: item for item in instance.items.all()}
        
        for item_data in items_data:
            item_id = item_data.get('id')
            if item_id and item_id in existing_items:
                item = existing_items[item_id]
                item.quantity = item_data.get('quantity', item.quantity)
                item.unit_price = item_data.get('unit_price', item.unit_price)
                if 'custom_item' in item_data:
                    item.custom_item = item_data['custom_item']
                item.save()
                del existing_items[item_id]
            else:
                # Create new item
                SaleItem.objects.create(sale=instance, **item_data)
        
        # Delete removed items
        for item in existing_items.values():
            item.delete()

        # Recalculate totals
        instance.calculate_totals()
        instance.save()

        return instance
    
class DeliverySerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    client_location = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    delivery_type = serializers.ChoiceField(choices=Delivery.DELIVERY_TYPE_CHOICES)
    
    class Meta:
        model = Delivery
        fields = '__all__'
        read_only_fields = ['delivery_no', 'created_at', 'updated_at']

    def get_client_name(self, obj):
        return obj.client_name
    
    def get_client_location(self, obj):
        return obj.client_location
    
    def get_total_items(self, obj):
        return obj.total_items
    
    def get_total_amount(self, obj):
        return obj.total_amount
    
    def get_assigned_to_name(self, obj):
        return f"{obj.assigned_to.firstname} {obj.assigned_to.lastname}"

    def validate(self, data):
        if data['delivery_type'] == 'Sale' and not data.get('sale'):
            raise serializers.ValidationError("Sale is required for Sale deliveries")
        if data['delivery_type'] == 'Lease' and not data.get('lease'):
            raise serializers.ValidationError("Lease is required for Lease deliveries")
        return data
    
class ChatMessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    read_by = UserSerializer(many=True, read_only=True)
    is_read = serializers.SerializerMethodField()
    file = serializers.FileField(required=False)
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'chat_group', 'sender', 'message_type', 'content', 
                 'file_url', 'created_at', 'read_by', 'is_read', 'file']
    
    def get_is_read(self, obj):
        """Check if message has been read by the current user"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return obj.read_by.filter(id=request.user.id).exists()
        return False

class ChatGroupSerializer(serializers.ModelSerializer):
    members = UserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = ChatGroup
        fields = ['id', 'name', 'members', 'created_at', 'updated_at', 
                 'last_message', 'unread_count']
    
    def get_last_message(self, obj):
        """Get the most recent message in the group"""
        last_message = ChatMessage.objects.filter(
            chat_group=obj
        ).order_by('-created_at').first()
        
        if last_message:
            return {
                'id': str(last_message.id),
                'content': last_message.content,
                'message_type': last_message.message_type,
                'sender_name': f"{last_message.sender.firstname} {last_message.sender.lastname}",
                'created_at': last_message.created_at.isoformat(),
            }
        return None
    
class LeaseAccInquiryPaymentSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = LeaseAccInquiryPayment
        fields = [
            'id', 'inquiry', 'amount', 'payment_method', 
            'reference_number', 'payment_date', 'notes', 
            'created_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']

class LeaseAccInquirySerializer(serializers.ModelSerializer):
    accessory = BasicAccessorySerializer(read_only=True)
    lease = LeaseContractSerializer(read_only=True)
    accessory_id = serializers.PrimaryKeyRelatedField(queryset=Accessory.objects.all(), write_only=True, source='accessory')
    lease_id = serializers.PrimaryKeyRelatedField(
        queryset=LeaseContract.objects.all(),
        write_only=True,
        source='lease'
    )
    store_acc_inquiry_id = serializers.PrimaryKeyRelatedField(
        queryset=StoreAccessoryInquiry.objects.all(),
        write_only=True,
        source='store_acc_inquiry',
        required=False,
    )
    payments = LeaseAccInquiryPaymentSerializer(many=True, read_only=True)
    payments_count = serializers.SerializerMethodField()

    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    vat_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = LeaseAccInquiry
        fields = [
            'id', 'lease', 'accessory', 'quantity', 'unit_amount', 'subtotal',
            'vat_rate', 'vat_amount', 'total_amount', 'apply_vat', 'date', 
            'is_paid', 'created_at', 'updated_at', 'accessory_id', 'lease_id', 
            'store_acc_inquiry_id', 'payment_type', 'initial_payment',
            'amount_paid', 'remaining_balance', 'payment_status', 
            'due_date', 'payment_notes', 'payments', 'payments_count'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'subtotal', 'vat_amount', 
            'total_amount', 'amount_paid', 'remaining_balance', 'payment_status'
        ]
    
    def get_payments_count(self, obj):
        return obj.payments.count()

class QuotationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationItem
        fields = '__all__'
        read_only_fields = ['quotation']

class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True)
    created_by = UserSerializer(read_only=True)
    client = ClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(),
        write_only=True,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Quotation
        fields = [
            'id', 'quotation_no', 'client', 'client_id', 'client_name', 'client_location',
            'created_by', 'created_at', 'updated_at', 'valid_until', 'subtotal',
            'vat_rate', 'vat_amount', 'total_amount', 'include_vat', 'status', 'notes', 'items'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'quotation_no']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        validated_data['created_by'] = self.context['request'].user
        client = validated_data.pop('client_id', None)
        if client:
            validated_data['client'] = client
        quotation = Quotation.objects.create(**validated_data)
        
        for item_data in items_data:
            QuotationItem.objects.create(quotation=quotation, **item_data)
        
        return quotation

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        instance = super().update(instance, validated_data)
        
        # Update items
        current_items = list(instance.items.all())
        updated_items = []
        
        for item_data in items_data:
            item_id = item_data.get('id', None)
            if item_id:
                # Update existing item
                item = next((i for i in current_items if str(i.id) == item_id), None)
                if item:
                    for attr, value in item_data.items():
                        setattr(item, attr, value)
                    item.save()
                    updated_items.append(item.id)
                else:
                    # ID provided but not found - create new
                    QuotationItem.objects.create(quotation=instance, **item_data)
            else:
                # New item
                QuotationItem.objects.create(quotation=instance, **item_data)
        
        # Delete items not in the update
        for item in current_items:
            if item.id not in updated_items:
                item.delete()
        
        return instance
    
class TransferItemSerializer(serializers.ModelSerializer):
    # For write operations
    machine = serializers.PrimaryKeyRelatedField(
        queryset=Machine.objects.filter(machine_status='Available'), 
        required=False,
        allow_null=True,
        write_only=True
    )
    part = serializers.PrimaryKeyRelatedField(
        queryset=Part.objects.filter(part_status='Available'), 
        required=False,
        allow_null=True,
        write_only=True
    )
    accessory = serializers.PrimaryKeyRelatedField(
        queryset=Accessory.objects.filter(acc_status='Available'), 
        required=False,
        allow_null=True,
        write_only=True
    )

    machine_details = MachineSerializer(source='machine', read_only=True)
    part_details = PartSerializer(source='part', read_only=True)
    accessory_details = AccessorySerializer(source='accessory', read_only=True)
    
    class Meta:
        model = TransferItem
        fields = ['id', 'item_type', 'machine', 'part', 'accessory', 
                  'machine_details', 'part_details', 'accessory_details',
                 'quantity', 'initial_quantity']
        read_only_fields = ['initial_quantity']

    def validate(self, data):
        item_type = data.get('item_type')
        quantity = data.get('quantity', 1)
        
        if item_type == 'Part' and data.get('part'):
            if quantity > data['part'].quantity:
                raise serializers.ValidationError(
                    f"Quantity exceeds available stock ({data['part'].quantity})"
                )
        
        if item_type == 'Accessory' and data.get('accessory'):
            if quantity > data['accessory'].quantity:
                raise serializers.ValidationError(
                    f"Quantity exceeds available stock ({data['accessory'].quantity})"
                )
        
        return data

class TransferSerializer(serializers.ModelSerializer):
    items = TransferItemSerializer(many=True)
    from_store = StoreSerializer(read_only=True)
    to_store = StoreSerializer(read_only=True)
    from_store_id = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(), 
        source='from_store',
        write_only=True
    )
    to_store_id = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(), 
        source='to_store',
        write_only=True
    )
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Transfer
        fields = [
            'id', 'from_store', 'to_store', 'from_store_id', 'to_store_id',
            'created_by', 'created_at', 'updated_at', 'status', 'notes', 'items'
        ]
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        transfer = Transfer.objects.create(**validated_data)
        
        for item_data in items_data:
            item_type = item_data['item_type']
            initial_quantity = 0
            
            if item_type == 'Machine':
                machine = item_data['machine']
                initial_quantity = machine.quantity
                item_data['machine'] = machine
            elif item_type == 'Part':
                part = item_data['part']
                initial_quantity = part.quantity
                item_data['part'] = part
            elif item_type == 'Accessory':
                accessory = item_data['accessory']
                initial_quantity = accessory.quantity
                item_data['accessory'] = accessory
            
            item_data['initial_quantity'] = initial_quantity
            TransferItem.objects.create(transfer=transfer, **item_data)
        
        return transfer
    
    def update(self, instance, validated_data):
        # Prevent updates to completed transfers
        if instance.status == 'Completed':
            raise serializers.ValidationError("Cannot modify completed transfers")
        
        # Update transfer fields
        instance.from_store = validated_data.get('from_store', instance.from_store)
        instance.to_store = validated_data.get('to_store', instance.to_store)
        instance.notes = validated_data.get('notes', instance.notes)
        instance.save()
        
        # Update items (if provided)
        items_data = validated_data.get('items', [])
        if items_data:
            # Clear existing items and create new ones
            instance.items.all().delete()
            for item_data in items_data:
                TransferItem.objects.create(transfer=instance, **item_data)
        
        return instance
    
class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'
        read_only_fields = ['purchase_order']

class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True)
    created_by = UserSerializer(read_only=True)
    verified_by_sales_manager = UserSerializer(read_only=True)
    verified_by_director = UserSerializer(read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'po_number', 'supplier', 'supplier_address',
            'created_by', 'created_at', 'updated_at', 'required_by_date', 'subtotal',
            'vat_rate', 'vat_amount', 'total_amount', 'include_vat', 'status', 'notes',
            'items', 'verified_by_sales_manager', 'verified_by_director', 'uploaded_pdf'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'po_number', 
                           'verified_by_sales_manager', 'verified_by_director', 'status']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        validated_data['created_by'] = self.context['request'].user
        purchase_order = PurchaseOrder.objects.create(**validated_data)
        
        for item_data in items_data:
            PurchaseOrderItem.objects.create(purchase_order=purchase_order, **item_data)
        
        return purchase_order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        instance = super().update(instance, validated_data)
        
        # Update items
        current_items = list(instance.items.all())
        updated_items = []
        
        for item_data in items_data:
            item_id = item_data.get('id', None)
            if item_id:
                # Update existing item
                item = next((i for i in current_items if str(i.id) == item_id), None)
                if item:
                    for attr, value in item_data.items():
                        setattr(item, attr, value)
                    item.save()
                    updated_items.append(item.id)
                else:
                    # ID provided but not found - create new
                    PurchaseOrderItem.objects.create(purchase_order=instance, **item_data)
            else:
                # New item
                PurchaseOrderItem.objects.create(purchase_order=instance, **item_data)
        
        # Delete items not in the update
        for item in current_items:
            if item.id not in updated_items:
                item.delete()
        
        return instance
