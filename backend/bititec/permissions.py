# permissions.py - Updated with key-based permissions

from rest_framework import permissions

class AllowAnyForVerify(permissions.BasePermission):
    def has_permission(self, request, view):
        return view.action == 'verify'

class HasKeyPermission(permissions.BasePermission):
    """Base permission class for key-based access"""
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