from rest_framework import permissions

class AllowAnyForVerify(permissions.BasePermission):
    def has_permission(self, request, view):
        # Allow unauthenticated access only to the verify action
        return view.action == 'verify'