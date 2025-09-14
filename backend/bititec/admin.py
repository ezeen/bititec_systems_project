from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Accessory, AccessoryType, Call, ChatGroup, ChatMessage, Client, ClientMachine, CustomUser, Delivery, KeyAudit, LeaseAccInquiry, LeaseContract, LeasePartInquiry, LoginAttempt, Machine, MachineType, MeterReading, Part, PartType, Quotation, QuotationItem, Sale, SaleItem, SecurityEvent, ServiceCallToken, Store, StoreAccessoryInquiry, StorePartInquiry
from django.utils.html import format_html

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'get_full_name', 'role', 'active', 'is_staff', 'profile_image_tag', 'failed_login_attempts', 'is_locked_display', 'stores_display')
    list_filter = ('role', 'active', 'is_staff', 'failed_login_attempts', 'stores')
    search_fields = ('email', 'firstname', 'lastname')
    ordering = ('email',)
    readonly_fields = ('profile_image_tag', 'is_locked_display', 'keys_granted_at', 'last_failed_login', 'stores_display')
    filter_horizontal = ('stores',)  # Add this for better UI for many-to-many field

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
        """Display assigned stores in a comma-separated format"""
        stores = obj.stores.all()
        if stores:
            return ", ".join([f"{store.store_name} ({store.store_location})" for store in stores])
        return "No stores assigned"
    stores_display.short_description = 'Assigned Stores'
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('firstname', 'lastname', 'phonenumber', 'role', 'profile_image', 'profile_image_tag')}),
        ('Store Assignments', {'fields': ('stores', 'stores_display')}),  # Add this section
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
            'fields': ('unit_value', 'quantity', 'condition_description', 'machine_condition', 'color_type')
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
            'fields': ('unit_value', 'intial_quantity', 'quantity', 'condition_description', 'part_condition', 'color_type')
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
            'fields': ('unit_value', 'intial_quantity', 'quantity', 'condition_description', 'acc_condition', 'color_type')
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
    list_display = ('ticket_no', 'client', 'item', 'status', 'reported_date', 'get_technicians', 'images_preview')
    list_filter = ('status', 'reported_date', 'department')
    search_fields = ('ticket_no', 'client__client_name', 'item__machine_name')
    filter_horizontal = ('technician',)
    readonly_fields = ('created_at', 'updated_at', 'get_technicians', 'images_preview')
    
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

@admin.register(LeaseContract)
class LeaseContractAdmin(admin.ModelAdmin):
    list_display = ('lease_no', 'client', 'item', 'contract_type', 'is_active')
    list_filter = ('contract_type', 'is_active', 'store')
    search_fields = ('lease_no', 'client__client_name', 'item__machine_name')
    readonly_fields = ('created_at', 'updated_at')

