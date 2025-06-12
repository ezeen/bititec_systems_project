import re
from rest_framework import generics, permissions, status, filters, viewsets
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from .models import Accessory, AccessoryType, ChatGroup, ChatMessage, Client, ClientMachine, CustomUser, Delivery, LeaseAccInquiry, LeaseContract, LeasePartInquiry, MachineType, Machine, MeterReading, PartType, Part, Sale, SaleItem, Store, Call, ServiceCallToken, StoreInquiry
from .serializers import AccessorySerializer, AccessoryTypeSerializer, CallSerializer, ChatGroupSerializer, ChatMessageSerializer, ClientMachineSerializer, ClientSerializer, DeliverySerializer, LeaseAccInquirySerializer, LeaseContractSerializer, LeasePartInquirySerializer, MachineSerializer, MachineTypeSerializer, MeterReadingSerializer, PartSerializer, PartTypeSerializer, SaleSerializer, StoreInquirySerializer, UserSerializer, RegisterSerializer, StoreSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes, action
from django.db.models import Q, Count, Max, Prefetch, Sum
from django.db import transaction
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import update_session_auth_hash
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from decimal import Decimal, InvalidOperation  # Add this line



class UserListCreate(generics.ListCreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        role = self.request.query_params.get('role')
        if role:
            return CustomUser.objects.filter(role=role)
        return CustomUser.objects.all()

class UserRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    lookup_field = 'id'

    def perform_update(self, serializer):
        # Allow Directors to edit any user, others only themselves
        if not (self.request.user.role == 'Director' or 
                serializer.instance == self.request.user):
            raise PermissionDenied("You can only update your own profile")
        serializer.save()

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        # Include full image URL in response
        instance = self.get_object()
        response.data['profile_image'] = instance.profile_image.url if instance.profile_image else None
        return response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """
    Return the currently authenticated user's details
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password
    """
    user = request.user
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')
    
    if not current_password or not new_password:
        return Response(
            {'detail': 'Both current and new password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if current password is correct
    if not user.check_password(current_password):
        return Response(
            {'detail': 'Current password is incorrect'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Set new password and save
    user.set_password(new_password)
    user.save()
    
    # Update session authentication hash to keep user logged in
    update_session_auth_hash(request, user)
    
    return Response({'detail': 'Password changed successfully'})

class UserByIdView(generics.RetrieveAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'id'
    lookup_url_kwarg = 'user_id'

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class IsDirectorOrSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['Director', 'Super Admin']

class IsInventoryManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'Inventory Manager'

class IsSalesRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['Sales Member', 'Sales Manager']

class IsTechnicianRole(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['Technician', 'Technician Manager']

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    user = request.user
    return Response({
        'id': str(user.id),  
        'email': user.email,
        'firstname': user.firstname,
        'lastname': user.lastname,
        'role': user.role,
        'active': user.active
    })

def post(self, request, *args, **kwargs):
    serializer = self.get_serializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        "user": UserSerializer(user, context=self.get_serializer_context()).data,
        "message": "User created successfully",
    }, status=status.HTTP_201_CREATED)

class StoreListCreate(generics.ListCreateAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

class StoreRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class AccessoryTypeListCreate(generics.ListCreateAPIView):
    queryset = AccessoryType.objects.all()
    serializer_class = AccessoryTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class AccessoryTypeRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = AccessoryType.objects.all()
    serializer_class = AccessoryTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class MachineTypeListCreate(generics.ListCreateAPIView):
    queryset = MachineType.objects.all()
    serializer_class = MachineTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class MachineTypeRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = MachineType.objects.all()
    serializer_class = MachineTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class PartTypeListCreate(generics.ListCreateAPIView):
    queryset = PartType.objects.all()
    serializer_class = PartTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class PartTypeRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = PartType.objects.all()
    serializer_class = PartTypeSerializer
    permission_classes = [permissions.IsAuthenticated]

class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class MachineViewSet(viewsets.ModelViewSet):
    serializer_class = MachineSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    
    def get_queryset(self):
        store_id = self.request.query_params.get('store')
        status = self.request.query_params.get('machine_status')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        queryset = Machine.objects.all()
        
        if store_id:
            queryset = queryset.filter(store=store_id)
        if status:
            queryset = queryset.filter(machine_status=status)
            
        if start_date and end_date:
            try:
                # Parse dates and ensure they are in datetime format
                start = parse_date(start_date)
                end = parse_date(end_date)
                
                if start and end:
                    if start > end:
                        raise ValidationError("End date must be after start date")
                    
                    # Create a query that explicitly filters by created_at date
                    queryset = queryset.filter(created_at__date__gte=start, created_at__date__lte=end)
                    
                    # Debug logging - check the exact SQL query 
                    sql_query = str(queryset.query)

                    sample_data = list(queryset[:5].values('id', 'created_at'))
            except (ValueError, TypeError) as e:
                error_msg = f"Invalid date format. Use YYYY-MM-DD: {str(e)}"
                raise ValidationError(error_msg) from e

        return queryset.order_by('-created_at')
    
    def update(self, request, *args, **kwargs):
        # Handle partial updates properly
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, 
            data=request.data, 
            partial=True  # Ensure partial updates are allowed
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    
class PartViewSet(viewsets.ModelViewSet):
    serializer_class = PartSerializer  
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        part_status = self.request.query_params.get('part_status')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        queryset = Part.objects.prefetch_related(
            Prefetch('leasepartinquiry_set', 
                queryset=LeasePartInquiry.objects.select_related(
                    'lease__client', 'part'
                ).filter(lease__is_active=True)  # Only show active leases
            ),
            Prefetch('saleitem_set', 
                queryset=SaleItem.objects.select_related('sale__client')
            )
        )
        
        store_id = self.request.query_params.get('store')
        if store_id:
            queryset = queryset.filter(store=store_id)
        if part_status:  
            queryset = queryset.filter(part_status=part_status)
            
        if start_date and end_date:
            try:
                # Parse dates and ensure they are in datetime format
                start = parse_date(start_date)
                end = parse_date(end_date)
                
                if start and end:
                    if start > end:
                        raise ValidationError("End date must be after start date")
                    
                    # Using __date correctly for comparing date fields
                    queryset = queryset.filter(created_at__date__gte=start, created_at__date__lte=end)
                    
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid date format. Use YYYY-MM-DD: {str(e)}") from e

        return queryset.order_by('-created_at')
    

class AccessoryViewSet(viewsets.ModelViewSet):
    serializer_class = AccessorySerializer  
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    
    def get_queryset(self):
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        acc_status = self.request.query_params.get('acc_status')
        
        queryset = Accessory.objects.prefetch_related(
            Prefetch('leaseaccinquiry_set', 
                queryset=LeaseAccInquiry.objects.select_related(
                    'lease__client', 'accessory'
                ).filter(lease__is_active=True)  
            ),
            Prefetch('saleitem_set', 
                queryset=SaleItem.objects.select_related('sale__client')
            )
        )
        
        store_id = self.request.query_params.get('store')
        if store_id:
            queryset = queryset.filter(store=store_id)
        if acc_status:  
            queryset = queryset.filter(acc_status=acc_status)
            
        if start_date and end_date:
            try:
                # Parse dates and ensure they are in datetime format
                start = parse_date(start_date)
                end = parse_date(end_date)
                
                if start and end:
                    if start > end:
                        raise ValidationError("End date must be after start date")
                    
                    # Using __date correctly for comparing date fields
                    queryset = queryset.filter(created_at__date__gte=start, created_at__date__lte=end)
                    
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid date format. Use YYYY-MM-DD: {str(e)}") from e

        return queryset.order_by('-created_at')
    
class MachineListCreate(generics.ListCreateAPIView):
    queryset = Machine.objects.all().select_related('store')
    serializer_class = MachineSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['machine_name', 'machine_brand', 'serial_no', 'store__store_name']
    ordering_fields = ['machine_name', 'created_at', 'unit_value']

    def get_queryset(self):
        store_id = self.request.query_params.get('store')
        machine_status = self.request.query_params.get('machine_status')  # Add this line
        queryset = Machine.objects.all()
        
        if store_id:
            queryset = queryset.filter(store=store_id)
        if machine_status:  # Add status filtering
            queryset = queryset.filter(machine_status=machine_status)
            
        return queryset

class MachineRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Machine.objects.all().select_related('store')
    serializer_class = MachineSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class PartListCreate(generics.ListCreateAPIView):
    queryset = Part.objects.all().select_related('store')
    serializer_class = PartSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['part_name', 'part_brand', 'serial_no', 'store__store_name']
    ordering_fields = ['part_name', 'created_at', 'unit_value']

    def get_queryset(self):
        store_id = self.request.query_params.get('store')
        if store_id:
            return Part.objects.filter(store=store_id)
        return Part.objects.all()

class PartRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Part.objects.all().select_related('store')
    serializer_class = PartSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class AccessoryListCreate(generics.ListCreateAPIView):
    queryset = Accessory.objects.all().select_related('store')
    serializer_class = AccessorySerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['acc_name', 'acc_brand', 'serial_no', 'store__store_name']
    ordering_fields = ['acc_name', 'created_at', 'unit_value']

    def get_queryset(self):
        store_id = self.request.query_params.get('store')
        if store_id:
            return Accessory.objects.filter(store=store_id)
        return Accessory.objects.all()

class AccessoryRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Accessory.objects.all().select_related('store')
    serializer_class = AccessorySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class ClientListCreate(generics.ListCreateAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['client_name', 'client_location']
    ordering_fields = ['client_name', 'created_at']

class ClientRetrieveUpdateDestroy(generics.RetrieveUpdateDestroyAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

class StoreInquiryViewSet(viewsets.ModelViewSet):
    serializer_class = StoreInquirySerializer
    permission_classes = [IsAuthenticated]
    requested_by = UserSerializer(read_only=True)
    lease_part_inquiries = LeasePartInquirySerializer(many=True, read_only=True)
    lookup_field = 'pk'
        
    def get_queryset(self):
        queryset = StoreInquiry.objects.select_related(
            'requested_by', 'issued_by', 'service_call'
        ).prefetch_related('lease_part_inquiries__part')

        service_call = self.request.query_params.get('service_call')
        if service_call:
            return StoreInquiry.objects.filter(service_call=service_call)
        return StoreInquiry.objects.all()
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = request.data.copy()
        if 'unit_price' in data:
            try:
                data['unit_price'] = Decimal(str(data['unit_price']))
            except (ValueError, TypeError, InvalidOperation) as e:
                return Response(
                    {'error': 'Invalid unit price format'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

class ClientMachineViewSet(viewsets.ModelViewSet):
    serializer_class = ClientMachineSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        client_name = self.request.query_params.get('client_name')
        client_location = self.request.query_params.get('client_location')
        
        if client_name and client_location:
            return ClientMachine.objects.filter(
                client_name=client_name,
                client_location=client_location
            )
        return ClientMachine.objects.all()

class CallViewSet(viewsets.ModelViewSet):
    queryset = Call.objects.all()  
    serializer_class = CallSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        status = self.request.query_params.get('status')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        technician_id = self.request.query_params.get('technician')
        
        queryset = super().get_queryset().select_related(
            'client', 
            'item', 
            'item__store'
        ).prefetch_related('technician')
        
        # Status filtering
        if status:
            status_mapping = {
                'open': 'Open',
                'pending': 'Pending',
                'in_progress': 'In Progress',
                'complete': 'Complete'
            }
            backend_status = status_mapping.get(status.lower(), status)
            queryset = queryset.filter(status=backend_status)

        # Technician filtering
        if technician_id:
            queryset = queryset.filter(technician__id=technician_id)

        # Date range filtering
        if start_date and end_date:
            try:
                start = parse_date(start_date)
                end = parse_date(end_date)
                
                if start and end:
                    if start > end:
                        raise ValidationError("End date must be after start date")
                    
                    queryset = queryset.filter(
                        created_at__date__gte=start,
                        created_at__date__lte=end
                    )
                    
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid date format. Use YYYY-MM-DD: {str(e)}") from e

        return queryset.order_by('-created_at')
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Check if both approvals are true after update
        updated_data = serializer.validated_data
        technician_approval = updated_data.get('technician_manager_approval', instance.technician_manager_approval)
        client_verification = updated_data.get('client_verification', instance.client_verification)
        
        if technician_approval and client_verification:
            updated_data['status'] = 'Complete'
        
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def create_access_token(self, request, pk=None):
        """
        Create a time-limited token for external users to access a specific service call
        """
        call = self.get_object()
        email = request.data.get('email')
        
        if not email:
            return Response({'error': 'Email is required'}, status=400)
        
        # Create a new token with 1-hour expiration
        token = ServiceCallToken.objects.create(
            service_call=call,
            email=email,
            expires_at=timezone.now() + timezone.timedelta(hours=1)
        )
        
        # Return the token ID that will be used in the URL
        return Response({
            'token': str(token.id),
            'expires_at': token.expires_at
        })

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def validate_token(self, request):
        """
        Validate a token and return the associated service call if valid
        """
        if request.method == 'OPTIONS':
            response = Response()
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'X-ServiceCall-Token, Content-Type'
            response['Access-Control-Max-Age'] = '86400'  # 24 hours
            return response
        
        token_id = request.query_params.get('token')
        
        if not token_id:
            return Response({'error': 'Token is required'}, status=400)
        
        try:
            if not re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$', token_id):
                return Response({'error': 'Invalid token format'}, status=400)
            token = ServiceCallToken.objects.get(id=token_id)
        except ServiceCallToken.DoesNotExist:
            return Response({'error': 'Invalid token'}, status=404)
        
        if not token.is_valid():
            return Response({
                'error': 'Token has expired or has been used',
                'expired': True
            }, status=403)
        
        # Return the service call data
        serializer = self.get_serializer(token.service_call)
        return Response(serializer.data) 

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def verify(self, request, pk=None):
        call = self.get_object()
        token = request.data.get('token')
        
        try:
            service_token = ServiceCallToken.objects.get(
                id=token,
                service_call=call,
                is_used=False,
                expires_at__gt=timezone.now()
            )
            call.client_verification = True
            call.save()
            service_token.is_used = True
            service_token.save()
            return Response({'status': 'verified'})
        except ServiceCallToken.DoesNotExist:
            return Response({'error': 'Invalid or expired token'}, status=400)
        
    @action(detail=True, methods=['patch'])
    def update_approval(self, request, pk=None):
        """Dedicated endpoint for approval updates"""
        call = self.get_object()
        field = request.data.get('field')
        value = request.data.get('value')
        
        # Validate the field
        if field not in ['technician_manager_approval', 'client_verification']:
            return Response({'error': 'Invalid field'}, status=400)
        
        # Validate the value
        if not isinstance(value, bool):
            return Response({'error': 'Value must be a boolean'}, status=400)
        
        # Update the field
        setattr(call, field, value)
        
        # Check if both approvals are now true and auto-complete
        if call.technician_manager_approval and call.client_verification and call.status != 'Complete':
            call.status = 'Complete'
        
        # Save the changes
        call.save()
        
        # Return serialized response
        serializer = self.get_serializer(call)
        return Response(serializer.data)

class LeaseContractViewSet(viewsets.ModelViewSet):
    serializer_class = LeaseContractSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def meter_readings(self, request, pk=None):
        lease = self.get_object()
        readings = lease.meter_readings.all().order_by('-month')
        serializer = MeterReadingSerializer(readings, many=True)
        return Response(serializer.data)
    
    def get_queryset(self):
        client_id = self.request.query_params.get('client')
        if client_id:
            return LeaseContract.objects.filter(client=client_id).select_related('client', 'item', 'store')
        return LeaseContract.objects.all().select_related('client', 'item', 'store')

    
class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Sale.objects.all().select_related('client').prefetch_related(
            'items__machine',
            'items__part',
            'items__accessory'
        )
        
        # Now apply filters
        client_id = self.request.query_params.get('client')
        client_name = self.request.query_params.get('client_name')
        sale_type = self.request.query_params.get('type')
        
        if client_id:
            queryset = queryset.filter(client=client_id)
        if client_name:
            queryset = queryset.filter(
                Q(client__client_name__icontains=client_name) |
                Q(local_client_name__icontains=client_name)
            )
        if sale_type:
            # Filter through the items' sale_type
            queryset = queryset.filter(items__sale_type=sale_type).distinct()
            
        return queryset.order_by('-created_at')
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)  # Allow partial updates
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, 
            data=request.data, 
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
    
class DeliveryViewSet(viewsets.ModelViewSet):
    queryset = Delivery.objects.all()
    serializer_class = DeliverySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['delivery_no', 'sale__sale_no', 'lease__lease_no']
    ordering_fields = ['delivery_date', 'created_at']

    def get_queryset(self):
        delivery_type = self.request.query_params.get('type')
        queryset = super().get_queryset()
        
        if delivery_type:
            queryset = queryset.filter(delivery_type=delivery_type)
            
        return queryset.select_related(
            'sale__client', 
            'lease__client', 
            'assigned_to'
        ).prefetch_related(
            'sale__items',
            'lease__part_inquiries',
            'lease__acc_inquiries'
        )

    @action(detail=False, methods=['post'])
    def create_delivery(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Handle sale or lease association
            delivery_type = serializer.validated_data['delivery_type']
            if delivery_type == 'Sale':
                if not serializer.validated_data.get('sale'):
                    return Response(
                        {"error": "Sale is required for sale deliveries"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            elif delivery_type == 'Lease':
                if not serializer.validated_data.get('lease'):
                    return Response(
                        {"error": "Lease is required for lease deliveries"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def delivery_types(self, request):
        return Response([
            {'value': 'Sale', 'label': 'Sale Delivery'},
            {'value': 'Lease', 'label': 'Lease Delivery'}
        ])
        
class ChatGroupViewSet(viewsets.ModelViewSet):
    queryset = ChatGroup.objects.all()
    serializer_class = ChatGroupSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Only return chat groups that the user is a member of"""
        user = self.request.user
        
        # Annotate with last message timestamp and unread count
        return ChatGroup.objects.filter(
            members=user
        ).annotate(
            last_message_time=Max('messages__created_at'),
            unread_count=Count(
                'messages', 
                filter=~Q(messages__read_by=user) & ~Q(messages__sender=user)
            )
        ).order_by('-last_message_time')
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get messages for a specific chat group"""
        try:
            group = self.get_queryset().get(pk=pk)
            
            # Get messages with prefetched read_by
            messages = ChatMessage.objects.filter(
                chat_group=group
            ).select_related('sender').prefetch_related('read_by')
            
            # Paginate results if needed
            page = self.paginate_queryset(messages)
            if page is not None:
                serializer = ChatMessageSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = ChatMessageSerializer(messages, many=True)
            return Response(serializer.data)
            
        except ChatGroup.DoesNotExist:
            return Response(
                {"error": "Chat group not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def global_chat(self, request):
        """Get the global chat group"""
        from .signals import GLOBAL_CHAT_ID, get_or_create_global_chat
        
        # Ensure global chat exists and user is a member
        global_chat = get_or_create_global_chat()
        
        # Make sure current user is a member
        if request.user not in global_chat.members.all():
            global_chat.members.add(request.user)
        
        # Annotate with unread count for this user
        queryset = ChatGroup.objects.filter(
            id=global_chat.id
        ).annotate(
            last_message_time=Max('messages__created_at'),
            unread_count=Count(
                'messages', 
                filter=~Q(messages__read_by=request.user) & ~Q(messages__sender=request.user)
            )
        )
        
        group = queryset.first()
        serializer = self.get_serializer(group)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark all messages in a group as read by the current user"""
        try:
            group = self.get_queryset().get(pk=pk)
            user = request.user

            unread_messages = ChatMessage.objects.filter(
                chat_group=group
            ).exclude(
                read_by=user
            )
            
            # Add user to read_by for all these messages
            for message in unread_messages:
                message.read_by.add(user)
            
            return Response({"status": "Messages marked as read"})
            
        except ChatGroup.DoesNotExist:
            return Response(
                {"error": "Chat group not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def create_or_get_direct_chat(self, request):
        """Create or get a direct chat between the current user and another user"""
        other_user_id = request.data.get('user_id')
        
        if not other_user_id:
            return Response(
                {"error": "user_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            other_user = CustomUser.objects.get(id=other_user_id)
            current_user = request.user
            
            # Check if a direct chat already exists
            existing_groups = ChatGroup.objects.annotate(
                member_count=Count('members')
            ).filter(
                member_count=2,
                members=current_user
            ).filter(
                members=other_user
            )
            
            if existing_groups.exists():
                group = existing_groups.first()
            else:
                # Create new direct chat
                group = ChatGroup.objects.create(
                    name=f"Chat with {other_user.firstname} {other_user.lastname}"
                )
                group.members.add(current_user, other_user)
                
            serializer = self.get_serializer(group)
            return Response(serializer.data)
            
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class ChatMessageViewSet(viewsets.ModelViewSet):
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Only return messages from groups the user is a member of"""
        user = self.request.user
        return ChatMessage.objects.filter(
            chat_group__members=user
        ).select_related('sender', 'chat_group')
    
    def perform_create(self, serializer):
        """Set the sender to the current user when creating a message"""
        serializer.save(sender=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a specific message as read"""
        try:
            message = self.get_queryset().get(pk=pk)
            user = request.user
            
            message.read_by.add(user)
            
            # Notify other users in the group
            channel_layer = get_channel_layer()
            
            for member in message.chat_group.members.exclude(id=user.id):
                notification_group = f'user_notifications_{member.id}'
                
                async_to_sync(channel_layer.group_send)(
                    notification_group,
                    {
                        'type': 'chat_notification',
                        'event': 'message_read',
                        'message_id': str(message.id),
                        'user_id': str(user.id),
                        'group_id': str(message.chat_group.id)
                    }
                )
            
            return Response({"status": "Message marked as read"})
            
        except ChatMessage.DoesNotExist:
            return Response(
                {"error": "Message not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
class LeasePartInquiryViewSet(viewsets.ModelViewSet):
    serializer_class = LeasePartInquirySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = LeasePartInquiry.objects.select_related(
            'part', 'lease', 'store_inquiry'
        ).all()
        
        # Filter by lease if provided
        lease_id = self.request.query_params.get('lease')
        if lease_id:
            queryset = queryset.filter(lease=lease_id)
            
        # Filter by store_inquiry if provided
        store_inquiry_id = self.request.query_params.get('store_inquiry')
        if store_inquiry_id:
            queryset = queryset.filter(store_inquiry=store_inquiry_id)
            
        return queryset
    
    def perform_create(self, serializer):
        with transaction.atomic():
            # Save the lease part inquiry
            instance = serializer.save()
            
            # Update the part inventory
            part = instance.part
            if part.quantity >= instance.quantity:
                part.quantity -= instance.quantity
                part.save()
            else:
                raise serializer.ValidationError(
                    f"Insufficient stock. Only {part.quantity} units available."
                )

    def perform_update(self, serializer):
        with transaction.atomic():
            old_instance = self.get_object()
            old_quantity = old_instance.quantity
            
            # Save the updated instance
            instance = serializer.save()
            
            # Adjust inventory based on quantity change
            part = instance.part
            quantity_difference = instance.quantity - old_quantity
            
            if quantity_difference > 0:
                # More parts needed - reduce inventory
                if part.quantity >= quantity_difference:
                    part.quantity -= quantity_difference
                    part.save()
                else:
                    raise serializers.ValidationError(
                        f"Insufficient stock for increase. Only {part.quantity} additional units available."
                    )
            elif quantity_difference < 0:
                # Fewer parts needed - restore inventory
                part.quantity += abs(quantity_difference)
                part.save()

    def perform_destroy(self, instance):
        with transaction.atomic():
            # Restore inventory when deleting
            part = instance.part
            part.quantity += instance.quantity
            part.save()
            
            # Delete the instance
            instance.delete()

class LeaseAccInquiryViewSet(viewsets.ModelViewSet):
    serializer_class = LeaseAccInquirySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        lease_id = self.request.query_params.get('lease')
        if lease_id:
            return LeaseAccInquiry.objects.filter(lease=lease_id).select_related('accessory', 'lease')
        return LeaseAccInquiry.objects.all()
    
class MeterReadingViewSet(viewsets.ModelViewSet):
    queryset = MeterReading.objects.all()
    serializer_class = MeterReadingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['lease__lease_no', 'machine__serial_no']
    ordering_fields = ['month', 'created_at']