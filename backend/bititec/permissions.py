from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

class AllowAnyForVerify(permissions.BasePermission):
    def has_permission(self, request, view):
        return view.action == 'verify'

class HasKeyPermission(permissions.BasePermission):
    """Base permission class for key-based access with store support"""
    required_key = None
    
    def get_required_action(self, request):
        """Map HTTP methods to actions"""
        method_action_map = {
            'GET': 'read',
            'POST': 'create',
            'PUT': 'update',
            'PATCH': 'update',
            'DELETE': 'delete'
        }
        return method_action_map.get(request.method, 'read')
    
    def has_permission(self, request, view):
        if not self.required_key:
            return False
            
        user = request.user
        action = self.get_required_action(request)
        return user.has_permission(self.required_key, action)
    
    def has_object_permission(self, request, view, obj):
        if not self.required_key:
            return False
            
        user = request.user
        action = self.get_required_action(request)
        return user.has_permission(self.required_key, action, obj)

class HasSalesPermission(HasKeyPermission):
    required_key = 'sales'

class HasInventoryPermission(HasKeyPermission):
    required_key = 'inventory'

class HasCallsPermission(HasKeyPermission):
    required_key = 'calls'

class HasLeasesPermission(HasKeyPermission):
    required_key = 'leases'

# Specific action permissions
class HasSalesReadPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_permission('sales', 'read')

class HasSalesCreatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_permission('sales', 'create')

class HasSalesUpdatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_permission('sales', 'update')

class HasSalesDeletePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_permission('sales', 'delete')

class HasInventoryReadPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_permission('inventory', 'read')

class HasInventoryCreatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_permission('inventory', 'create')

class HasInventoryUpdatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_permission('inventory', 'update')

class HasInventoryDeletePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_permission('inventory', 'delete')
    
class HasObjectStorePermission(permissions.BasePermission):
    """
    Permission check for store-level access on specific objects.
    """
    def has_object_permission(self, request, view, obj):
        # Get the store from the object
        store = None
        if hasattr(obj, 'store'):
            store = obj.store
        elif hasattr(obj, 'stores'):
            # For many-to-many relationships
            store = obj.stores.first()
        
        if not store:
            # If no store association, only allow if user is Director/Super Admin
            return request.user.role in ['Director', 'Super Admin']
        
        # Check if user has access to this store
        return request.user.check_store_access(store)
    
class StorePermissionMixin:
    """
    Mixin to filter querysets based on user's store permissions
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Directors and Super Admins have access to all stores
        if user.role in ['Director', 'Super Admin']:
            return queryset
        
        # For other users, filter by their assigned stores
        user_stores = user.stores.all()
        
        # Handle different models with store relationships
        if hasattr(queryset.model, 'store'):
            return queryset.filter(store__in=user_stores)
        elif hasattr(queryset.model, 'stores'):
            return queryset.filter(stores__in=user_stores).distinct()
        elif hasattr(queryset.model, 'item') and hasattr(queryset.model.item, 'store'):
            return queryset.filter(item__store__in=user_stores)
        elif hasattr(queryset.model, 'service_call') and hasattr(queryset.model.service_call, 'item'):
            return queryset.filter(service_call__item__store__in=user_stores)
        
        # Default: return empty queryset for models without store relationship
        return queryset.none()
    
    def check_store_permission(self, store):
        """Check if user has permission to access a specific store"""
        user = self.request.user
        
        # Directors and Super Admins have access to all stores
        if user.role in ['Director', 'Super Admin']:
            return True
        
        # Check if the store is in user's assigned stores
        return store in user.stores.all()
    
    def perform_create(self, serializer):
        user = self.request.user
        
        # For Directors/Super Admins, allow any store
        if user.role in ['Director', 'Super Admin']:
            serializer.save()
            return
        
        # For other users, validate that the store is in their assigned stores
        store_data = serializer.validated_data.get('store')
        if store_data and not self.check_store_permission(store_data):
            raise PermissionDenied("You don't have permission to create records for this store")
        
        serializer.save()