# Updated SaleItem inline with VAT handling
class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    fields = ('sale_type', 'machine', 'part', 'accessory', 'quantity', 'unit_price', 'subtotal', 'vat_amount', 'total_price')
    readonly_fields = ('subtotal', 'vat_amount', 'total_price')
    raw_id_fields = ('machine', 'part', 'accessory')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sale_no', 'client_display', 'sale_type', 'sale_date', 'subtotal', 'vat_total', 'total_amount', 'created_at')
    list_filter = ('sale_type', 'sale_date', 'add_vat', 'client')
    search_fields = ('sale_no', 'client__client_name', 'local_client_name')
    readonly_fields = ('sale_no', 'subtotal', 'vat_total', 'total_amount', 'created_at', 'updated_at')
    date_hierarchy = 'sale_date'
    raw_id_fields = ('client',)  # Removed 'store_inquiry' as it doesn't exist in Sale model
    inlines = [SaleItemInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('sale_no', 'sale_type', 'client', 'local_client_name', 'sale_date')
        }),
        ('VAT Configuration', {
            'fields': ('add_vat', 'vat_rate'),
            'description': 'Configure VAT settings for this sale'
        }),
        ('Financial Summary', {
            'fields': ('subtotal', 'vat_total', 'total_amount'),
            'classes': ('collapse',)
        }),
        ('Additional Information', {
            'fields': ('notes', 'store_part_inquiry', 'store_acc_inquiry'),  # Using correct field names
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
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Recalculate totals after saving
        obj.calculate_totals()
        obj.save()
    
    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        # Recalculate totals after saving items
        if formset.model == SaleItem:
            form.instance.calculate_totals()
            form.instance.save()

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
        # Recalculate sale totals after saving item
        obj.sale.calculate_totals()
        obj.sale.save()

@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('delivery_no', 'client_name', 'status', 'assigned_to_display', 'delivery_date')
    list_filter = ('status', 'delivery_date')
    search_fields = ('delivery_no', 'sale__client__client_name', 'delivery_notes')
    readonly_fields = ('delivery_no', 'created_at', 'updated_at')
    
    def client_name(self, obj):
        if obj.delivery_type == 'Sale':
            if obj.sale:
                if obj.sale.client:
                    return obj.sale.client.client_name
                elif obj.sale.local_client_name:
                    return obj.sale.local_client_name
            return 'Unknown Sale Client'
        else:  # Lease
            if obj.lease and obj.lease.client:
                return obj.lease.client.client_name
            return 'Unknown Lease Client'
    client_name.short_description = 'Client Name'
    
    def assigned_to_display(self, obj):
        return f"{obj.assigned_to.firstname} {obj.assigned_to.lastname}"
    
    assigned_to_display.short_description = 'Assigned To'

@admin.register(LeasePartInquiry)
class LeasePartInquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'lease_display', 'part', 'quantity', 'unit_amount', 'subtotal', 'vat_amount', 'total_amount', 'apply_vat', 'is_paid', 'date')
    list_filter = ('is_paid', 'apply_vat', 'date', 'vat_rate')
    search_fields = ('lease__lease_no', 'part__part_name')
    date_hierarchy = 'date'
    readonly_fields = ('subtotal', 'vat_amount', 'total_amount', 'created_at', 'updated_at')
    raw_id_fields = ('lease', 'part', 'store_part_inquiry')  # Fixed: using correct field name
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lease', 'part', 'store_part_inquiry', 'quantity', 'date')  # Fixed: using correct field name
        }),
        ('Pricing & VAT', {
            'fields': ('unit_amount', 'apply_vat', 'vat_rate', 'subtotal', 'vat_amount', 'total_amount'),
            'description': 'VAT calculations are automatically computed based on settings'
        }),
        ('Status', {
            'fields': ('is_paid',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def lease_display(self, obj):
        return obj.lease.lease_no if obj.lease else "No Lease"
    lease_display.short_description = 'Lease Contract'
    
    def save_model(self, request, obj, form, change):
        # The model's save method will handle VAT calculations
        super().save_model(request, obj, form, change)

@admin.register(LeaseAccInquiry)
class LeaseAccInquiryAdmin(admin.ModelAdmin):
    # Fixed: using correct field names from the model
    list_display = ('id', 'lease', 'accessory', 'quantity', 'unit_amount', 'total_amount', 'date', 'is_paid')
    list_filter = ('is_paid', 'date', 'apply_vat')  # Fixed: using correct field name
    search_fields = ('lease__lease_no', 'accessory__acc_name')  # Fixed: using correct field name
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'updated_at', 'subtotal', 'vat_amount', 'total_amount')

@admin.register(ClientMachine)
class ClientMachineAdmin(admin.ModelAdmin):
    list_display = ('client_name', 'client_location', 'machine_name', 'serial_no', 'created_at')
    search_fields = ('client_name', 'machine_name', 'serial_no')
    list_filter = ('created_at',)
    readonly_fields = ('created_at',)

@admin.register(StorePartInquiry)
class StorePartInquiryAdmin(admin.ModelAdmin):
    list_display = ('part_name', 'quantity', 'status', 'requested_by', 'requested_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('part_name', 'service_call__ticket_no')
    raw_id_fields = ('service_call', 'requested_by', 'issued_by')
    readonly_fields = ('requested_at',)

@admin.register(StoreAccessoryInquiry)
class StoreAccessoryInquiryAdmin(admin.ModelAdmin):
    list_display = ('acc_name', 'quantity', 'status', 'requested_by', 'requested_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('acc_name', 'service_call__ticket_no')
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

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1
    fields = ('item_type', 'item_name', 'item_brand', 'quantity', 'unit_price', 'total_price')
    readonly_fields = ('total_price',)

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('quotation_no', 'client_display', 'status', 'total_amount', 'valid_until', 'created_at')
    list_filter = ('status', 'created_at', 'valid_until')
    search_fields = ('quotation_no', 'client__client_name', 'client_name')
    inlines = [QuotationItemInline]
    readonly_fields = ('subtotal', 'vat_amount', 'total_amount', 'created_at', 'updated_at')
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
    list_display = ('item_name', 'item_type', 'item_brand', 'quantity', 'unit_price', 'total_price', 'quotation')
    list_filter = ('item_type',)
    search_fields = ('item_name', 'quotation__quotation_no')
    readonly_fields = ('total_price',)

@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'email', 'success', 'timestamp')
    list_filter = ('success', 'timestamp')
    search_fields = ('ip_address', 'email')
    readonly_fields = ('timestamp',)

@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'ip_address', 'timestamp')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('user__email', 'ip_address', 'event_type')
    readonly_fields = ('timestamp',)

@admin.register(KeyAudit)
class KeyAuditAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'action_type', 'granted_by', 'timestamp')
    list_filter = ('action_type', 'key', 'timestamp')
    search_fields = ('user__email', 'key', 'granted_by__email')
    readonly_fields = ('timestamp',)
    raw_id_fields = ('user', 'granted_by')
    
    fieldsets = (
        ('Audit Information', {
            'fields': ('user', 'key', 'actions', 'action_type', 'granted_by', 'reason')
        }),
        ('Metadata', {
            'fields': ('timestamp',),
            'classes': ('collapse',)
        }),
    )