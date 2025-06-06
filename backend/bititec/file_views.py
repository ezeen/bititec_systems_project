# file_views.py
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import uuid
import os
from .models import message_file_path

class ChatFileUploadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if 'file' not in request.FILES:
            return Response(
                {"error": "No file uploaded"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        file = request.FILES['file']
        
        # Generate a path using the model's function
        file_name = message_file_path(None, file.name)
        
        # Save the file
        path = default_storage.save(file_name, ContentFile(file.read()))
        
        # Get the file URL
        file_url = default_storage.url(path)
        
        return Response({
            "file_url": file_url
        })