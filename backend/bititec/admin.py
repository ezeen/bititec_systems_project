from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Accessory, AccessoryType, Call, ChatGroup, ChatMessage, Client, ClientMachine, 
    CustomUser, Delivery, KeyAudit, LeaseAccInquiry, LeaseAccInquiryPayment, 
    LeaseContract, LeasePartInquiry, LeasePartInquiryPayment, LoginAttempt, 
    Machine, MachineType, MeterReading, MyQPayment, Part, PartType, Payment, 
    Quotation, QuotationItem, Sale, SaleItem, SecurityEvent, ServiceCallToken, 
    Store, StoreAccessoryInquiry, StorePartInquiry, LeasePayment, LeaseMachineSwap,
    LeaseServiceSchedule, Transfer, TransferItem, PurchaseOrder, PurchaseOrderItem
)
from django.utils.html import format_html

# ============================================================================
# USER MANAGEMENT
# ============================================================================

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'get_full_name', 'role', 'active', 'is_staff', 'profile_image_tag', 'failed_login_attempts', 'is_locked_display', 'stores_display')
    list_filter = ('role', 'active', 'is_staff', 'failed_login_attempts', 'stores')
    search_fields = ('email', 'firstname', 'lastname')
    ordering = ('email',)
    readonly_fields = ('profile_image_tag', 'is_locked_display', 'keys_granted_at', 'last_failed_login', 'stores_display')
    filter_horizontal = ('stores',)

    def profile_image_tag(self, obj):
        if obj.profile_image:
            return format_html('<img src="{}" width="50" height="50" />', obj.profile_image.url)
        return "No Image"
    profile_image_tag.short_description = 'Profile Image'
    
    def is_locked_display(self, obj):
        return obj.is_locked() if hasattr(obj, 'is_locked') else 'Unknown'
    is_locked_display.short_description = 'Account Locked'
    is_locked_display.boolean = True
    
    def stores_display(self, obj):
        stores = obj.stores.all()
        if stores:
            return ", ".join([f"{store.store_name} ({store.store_location})" for store in stores])
        return "No stores assigned"
    stores_display.short_description = 'Assigned Stores'
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('firstname', 'lastname', 'phonenumber', 'role', 'profile_image', 'profile_image_tag')}),
        ('Store Assignments', {'fields': ('stores', 'stores_display')}),
        ('Permissions', {'fields': ('active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Security Settings', {
            'fields': ('failed_login_attempts', 'locked_until', 'last_failed_login', 'security_token', 'is_locked_display'),
            'classes': ('collapse',)
        }),
        ('Key-based Permissions', {
            'fields': ('keys', 'keys_granted_by', 'keys_granted_at', 'keys_reason'),
            'classes': ('collapse',),
            'description': 'Additional permissions granted via key system'
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'firstname', 'lastname', 'phonenumber', 'role', 'password1', 'password2', 'profile_image', 'active', 'stores'),
        }),
    )
    
    def get_full_name(self, obj):
        return f"{obj.firstname} {obj.lastname}"
    get_full_name.short_description = 'Full Name'

admin.site.register(CustomUser, CustomUserAdmin)

# ============================================================================
# SECURITY & AUDIT
# ============================================================================

@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'email', 'success', 'timestamp', 'user_agent_preview')
    list_filter = ('success', 'timestamp')
    search_fields = ('ip_address', 'email')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'
    
    def user_agent_preview(self, obj):
        return obj.user_agent[:50] + '...' if len(obj.user_agent) > 50 else obj.user_agent
    user_agent_preview.short_description = 'User Agent'

@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'ip_address', 'timestamp')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('user__email', 'ip_address', 'event_type')
    readonly_fields = ('timestamp', 'details')
    date_hierarchy = 'timestamp'

@admin.register(KeyAudit)
class KeyAuditAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'action_type', 'granted_by', 'timestamp')
    list_filter = ('action_type', 'key', 'timestamp')
    search_fields = ('user__email', 'key', 'granted_by__email')
    readonly_fields = ('timestamp',)
    raw_id_fields = ('user', 'granted_by')
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Audit Information', {
            'fields': ('user', 'key', 'actions', 'action_type', 'granted_by', 'reason')
        }),
        ('Metadata', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )

# ============================================================================
# STORE MANAGEMENT
# ============================================================================

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('id', 'store_name', 'store_location', 'store_size', 'machines_count', 'parts_count', 'accessories_count', 'created_at')
    search_fields = ('store_name', 'store_location')
    list_filter = ('created_at', 'store_size')
    readonly_fields = ('created_at', 'updated_at', 'machines_count', 'parts_count', 'accessories_count')
    
    fieldsets = (
        ('Store Information', {
            'fields': ('store_name', 'store_location', 'store_size')
        }),
        ('Statistics', {
            'fields': ('machines_count', 'parts_count', 'accessories_count'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# ============================================================================
# INVENTORY TYPE DEFINITIONS
# ============================================================================

@admin.register(MachineType)
class MachineTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'brand', 'color', 'image_preview', 'created_at')
    search_fields = ('name', 'type', 'brand')
    list_filter = ('type', 'brand', 'created_at')
    readonly_fields = ('created_at', 'updated_at', 'image_preview')
    
    def image_preview(self, obj):
        if obj.image1:
            return format_html('<img src="{}" width="100" height="100" />', obj.image1.url)
        return "No Image"
    image_preview.short_description = 'Image Preview'

@admin.register(PartType)
class PartTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'brand', 'color', 'image_preview', 'created_at')
    search_fields = ('name', 'type', 'brand')
    list_filter = ('type', 'brand', 'created_at')
    readonly_fields = ('created_at', 'updated_at', 'image_preview')
    
    def image_preview(self, obj):
        if obj.image1:
            return format_html('<img src="{}" width="100" height="100" />', obj.image1.url)
        return "No Image"
    image_preview.short_description = 'Image Preview'

@admin.register(AccessoryType)
class AccessoryTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'brand', 'color', 'image_preview', 'created_at')
    search_fields = ('name', 'type', 'brand')
    list_filter = ('type', 'brand', 'created_at')
    readonly_fields = ('created_at', 'updated_at', 'image_preview')
    
    def image_preview(self, obj):
        if obj.image1:
            return format_html('<img src="{}" width="100" height="100" />', obj.image1.url)
        return "No Image"
    image_preview.short_description = 'Image Preview'

# ============================================================================
# INVENTORY MANAGEMENT
# ============================================================================

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('machine_name', 'machine_brand', 'machine_type', 'serial_no', 'store', 'machine_status', 'quantity', 'unit_value', 'is_transfer')
    list_filter = ('machine_type', 'machine_status', 'machine_condition', 'is_transfer', 'store')
    search_fields = ('machine_name', 'machine_brand', 'serial_no', 'store__store_name')
    readonly_fields = ('created_at',)
    raw_id_fields = ('store', 'source_transfer')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('machine_name', 'machine_brand', 'machine_type', 'serial_no')
        }),
        ('Inventory Details', {
            'fields': ('unit_value', 'quantity', 'condition_description', 'machine_condition', 'color_type')
        }),
        ('Location & Status', {
            'fields': ('store', 'supplier_name', 'machine_status', 'is_transfer', 'source_transfer')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ('part_name', 'part_brand', 'part_type', 'ref_no', 'store', 'part_status', 'quantity', 'intial_quantity', 'unit_value', 'is_transfer')
    list_filter = ('part_type', 'part_status', 'part_condition', 'is_transfer', 'store')
    search_fields = ('part_name', 'part_brand', 'ref_no', 'store__store_name')
    readonly_fields = ('created_at', 'transferred_quantity', 'received_quantity')
    raw_id_fields = ('store', 'source_transfer', 'origin_machine', 'current_machine')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('part_name', 'part_brand', 'part_type', 'ref_no')
        }),
        ('Inventory Details', {
            'fields': ('unit_value', 'intial_quantity', 'quantity', 'condition_description', 'part_condition', 'color_type')
        }),
        ('Location & Status', {
            'fields': ('store', 'supplier_name', 'part_status', 'is_transfer', 'source_transfer')
        }),
        ('Machine Tracking', {
            'fields': ('origin_machine', 'current_machine', 'removed_date', 'installed_date'),
            'classes': ('collapse',)
        }),
        ('Transfer Information', {
            'fields': ('transferred_quantity', 'received_quantity'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Accessory)
class AccessoryAdmin(admin.ModelAdmin):
    list_display = ('acc_name', 'acc_brand', 'acc_type', 'ref_no', 'store', 'acc_status', 'quantity', 'intial_quantity', 'unit_value', 'is_transfer')
    list_filter = ('acc_type', 'acc_status', 'acc_condition', 'is_transfer', 'store')
    search_fields = ('acc_name', 'acc_brand', 'ref_no', 'store__store_name')
    readonly_fields = ('created_at', 'transferred_quantity', 'received_quantity')
    raw_id_fields = ('store', 'source_transfer')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('acc_name', 'acc_brand', 'acc_type', 'ref_no')
        }),
        ('Inventory Details', {
            'fields': ('unit_value', 'intial_quantity', 'quantity', 'condition_description', 'acc_condition', 'color_type')
        }),
        ('Location & Status', {
            'fields': ('store', 'supplier_name', 'acc_status', 'is_transfer', 'source_transfer')
        }),
        ('Transfer Information', {
            'fields': ('transferred_quantity', 'received_quantity'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

# ============================================================================
# TRANSFER MANAGEMENT
# ============================================================================

class TransferItemInline(admin.TabularInline):
    model = TransferItem
    extra = 1
    fields = ('item_type', 'machine', 'part', 'accessory', 'quantity', 'initial_quantity')
    raw_id_fields = ('machine', 'part', 'accessory')

@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('id', 'from_store', 'to_store', 'status', 'created_by', 'created_at', 'items_count')
    list_filter = ('status', 'created_at', 'from_store', 'to_store')
    search_fields = ('from_store__store_name', 'to_store__store_name', 'created_by__email')
    readonly_fields = ('created_at', 'updated_at', 'items_count')
    raw_id_fields = ('from_store', 'to_store', 'created_by')
    inlines = [TransferItemInline]
    date_hierarchy = 'created_at'
    
    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = 'Number of Items'
    
    fieldsets = (
        ('Transfer Information', {
            'fields': ('from_store', 'to_store', 'status', 'created_by')
        }),
        ('Details', {
            'fields': ('notes', 'items_count')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(TransferItem)
class TransferItemAdmin(admin.ModelAdmin):
    list_display = ('transfer', 'item_type', 'get_item_name', 'quantity', 'initial_quantity')
    list_filter = ('item_type', 'transfer__status')
    search_fields = ('transfer__id', 'machine__machine_name', 'part__part_name', 'accessory__acc_name')
    raw_id_fields = ('transfer', 'machine', 'part', 'accessory')
    
    def get_item_name(self, obj):
        if obj.machine:
            return obj.machine.machine_name
        elif obj.part:
            return obj.part.part_name
        elif obj.accessory:
            return obj.accessory.acc_name
        return 'Unknown'
    get_item_name.short_description = 'Item Name'

# ============================================================================
# CLIENT MANAGEMENT
# ============================================================================

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'client_location', 'created_at')
    search_fields = ('client_name', 'client_location')
    list_filter = ('created_at',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ClientMachine)
class ClientMachineAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'client_location', 'machine_name', 'machine_brand', 'serial_no', 'machine_type', 'created_at')
    search_fields = ('client_name', 'machine_name', 'serial_no')
    list_filter = ('created_at', 'machine_type')
    readonly_fields = ('created_at',)

# ============================================================================
# SERVICE CALLS
# ============================================================================

@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ('ticket_no', 'client_display', 'contract_type', 'service_type', 'status', 'reported_date', 'get_technicians', 'client_verification', 'technician_manager_approval')
    list_filter = ('status', 'contract_type', 'service_type', 'reported_date', 'department', 'client_verification', 'technician_manager_approval')
    search_fields = ('ticket_no', 'client__client_name', 'client_name', 'item__machine_name', 'fault_reported')
    filter_horizontal = ('technician',)
    readonly_fields = ('created_at', 'updated_at', 'get_technicians', 'images_preview', 'ticket_no')
    raw_id_fields = ('client', 'item', 'client_machine', 'lease', 'lease_service_schedule')
    date_hierarchy = 'reported_date'
    
    def client_display(self, obj):
        if obj.client:
            return obj.client.client_name
        return obj.client_name or "Walk-in"
    client_display.short_description = 'Client'
    
    def get_technicians(self, obj):
        return ", ".join([f"{t.firstname} {t.lastname}" for t in obj.technician.all()]) if obj.technician.exists() else "No technicians assigned"
    get_technicians.short_description = "Technicians"

    def images_preview(self, obj):
        if obj.images:
            html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
            for image_url in obj.images:
                html += f'<img src="{image_url}" width="100" height="100" style="object-fit: cover; border-radius: 5px;" />'
            html += '</div>'
            return format_html(html)
        return "No images"
    images_preview.short_description = "Images Preview"
    
    fieldsets = (
        ('Call Information', {
            'fields': ('ticket_no', 'contract_type', 'service_type', 'lpo', 'status')
        }),
        ('Client Details', {
            'fields': ('client', 'client_name', 'client_location', 'department')
        }),
        ('Machine Information', {
            'fields': ('item', 'client_machine', 'walk_in_machine_name', 'walk_in_machine_type', 'walk_in_serial_no')
        }),
        ('Service Details', {
            'fields': ('reported_by', 'reported_date', 'fault_reported', 'action_taken', 'parts_required', 'parts_used', 'spare_description')
        }),
        ('Meter Readings', {
            'fields': ('meter_reading', 'color_meter_reading', 'mono_meter_reading'),
            'classes': ('collapse',)
        }),
        ('Timing', {
            'fields': ('start_time', 'finish_time'),
            'classes': ('collapse',)
        }),
        ('Assignment & Verification', {
            'fields': ('technician', 'get_technicians', 'client_verification', 'technician_manager_approval')
        }),
        ('Lease Information', {
            'fields': ('lease', 'lease_service_schedule'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('comments', 'director_comment', 'is_checked', 'images', 'images_preview'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(StorePartInquiry)
class StorePartInquiryAdmin(admin.ModelAdmin):
    list_display = ('service_call', 'part_name', 'quantity', 'unit_price', 'add_vat', 'status', 'requested_by', 'issued_by', 'requested_at')
    list_filter = ('status', 'add_vat', 'is_issued', 'requested_at')
    search_fields = ('part_name', 'service_call__ticket_no', 'requested_by__email')
    raw_id_fields = ('service_call', 'requested_by', 'issued_by')
    readonly_fields = ('requested_at',)
    date_hierarchy = 'requested_at'

@admin.register(StoreAccessoryInquiry)
class StoreAccessoryInquiryAdmin(admin.ModelAdmin):
    list_display = ('service_call', 'acc_name', 'quantity', 'unit_price', 'add_vat', 'status', 'requested_by', 'issued_by', 'requested_at')
    list_filter = ('status', 'add_vat', 'is_issued', 'requested_at')
    search_fields = ('acc_name', 'service_call__ticket_no', 'requested_by__email')
    raw_id_fields = ('service_call', 'requested_by', 'issued_by')
    readonly_fields = ('requested_at',)
    date_hierarchy = 'requested_at'

@admin.register(ServiceCallToken)
class ServiceCallTokenAdmin(admin.ModelAdmin):
    list_display = ('service_call', 'email', 'created_at', 'expires_at', 'is_used', 'is_valid_display')
    list_filter = ('is_used', 'expires_at', 'created_at')
    search_fields = ('email', 'service_call__ticket_no')
    readonly_fields = ('created_at', 'is_valid_display')
    raw_id_fields = ('service_call',)

    def is_valid_display(self, obj):
        return obj.is_valid()
    is_valid_display.boolean = True
    is_valid_display.short_description = 'Valid'

# ============================================================================
# LEASE CONTRACTS
# ============================================================================

@admin.register(LeaseContract)
class LeaseContractAdmin(admin.ModelAdmin):
    list_display = ('lease_no', 'client', 'item', 'contract_type', 'from_date', 'to_date', 'is_active', 'account_handler_display', 'technician_display', 'payment_status')
    list_filter = ('contract_type', 'is_active', 'store', 'from_date', 'to_date', 'add_vat', 'add_myq', 'payment_status')
    search_fields = ('lease_no', 'client__client_name', 'item__machine_name')
    readonly_fields = ('created_at', 'updated_at', 'account_handler_display', 'technician_display', 'lease_no')
    raw_id_fields = ('client', 'item', 'store', 'account_handler', 'technician')
    date_hierarchy = 'from_date'
    
    def account_handler_display(self, obj):
        if obj.account_handler:
            return f"{obj.account_handler.firstname} {obj.account_handler.lastname}"
        return "Not Assigned"
    account_handler_display.short_description = 'Account Handler'
    
    def technician_display(self, obj):
        if obj.technician:
            return f"{obj.technician.firstname} {obj.technician.lastname}"
        return "Not Assigned"
    technician_display.short_description = 'Technician'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lease_no', 'client', 'contract_type', 'department', 'store')
        }),
        ('Machine & Dates', {
            'fields': ('item', 'from_date', 'to_date', 'is_active')
        }),
        ('Counter Settings', {
            'fields': ('initial_mono_counter', 'initial_color_counter', 'monochrome_rate', 'color_rate'),
            'description': 'Initial counter readings and per-copy rates'
        }),
        ('Billing Options', {
            'fields': ('add_vat', 'add_myq', 'billed_myq')
        }),
        ('Assignment', {
            'fields': ('account_handler', 'account_handler_display', 'technician', 'technician_display')
        }),
        ('Payment Tracking', {
            'fields': ('amount_paid', 'remaining_balance', 'payment_status', 'payment_notes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(LeaseServiceSchedule)
class LeaseServiceScheduleAdmin(admin.ModelAdmin):
    list_display = ('lease', 'service_type', 'frequency', 'start_date', 'end_date', 'is_active', 'created_at')
    list_filter = ('service_type', 'frequency', 'is_active', 'start_date', 'end_date')
    search_fields = ('lease__lease_no', 'lpo')
    filter_horizontal = ('default_technicians',)
    raw_id_fields = ('lease',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'start_date'

@admin.register(LeaseMachineSwap)
class LeaseMachineSwapAdmin(admin.ModelAdmin):
    list_display = ('lease', 'old_machine', 'new_machine', 'swapped_by', 'swapped_at')
    list_filter = ('swapped_at',)
    search_fields = ('lease__lease_no', 'old_machine__serial_no', 'new_machine__serial_no')
    raw_id_fields = ('lease', 'old_machine', 'new_machine', 'swapped_by')
    readonly_fields = ('swapped_at',)
    date_hierarchy = 'swapped_at'

@admin.register(MeterReading)
class MeterReadingAdmin(admin.ModelAdmin):
    list_display = ('lease', 'machine', 'month', 'meter_reading', 'mono_meter_reading', 'color_meter_reading', 'created_at')
    list_filter = ('month', 'created_at')
    search_fields = ('lease__lease_no', 'machine__machine_name', 'machine__serial_no')
    raw_id_fields = ('lease', 'machine')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'month'

@admin.register(LeasePayment)
class LeasePaymentAdmin(admin.ModelAdmin):
    list_display = ('lease', 'amount', 'payment_method', 'payment_type', 'payment_date', 'reference_number', 'meter_reading', 'created_by')
    list_filter = ('payment_method', 'payment_type', 'payment_date', 'created_at')
    search_fields = ('lease__lease_no', 'reference_number')
    raw_id_fields = ('lease', 'meter_reading', 'created_by')
    readonly_fields = ('created_at',)
    date_hierarchy = 'payment_date'

@admin.register(MyQPayment)
class MyQPaymentAdmin(admin.ModelAdmin):
    list_display = ('lease', 'payment_type', 'one_off_amount', 'color_rate', 'monochrome_rate', 'created_at')
    list_filter = ('payment_type', 'created_at')
    search_fields = ('lease__lease_no',)
    raw_id_fields = ('lease',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LeasePartInquiry)
class LeasePartInquiryAdmin(admin.ModelAdmin):
    list_display = ('lease_display', 'part', 'quantity', 'unit_amount', 'subtotal', 'vat_amount', 'total_amount', 'apply_vat', 'payment_status', 'date')
    list_filter = ('apply_vat', 'payment_status', 'date', 'vat_rate')
    search_fields = ('lease__lease_no', 'part__part_name')
    date_hierarchy = 'date'
    readonly_fields = ('subtotal', 'vat_amount', 'total_amount', 'created_at', 'updated_at')
    raw_id_fields = ('lease', 'part', 'store_part_inquiry')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lease', 'part', 'store_part_inquiry', 'quantity', 'date')
        }),
        ('Pricing & VAT', {
            'fields': ('unit_amount', 'apply_vat', 'vat_rate', 'subtotal', 'vat_amount', 'total_amount'),
            'description': 'VAT calculations are automatically computed based on settings'
        }),
        ('Payment Information', {
            'fields': ('payment_type', 'initial_payment', 'amount_paid', 'remaining_balance', 'payment_status', 'due_date', 'payment_notes')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def lease_display(self, obj):
        return obj.lease.lease_no if obj.lease else "No Lease"
    lease_display.short_description = 'Lease Contract'

@admin.register(LeaseAccInquiry)
class LeaseAccInquiryAdmin(admin.ModelAdmin):
    list_display = ('lease', 'accessory', 'quantity', 'unit_amount', 'subtotal', 'vat_amount', 'total_amount', 'apply_vat', 'payment_status', 'date')
    list_filter = ('apply_vat', 'payment_status', 'date')
    search_fields = ('lease__lease_no', 'accessory__acc_name')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at', 'subtotal', 'vat_amount', 'total_amount')
    raw_id_fields = ('lease', 'accessory', 'store_acc_inquiry')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lease', 'accessory', 'store_acc_inquiry', 'quantity', 'date')
        }),
        ('Pricing & VAT', {
            'fields': ('unit_amount', 'apply_vat', 'vat_rate', 'subtotal', 'vat_amount', 'total_amount')
        }),
        ('Payment Information', {
            'fields': ('payment_type', 'initial_payment', 'amount_paid', 'remaining_balance', 'payment_status', 'due_date', 'payment_notes')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(LeasePartInquiryPayment)
class LeasePartInquiryPaymentAdmin(admin.ModelAdmin):
    list_display = ('inquiry', 'amount', 'payment_method', 'payment_date', 'reference_number', 'created_by', 'created_at')
    list_filter = ('payment_method', 'payment_date', 'created_at')
    search_fields = ('inquiry__lease__lease_no', 'inquiry__part__part_name', 'reference_number')
    raw_id_fields = ('inquiry', 'created_by')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'payment_date'

@admin.register(LeaseAccInquiryPayment)
class LeaseAccInquiryPaymentAdmin(admin.ModelAdmin):
    list_display = ('inquiry', 'amount', 'payment_method', 'payment_date', 'reference_number', 'created_by', 'created_at')
    list_filter = ('payment_method', 'payment_date', 'created_at')
    search_fields = ('inquiry__lease__lease_no', 'inquiry__accessory__acc_name', 'reference_number')
    raw_id_fields = ('inquiry', 'created_by')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'payment_date'

# ============================================================================
# SALES MANAGEMENT
# ============================================================================

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    fields = ('sale_type', 'machine', 'part', 'accessory', 'quantity', 'unit_price', 'subtotal', 'vat_amount', 'total_price')
    readonly_fields = ('subtotal', 'vat_amount', 'total_price')
    raw_id_fields = ('machine', 'part', 'accessory')

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ('payment_date', 'amount', 'payment_method', 'reference_number', 'notes', 'created_by')
    readonly_fields = ('created_by',)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('created_by')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sale_no', 'client_display', 'sale_type', 'sale_date', 'subtotal', 'vat_total', 'total_amount', 'amount_paid', 'remaining_balance', 'payment_status', 'is_overdue_display', 'created_at')
    list_filter = ('sale_type', 'sale_date', 'add_vat', 'payment_status', 'created_at')
    search_fields = ('sale_no', 'client__client_name', 'local_client_name')
    readonly_fields = ('sale_no', 'subtotal', 'vat_total', 'total_amount', 'amount_paid', 'remaining_balance', 'payment_status', 'is_overdue_display', 'created_at', 'updated_at')
    date_hierarchy = 'sale_date'
    raw_id_fields = ('client', 'store_part_inquiry', 'store_acc_inquiry')
    inlines = [SaleItemInline, PaymentInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sale_no', 'sale_type', 'client', 'local_client_name', 'sale_date', 'lpo')
        }),
        ('VAT Configuration', {
            'fields': ('add_vat', 'vat_rate'),
            'description': 'Configure VAT settings for this sale'
        }),
        ('Financial Summary', {
            'fields': ('subtotal', 'vat_total', 'total_amount', 'amount_paid', 'remaining_balance', 'payment_status')
        }),
        ('Payment Information', {
            'fields': ('due_date', 'payment_notes', 'is_overdue_display'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'store_part_inquiry', 'store_acc_inquiry'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def client_display(self, obj):
        if obj.client:
            return obj.client.client_name
        elif obj.local_client_name:
            return f"{obj.local_client_name} (Local)"
        return "Unknown Client"
    client_display.short_description = 'Client'
    
    def is_overdue_display(self, obj):
        return obj.is_overdue
    is_overdue_display.short_description = 'Overdue'
    is_overdue_display.boolean = True
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.calculate_totals()
        obj.save()
    
    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if formset.model == SaleItem:
            form.instance.calculate_totals()
            form.instance.save()
    
    actions = ['recalculate_totals', 'update_payment_status']
    
    def recalculate_totals(self, request, queryset):
        for sale in queryset:
            sale.calculate_totals()
            sale.save()
        self.message_user(request, f'Recalculated totals for {queryset.count()} sales.')
    recalculate_totals.short_description = "Recalculate totals for selected sales"

    def update_payment_status(self, request, queryset):
        for sale in queryset:
            sale.update_payment_status()
            sale.save()
        self.message_user(request, f'Updated payment status for {queryset.count()} sales.')
    update_payment_status.short_description = "Update payment status for selected sales"

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('sale', 'sale_type', 'get_item_name', 'quantity', 'unit_price', 'subtotal', 'vat_amount', 'total_price')
    list_filter = ('sale_type', 'sale__add_vat')
    search_fields = ('sale__sale_no', 'machine__machine_name', 'part__part_name', 'accessory__acc_name')
    readonly_fields = ('subtotal', 'vat_amount', 'total_price')
    raw_id_fields = ('sale', 'machine', 'part', 'accessory')
    
    fieldsets = (
        ('Sale Information', {
            'fields': ('sale', 'sale_type')
        }),
        ('Item Details', {
            'fields': ('machine', 'part', 'accessory', 'custom_item')
        }),
        ('Pricing', {
            'fields': ('quantity', 'unit_price', 'subtotal', 'vat_amount', 'total_price'),
            'description': 'VAT is calculated based on the parent sale VAT settings'
        }),
    )
    
    def get_item_name(self, obj):
        if obj.machine:
            return obj.machine.machine_name
        elif obj.part:
            return obj.part.part_name
        elif obj.accessory:
            return obj.accessory.acc_name
        elif obj.custom_item:
            return obj.custom_item.get('name', 'Custom Item')
        return 'Unknown Item'
    get_item_name.short_description = 'Item Name'
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.sale.calculate_totals()
        obj.sale.save()

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('sale_display', 'payment_date', 'amount', 'payment_method', 'reference_number', 'created_by_display', 'created_at')
    list_filter = ('payment_method', 'payment_date', 'created_at')
    search_fields = ('sale__sale_no', 'reference_number', 'created_by__email')
    readonly_fields = ('created_at', 'created_by_display')
    raw_id_fields = ('sale', 'created_by')
    date_hierarchy = 'payment_date'
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('sale', 'payment_date', 'amount', 'payment_method', 'reference_number')
        }),
        ('Additional Details', {
            'fields': ('notes', 'created_by_display'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def sale_display(self, obj):
        return obj.sale.sale_no if obj.sale else "No Sale"
    sale_display.short_description = 'Sale Number'
    
    def created_by_display(self, obj):
        if obj.created_by:
            return f"{obj.created_by.firstname} {obj.created_by.lastname} ({obj.created_by.email})"
        return "System"
    created_by_display.short_description = 'Created By'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        
        if obj.sale:
            obj.sale.calculate_totals()
            obj.sale.update_payment_status()
            obj.sale.save()
    
    actions = ['mark_as_cash_payments', 'mark_as_bank_transfer_payments']
    
    def mark_as_cash_payments(self, request, queryset):
        updated = queryset.update(payment_method='Cash')
        self.message_user(request, f'{updated} payments marked as Cash.')
    mark_as_cash_payments.short_description = "Mark selected payments as Cash"

    def mark_as_bank_transfer_payments(self, request, queryset):
        updated = queryset.update(payment_method='Bank Transfer')
        self.message_user(request, f'{updated} payments marked as Bank Transfer.')
    mark_as_bank_transfer_payments.short_description = "Mark selected payments as Bank Transfer"

# ============================================================================
# DELIVERY MANAGEMENT
# ============================================================================

@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('delivery_no', 'delivery_type', 'client_name', 'status', 'assigned_to_display', 'delivery_date', 'customer_signature', 'created_at')
    list_filter = ('delivery_type', 'status', 'delivery_date', 'customer_signature', 'created_at')
    search_fields = ('delivery_no', 'sale__client__client_name', 'sale__local_client_name', 'lease__client__client_name', 'delivery_notes')
    readonly_fields = ('delivery_no', 'created_at', 'updated_at', 'client_name', 'client_location', 'total_items', 'total_amount')
    raw_id_fields = ('sale', 'lease', 'assigned_to')
    date_hierarchy = 'delivery_date'
    
    fieldsets = (
        ('Delivery Information', {
            'fields': ('delivery_no', 'delivery_type', 'sale', 'lease', 'lpo')
        }),
        ('Client Information', {
            'fields': ('client_name', 'client_location')
        }),
        ('Assignment & Status', {
            'fields': ('assigned_to', 'assigned_to_display', 'status', 'delivery_date', 'customer_signature')
        }),
        ('Summary', {
            'fields': ('total_items', 'total_amount', 'delivery_notes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def client_name(self, obj):
        return obj.client_name
    client_name.short_description = 'Client Name'
    
    def assigned_to_display(self, obj):
        return f"{obj.assigned_to.firstname} {obj.assigned_to.lastname}"
    assigned_to_display.short_description = 'Assigned To'

# ============================================================================
# QUOTATION MANAGEMENT
# ============================================================================

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1
    fields = ('item_type', 'item_name', 'item_brand', 'quantity', 'unit_price', 'total_price', 'description')
    readonly_fields = ('total_price',)

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('quotation_no', 'client_display', 'status', 'subtotal', 'vat_amount', 'total_amount', 'valid_until', 'created_by', 'created_at')
    list_filter = ('status', 'created_at', 'valid_until', 'include_vat')
    search_fields = ('quotation_no', 'client__client_name', 'client_name')
    inlines = [QuotationItemInline]
    readonly_fields = ('quotation_no', 'subtotal', 'vat_amount', 'total_amount', 'created_at', 'updated_at')
    raw_id_fields = ('client', 'created_by')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('quotation_no', 'client', 'client_name', 'client_location', 'created_by', 'status')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'valid_until')
        }),
        ('Financial Details', {
            'fields': ('include_vat', 'vat_rate', 'subtotal', 'vat_amount', 'total_amount')
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def client_display(self, obj):
        return obj.client.client_name if obj.client else obj.client_name
    client_display.short_description = 'Client'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(QuotationItem)
class QuotationItemAdmin(admin.ModelAdmin):
    list_display = ('quotation', 'item_type', 'item_name', 'item_brand', 'quantity', 'unit_price', 'total_price')
    list_filter = ('item_type',)
    search_fields = ('item_name', 'item_brand', 'quotation__quotation_no')
    readonly_fields = ('total_price',)
    raw_id_fields = ('quotation',)

# ============================================================================
# PURCHASE ORDER MANAGEMENT
# ============================================================================

class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    fields = ('item_type', 'item_name', 'item_brand', 'item_code', 'quantity', 'unit_price', 'vat_amount', 'total_price', 'description')
    readonly_fields = ('total_price',)

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'status', 'subtotal', 'vat_amount', 'total_amount', 'required_by_date', 'created_by', 'verified_by_sales_manager', 'verified_by_director', 'created_at')
    list_filter = ('status', 'include_vat', 'created_at', 'required_by_date')
    search_fields = ('po_number', 'supplier', 'created_by__email')
    inlines = [PurchaseOrderItemInline]
    readonly_fields = ('po_number', 'subtotal', 'vat_amount', 'total_amount', 'created_at', 'updated_at')
    raw_id_fields = ('created_by', 'verified_by_sales_manager', 'verified_by_director')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('po_number', 'supplier', 'supplier_address', 'status', 'required_by_date')
        }),
        ('Financial Details', {
            'fields': ('include_vat', 'vat_rate', 'subtotal', 'vat_amount', 'total_amount')
        }),
        ('Verification', {
            'fields': ('created_by', 'verified_by_sales_manager', 'verified_by_director')
        }),
        ('Additional Information', {
            'fields': ('notes', 'uploaded_pdf'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'item_type', 'item_name', 'item_brand', 'item_code', 'quantity', 'unit_price', 'vat_amount', 'total_price')
    list_filter = ('item_type',)
    search_fields = ('item_name', 'item_brand', 'item_code', 'purchase_order__po_number')
    readonly_fields = ('total_price',)
    raw_id_fields = ('purchase_order',)

# ============================================================================
# CHAT MANAGEMENT
# ============================================================================

@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'member_count', 'created_at', 'updated_at')
    search_fields = ('name',)
    filter_horizontal = ('members',)
    readonly_fields = ('created_at', 'updated_at', 'member_count')
    date_hierarchy = 'created_at'

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'chat_group', 'message_type', 'content_preview', 'file_preview', 'created_at')
    list_filter = ('message_type', 'created_at')
    search_fields = ('content', 'sender__email', 'chat_group__name')
    raw_id_fields = ('chat_group', 'sender')
    filter_horizontal = ('read_by',)
    readonly_fields = ('created_at', 'file_url', 'file_preview')

    def content_preview(self, obj):
        if obj.content:
            return f"{obj.content[:50]}..." if len(obj.content) > 50 else obj.content
        return "No content"
    content_preview.short_description = 'Content'
    
    def file_preview(self, obj):
        if obj.file:
            if obj.message_type == 'image':
                return format_html('<img src="{}" width="100" height="100" />', obj.file.url)
            return format_html('<a href="{}" target="_blank">View File</a>', obj.file.url)
        return "No file"
    file_preview.short_description = 'File'

# ============================================================================
# ADMIN SITE CONFIGURATION
# ============================================================================

admin.site.site_header = "Inventory Management System"
admin.site.site_title = "IMS Admin"
admin.site.index_title = "Welcome to Inventory Management System Administration"