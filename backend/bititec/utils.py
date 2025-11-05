import random
import string
import qrcode
import os
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image


def generate_unique_serial(prefix='', length=8, model_class=None, field_name='serial_no'):
    """
    Generate a unique alphanumeric serial number.
    
    Args:
        prefix: Optional prefix for the serial number
        length: Length of the random part (default: 8)
        model_class: Model class to check uniqueness against
        field_name: Field name to check for uniqueness (default: 'serial_no')
    
    Returns:
        Unique serial number string
    """
    characters = string.ascii_uppercase + string.digits
    
    while True:
        # Generate random alphanumeric string
        random_part = ''.join(random.choices(characters, k=length))
        serial = f"{prefix}{random_part}" if prefix else random_part
        
        # Check uniqueness if model_class provided
        if model_class:
            lookup = {field_name: serial}
            if not model_class.objects.filter(**lookup).exists():
                return serial
        else:
            return serial


def generate_unique_ref(prefix='', length=8, model_class=None, field_name='ref_no'):
    """
    Generate a unique alphanumeric reference number.
    Alias for generate_unique_serial with different default field name.
    """
    return generate_unique_serial(prefix, length, model_class, field_name)


def generate_qr_code(data, filename_prefix='qr'):
    """
    Generate a QR code image and save it to storage.
    
    Args:
        data: Data to encode in QR code (usually serial/ref number)
        filename_prefix: Prefix for the saved file
    
    Returns:
        Path to saved QR code image
    """
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,  # Controls size (1-40, 1 is smallest)
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction
        box_size=10,
        border=4,
    )
    
    # Add data
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to RGB if needed (some QR libraries return P mode)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Save to BytesIO
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Generate filename
    filename = f"qr_codes/{filename_prefix}_{data}.png"
    
    # Save to storage
    path = default_storage.save(filename, ContentFile(buffer.read()))
    
    return path


def regenerate_qr_code(instance, data_field, qr_field='qr_code', prefix='qr'):
    """
    Regenerate QR code for an existing instance.
    
    Args:
        instance: Model instance
        data_field: Field name containing the data to encode
        qr_field: Field name for QR code storage
        prefix: Filename prefix
    """
    data = getattr(instance, data_field)
    
    if not data:
        return None
    
    # Delete old QR code if exists
    old_qr = getattr(instance, qr_field)
    if old_qr and default_storage.exists(old_qr.name):
        default_storage.delete(old_qr.name)
    
    # Generate new QR code
    qr_path = generate_qr_code(data, prefix)
    setattr(instance, qr_field, qr_path)
    instance.save(update_fields=[qr_field])
    
    return qr_path
