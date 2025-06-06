from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Accessory, AccessoryType, ChatGroup, ChatMessage, Client, ClientMachine, CustomUser, Delivery, LeaseAccInquiry, LeaseContract, LeasePartInquiry, MachineType, Machine, MeterReading, PartType, Part, Sale, SaleItem, Store, Call, StoreInquiry
from django.db.models import Sum
from dateutil.relativedelta import relativedelta
from django.utils import timezone

class UserSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    profile_image = serializers.ImageField(
        required=False, 
        allow_null=True,
        allow_empty_file=True  
    )
    phonenumber = serializers.IntegerField(
        required=False, 
        allow_null=True,
        min_value=100000000,  
        max_value=999999999999999  
    )

    def update(self, instance, validated_data):
        # Handle profile image separately
        profile_image = validated_data.pop('profile_image', None)
        if profile_image:
            # Delete old image if exists
            if instance.profile_image:
                instance.profile_image.delete(save=False)
            instance.profile_image = profile_image
        
        return super().update(instance, validated_data)
    
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'email',
            'firstname',
            'lastname',
            'phonenumber',
            'role',
            'active',
            'profile_image'
        ]
        extra_kwargs = {'password': {'write_only': True}, 'role': {'read_only': True}}
        
class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'firstname', 'lastname', 'phonenumber', 'role']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        validated_data['active'] = validated_data['role'] in ['Director', 'Super Admin']
        user = CustomUser.objects.create_user(**validated_data)
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['email'] = self.user.email
        data['role'] = self.user.role
        data['active'] = self.user.active
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = user.role
        return token

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
    
class AccessoryTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessoryType
        fields = ['id', 'name', 'type', 'brand', 'color']

class MachineTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineType
        fields = ['id', 'name', 'type', 'brand', 'color']

class PartTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartType
        fields = ['id', 'name', 'type', 'brand', 'color']

class MachineSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.store_name', read_only=True)
    store_id = serializers.UUIDField(source='store.id', read_only=True)
    store = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        write_only=True,
        required=True
    )
    
    class Meta:
        model = Machine
        fields = [
            'id',
            'machine_name',
            'machine_brand',
            'machine_type',
            'serial_no',
            'unit_value',
            'quantity',
            'description',
            'created_at',
            'machine_condition',
            'color_type',
            'store',  # Now included in fields list
            'store_id',
            'store_name',
            'supplier_name',
            'machine_status',
            'is_transfer'
        ]
        extra_kwargs = {
            'created_at': {'read_only': True}
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

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'client_name', 'client_location', 'created_at']
        read_only_fields = ['created_at']
    
class BasicPartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Part
        fields = ['id', 'part_name', 'ref_no']  

class BasicAccessorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Accessory
        fields = ['id', 'acc_name', 'ref_no']  

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
        write_only=True
    )
    
    item_id = serializers.PrimaryKeyRelatedField(
        source='item',
        queryset=Machine.objects.all(),
        write_only=True
    )
    client = ClientSerializer(read_only=True)
    meter_readings = MeterReadingSerializer(many=True, read_only=True)
    missing_readings = serializers.SerializerMethodField()
    
    class Meta:
        model = LeaseContract
        fields = [
            'id', 'client', 'client_name', 'client_location', 'department', 
            'item', 'item_id', 'item_name', 'client_id',
            'serial_no', 'store', 'store_name', 'from_date', 'to_date', 'add_vat', 'add_myq',
            'billed_myq', 'is_active', 'contract_type', 'lease_no', 'created_at', 'client', 'meter_readings', 'missing_readings'
        ]
        extra_kwargs = {
            'created_at': {'read_only': True},
            'lease_no': {'read_only': True}
        }

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

