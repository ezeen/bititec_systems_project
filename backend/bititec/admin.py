from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Accessory, AccessoryType, Call, ChatGroup, ChatMessage, Client, ClientMachine, CustomUser, Delivery, LeaseAccInquiry, LeaseContract, LeasePartInquiry, Machine, MachineType, MeterReading, Part, PartType, ServiceCallToken, Store, Sale, SaleItem, StoreInquiry
from django.utils.html import format_html

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'get_full_name', 'role', 'active', 'is_staff', 'profile_image_tag')
    list_filter = ('role', 'active', 'is_staff')
    search_fields = ('email', 'firstname', 'lastname')
    ordering = ('email',)
    readonly_fields = ('profile_image_tag',)

    def profile_image_tag(self, obj):
        if obj.profile_image:
            return format_html('<img src="{}" width="50" height="50" />', obj.profile_image.url)
        return "No Image"
    profile_image_tag.short_description = 'Profile Image'
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('firstname', 'lastname', 'phonenumber', 'role', 'profile_image', 'profile_image_tag')}),
        ('Permissions', {'fields': ('active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
        
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'firstname', 'lastname', 'phonenumber', 'role', 'password1', 'password2', 'profile_image_display'),
        }),
    )
    
    def get_full_name(self, obj):
        return f"{obj.firstname} {obj.lastname}"
    get_full_name.short_description = 'Full Name'

admin.site.register(CustomUser, CustomUserAdmin)

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('id', 'store_name', 'store_location', 'store_size', 'created_at')
    search_fields = ('store_name', 'store_location')
    list_filter = ('created_at', 'store_size')

@admin.register(AccessoryType)
class AccessoryTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'brand', 'color')
    search_fields = ('name', 'type', 'brand')
    list_filter = ('type', 'brand')

@admin.register(PartType)
class PartTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'brand', 'color')
    search_fields = ('name', 'type', 'brand')
    list_filter = ('type', 'brand')

@admin.register(MachineType)
class MachineTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'brand', 'color')
    search_fields = ('name', 'type', 'brand')
    list_filter = ('type', 'brand')

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('machine_name', 'machine_brand', 'machine_type', 'serial_no', 'store', 'machine_status')
    list_filter = ('machine_type', 'machine_status', 'machine_condition', 'is_transfer')
    search_fields = ('machine_name', 'machine_brand', 'serial_no', 'store__store_name')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('machine_name', 'machine_brand', 'machine_type', 'serial_no')
        }),
        ('Inventory Details', {
            'fields': ('unit_value', 'quantity', 'description', 'machine_condition', 'color_type')
        }),
        ('Location & Status', {
            'fields': ('store', 'supplier_name', 'machine_status', 'is_transfer')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    raw_id_fields = ('store',)

@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('part_name', 'part_brand', 'part_type', 'ref_no', 'store', 'part_status')
    list_filter = ('part_type', 'part_status', 'part_condition', 'is_transfer')
    search_fields = ('part_name', 'part_brand', 'ref_no', 'store__store_name')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('part_name', 'part_brand', 'part_type', 'ref_no')
        }),
        ('Inventory Details', {
            'fields': ('unit_value', 'intial_quantity', 'quantity', 'description', 'part_condition', 'color_type')
        }),
        ('Location & Status', {
            'fields': ('store', 'supplier_name', 'part_status', 'is_transfer')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    raw_id_fields = ('store',)

@admin.register(Accessory)
class AccessoryAdmin(admin.ModelAdmin):
    list_display = ('acc_name', 'acc_brand', 'acc_type', 'ref_no', 'store', 'acc_status')
    list_filter = ('acc_type', 'acc_status', 'acc_condition', 'is_transfer')
    search_fields = ('acc_name', 'acc_brand', 'ref_no', 'store__store_name')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('acc_name', 'acc_brand', 'acc_type', 'ref_no')
        }),
        ('Inventory Details', {
            'fields': ('unit_value', 'intial_quantity', 'quantity', 'description', 'acc_condition', 'color_type')
        }),
        ('Location & Status', {
            'fields': ('store', 'supplier_name', 'acc_status', 'is_transfer')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    raw_id_fields = ('store',)

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'client_location', 'created_at')
    search_fields = ('client_name', 'client_location')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)