class LeasePartInquirySerializer(serializers.ModelSerializer):
    part = BasicPartSerializer(read_only=True)
    lease = LeaseContractSerializer(read_only=True)
    part_id = serializers.PrimaryKeyRelatedField(queryset=Part.objects.all(), write_only=True, source='part')
    lease_id = serializers.PrimaryKeyRelatedField(  # Add this
        queryset=LeaseContract.objects.all(),
        write_only=True,
        source='lease'
    )
    store_inquiry_id = serializers.PrimaryKeyRelatedField(
        queryset=StoreInquiry.objects.all(),
        write_only=True,
        source='store_inquiry',
        required=True
    )
    
    class Meta:
        model = LeasePartInquiry
        fields = [
            'id', 'lease', 'part', 'quantity', 'amount', 
            'vat', 'date', 'is_paid', 'created_at', 'updated_at',
            'part_id', 'lease_id', 'store_inquiry_id'
        ]
        read_only_fields = ['created_at', 'updated_at', 'store_inquiry']

class PartSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.store_name', read_only=True)
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
    
    class Meta:
        model = Part
        fields = [
            'id',
            'part_name',
            'part_brand',
            'part_type',
            'ref_no',
            'unit_value',
            'intial_quantity',
            'quantity',
            'description',
            'created_at',
            'part_condition',
            'color_type',
            'store',
            'store_id',
            'store_name',
            'supplier_name',
            'part_status',
            'is_transfer',
            'leased_quantity', 
            'sold_quantity',
            'lease_inquiries', 
            'sold_items'
        ]
        extra_kwargs = {
            'store': {'write_only': True},
            'created_at': {'read_only': True}
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
        
class LeaseAccInquirySerializer(serializers.ModelSerializer):
    accessory = BasicAccessorySerializer(read_only=True)
    lease = LeaseContractSerializer(read_only=True)
    accessory_id = serializers.PrimaryKeyRelatedField(queryset=Accessory.objects.all(), write_only=True, source='accessory')
    
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
            'description',
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
            'sold_items'
        ]
        extra_kwargs = {
            'store': {'write_only': True},
            'created_at': {'read_only': True}
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
    # Flattened fields for reading
    client_name_display = serializers.CharField(source='client.client_name', read_only=True)
    client_location_display = serializers.CharField(source='client.client_location', read_only=True)
    item_name = serializers.CharField(source='item.machine_name', read_only=True)
    serial_no = serializers.CharField(source='item.serial_no', read_only=True)
    store_name = serializers.CharField(source='item.store.store_name', read_only=True)
    
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
    
    class Meta:
        model = Call
        fields = [
            'id', 'technician', 'technician_ids', 'contract_type', 
            'client', 'client_id', 'client_name', 'client_name_display', 
            'client_location', 'client_location_display',
            'reported_by', 'reported_date', 
            'item', 'item_id', 'item_name', 'serial_no', 'store_name',
            'fault_reported', 'action_taken', 'meter_reading', 'parts_required', 'parts_used',
            'comments', 'status', 'department', 'is_checked', 'director_comment', 'ticket_no',
            'spare_description', 'created_at', 'walk_in_machine',
            'walk_in_machine_name', 'walk_in_machine_type', 'walk_in_serial_no', 'technician_manager_approval', 'client_verification'
        ]
        extra_kwargs = {
            'created_at': {'read_only': True},
            'ticket_no': {'read_only': True},
            'client_verification': {'read_only': True}
        }
    
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
        call.technician.set(technicians)
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
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
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
        
        # For walk-in calls, use the stored walk-in data if client is None
        if instance.contract_type == 'WalkIn' and not instance.client:
            data['client_name'] = instance.client_name or ''
            data['client_location'] = instance.client_location or ''
        
        return data
    
    def validate(self, data):
        contract_type = data.get('contract_type')
        
        if contract_type == 'WalkIn':
            # For WalkIn, client and item are not required
            data['client'] = None
            data['item'] = None
            
            # Validate walk-in specific fields
            client_name = data.get('client_name', '').strip()
            client_location = data.get('client_location', '').strip()
            
            if not client_name:
                raise serializers.ValidationError("Client name is required for Walk-In calls")
            if not client_location:
                raise serializers.ValidationError("Client location is required for Walk-In calls")
            
            walk_in_machine = data.get('walk_in_machine')
            if not walk_in_machine:
                raise serializers.ValidationError("Machine details are required for Walk-In calls")
                
            machine_name = walk_in_machine.get('machineName', '').strip()
            serial_no = walk_in_machine.get('serialNo', '').strip()
            
            if not machine_name or not serial_no:
                raise serializers.ValidationError("Machine name and serial number are required for Walk-In calls")
            
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
            data['client_name'] = instance.client_name
            data['client_location'] = instance.client_location
            
        return data
    
class StoreInquirySerializer(serializers.ModelSerializer):
    requested_by = UserSerializer(read_only=True)
    lease_part_inquiries = LeasePartInquirySerializer(many=True, read_only=True)
    
    class Meta:
        model = StoreInquiry
        fields = [
            'id', 'service_call', 'part_name', 'quantity', 'requested_by', 
            'requested_at', 'unit_price', 'add_vat', 'is_issued', 'issued_by', 
            'status', 'notes', 'lease_part_inquiries'
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
    total_price = serializers.SerializerMethodField()
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
            'quantity', 'unit_price', 'total_price', 'custom_item'
        ]
    
    def get_total_price(self, obj):
        return obj.quantity * obj.unit_price

class SaleSerializer(serializers.ModelSerializer):
    sale_type = serializers.ChoiceField(choices=Sale.SALE_TYPE_CHOICES)
    client_name = serializers.CharField(write_only=True, required=False)
    client_location = serializers.CharField(write_only=True, required=False)
    items = SaleItemSerializer(many=True, required=True)
    total_price = serializers.SerializerMethodField() 
    items_count = serializers.SerializerMethodField()
    add_vat = serializers.BooleanField()
    client = ClientSerializer(read_only=True)
    client_id = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(),
        write_only=True,
        required=False,
        source='client'  
    )
    
    class Meta:
        model = Sale
        fields = [
            'id', 'sale_no', 'client', 'client_id', 'items', 'add_vat', 'client_name', 'client_location',
            'sale_date', 'notes', 'created_at', 'total_price', 'items_count', 'sale_type', 'client_id', 
        ]
        read_only_fields = ['sale_no', 'created_at', 'total_price']
        extra_kwargs = {
            'local_client_name': {'required': False}
        }
    
    def validate(self, data):
        sale_type = data.get('sale_type')
        client = data.get('client')  
        client_name = data.get('client_name')
        client_location = data.get('client_location')

        # For Internal Sales: Require existing client (via client_id)
        if sale_type == 'Internal':
            if not client:  # Changed this condition
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

        return data

    def get_total_price(self, obj):
        return sum(item.total_price for item in obj.items.all())
    
    def get_items_count(self, obj):
        return obj.items.count()

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        sale_type = validated_data.get('sale_type')
        client = validated_data.get('client')

        # Handle client based on sale type
        if sale_type == 'Internal':
            if not client:
                raise serializers.ValidationError({"client_id": "Client selection is required for internal sales."})
            
        elif sale_type == 'Local'and not client:
            # Create or get client using name + location
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
            
            SaleItem.objects.create(
                sale=sale,
                sale_type=item_data['sale_type'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                custom_item=custom_data if custom_data else None,
                **({'machine': item_data.get('machine')} if item_data.get('machine') else {}),
                **({'part': item_data.get('part')} if item_data.get('part') else {}),
                **({'accessory': item_data.get('accessory')} if item_data.get('accessory') else {})
            )
        return sale
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', [])
        
        # Update sale fields
        instance.sale_date = validated_data.get('sale_date', instance.sale_date)
        instance.notes = validated_data.get('notes', instance.notes)
        instance.add_vat = validated_data.get('add_vat', instance.add_vat)
        instance.save()

        # Update items
        existing_items = {item.id: item for item in instance.items.all()}
        
        for item_data in items_data:
            item_id = item_data.get('id')
            if item_id and item_id in existing_items:
                # Update existing item
                item = existing_items[item_id]
                item.quantity = item_data.get('quantity', item.quantity)
                item.unit_price = item_data.get('unit_price', item.unit_price)
                item.total_price = item.quantity * item.unit_price
                
                # Update custom item if present
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

class LeaseAccInquirySerializer(serializers.ModelSerializer):
    accessory = AccessorySerializer(read_only=True)
    accessory_id = serializers.PrimaryKeyRelatedField(queryset=Accessory.objects.all(), write_only=True, source='accessory')
    
    class Meta:
        model = LeaseAccInquiry
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