@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ('ticket_no', 'client', 'item', 'status', 'reported_date', 'get_technicians')
    list_filter = ('status', 'reported_date', 'department')
    search_fields = ('ticket_no', 'client__client_name', 'item__machine_name')
    filter_horizontal = ('technician',)
    readonly_fields = ('created_at', 'updated_at', 'get_technicians')
    
    def get_technicians(self, obj):
        return ", ".join([f"{t.firstname} {t.lastname}" for t in obj.technician.all()]) if obj.technician.exists() else "No technicians assigned"
    get_technicians.short_description = "Technicians"

@admin.register(LeaseContract)
class LeaseContractAdmin(admin.ModelAdmin):
    list_display = ('lease_no', 'client', 'item', 'contract_type', 'is_active')
    list_filter = ('contract_type', 'is_active', 'store')
    search_fields = ('lease_no', 'client__client_name', 'item__machine_name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sale_no', 'client', 'sale_date',  'created_at')
    list_filter = ('sale_date', 'client')
    search_fields = ('sale_no', 'client__client_name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'sale_date'
    raw_id_fields = ('client',)

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('sale', 'sale_type', 'unit_price', 'quantity', 'total_price')
    list_filter = ('sale_type',)
    search_fields = ('sale__sale_no',)
    raw_id_fields = ('machine', 'part', 'accessory')

@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('delivery_no', 'client_name', 'status', 'assigned_to_display', 'delivery_date')
    list_filter = ('status', 'delivery_date')
    search_fields = ('delivery_no', 'sale__client__client_name', 'delivery_notes')
    readonly_fields = ('delivery_no', 'created_at', 'updated_at')
    
    def client_name(self, obj):
        return obj.sale.client.client_name
    
    def assigned_to_display(self, obj):
        return f"{obj.assigned_to.firstname} {obj.assigned_to.lastname}"
    
    assigned_to_display.short_description = 'Assigned To'

@admin.register(LeasePartInquiry)
class LeasePartInquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'lease', 'part', 'quantity', 'amount', 'vat', 'date', 'is_paid')
    list_filter = ('is_paid', 'date')
    search_fields = ('lease__lease_number', 'part__part_name')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LeaseAccInquiry)
class LeaseAccInquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'lease', 'accessory', 'quantity', 'amount', 'vat', 'date', 'is_paid')
    list_filter = ('is_paid', 'date')
    search_fields = ('lease__lease_number', 'accessory__name')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ClientMachine)
class ClientMachineAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'client_location', 'machine_name', 'serial_no', 'created_at')
    search_fields = ('client_name', 'machine_name', 'serial_no')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)

@admin.register(StoreInquiry)
class StoreInquiryAdmin(admin.ModelAdmin):
    list_display = ('part_name', 'quantity', 'status', 'requested_by', 'requested_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('part_name', 'service_call__ticket_no')
    raw_id_fields = ('service_call', 'requested_by', 'issued_by')
    readonly_fields = ('requested_at',)

@admin.register(ServiceCallToken)
class ServiceCallTokenAdmin(admin.ModelAdmin):
    list_display = ('service_call', 'email', 'expires_at', 'is_used', 'is_valid')
    list_filter = ('is_used', 'expires_at')
    search_fields = ('email', 'service_call__ticket_no')
    readonly_fields = ('created_at', 'is_valid')
    raw_id_fields = ('service_call',)

    def is_valid(self, obj):
        return obj.is_valid()
    is_valid.boolean = True

@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'member_count')
    search_fields = ('name',)
    filter_horizontal = ('members',)
    readonly_fields = ('created_at', 'updated_at')

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'chat_group', 'message_type', 'content_preview', 'created_at')
    list_filter = ('message_type', 'created_at')
    search_fields = ('content', 'sender__email')
    raw_id_fields = ('chat_group', 'sender')
    readonly_fields = ('created_at', 'file_url')

    def content_preview(self, obj):
        return f"{obj.content[:50]}..." if obj.content else None
    content_preview.short_description = 'Content'

@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    list_display = ('lease', 'machine', 'month', 'meter_reading', 'created_at')
    list_filter = ('month', 'created_at')
    search_fields = ('lease__lease_no', 'machine__machine_name')
    raw_id_fields = ('lease', 'machine')
    readonly_fields = ('created_at', 'updated_at')