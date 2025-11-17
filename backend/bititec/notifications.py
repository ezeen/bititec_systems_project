from exponent_server_sdk import (
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
    PushServerError,
    PushTicketError,
)
from requests.exceptions import ConnectionError, HTTPError
import logging

logger = logging.getLogger(__name__)

def send_push_notification(push_token, title, body, data=None, sound='default', priority='high'):
    """
    Send a push notification to a specific device token
    """
    try:
        response = PushClient().publish(
            PushMessage(
                to=push_token,
                title=title,
                body=body,
                data=data or {},
                sound=sound,
                priority=priority,
                badge=1,  # iOS badge count
            )
        )
        
        # Validate the response
        try:
            response.validate_response()
            logger.info(f"Push notification sent successfully to {push_token[:20]}...")
            return True
        except DeviceNotRegisteredError:
            # Token is invalid, mark device as inactive
            logger.warning(f"Device not registered: {push_token[:20]}...")
            from .models import Device
            Device.objects.filter(push_token=push_token).update(active=False)
            return False
        except PushTicketError as exc:
            logger.error(f"Push ticket error: {exc}")
            return False
            
    except PushServerError as exc:
        logger.error(f"Push server error: {exc}")
        return False
    except (ConnectionError, HTTPError) as exc:
        logger.error(f"Connection error: {exc}")
        return False
    except Exception as exc:
        logger.error(f"Unexpected error sending push notification: {exc}")
        return False

def send_notification_to_users(user_ids, title, body, data=None):
    """
    Send notification to multiple users' active devices
    """
    from .models import Device
    
    devices = Device.objects.filter(
        user_id__in=user_ids,
        active=True
    ).select_related('user')
    
    success_count = 0
    failed_count = 0
    
    for device in devices:
        result = send_push_notification(
            push_token=device.push_token,
            title=title,
            body=body,
            data=data
        )
        
        if result:
            success_count += 1
        else:
            failed_count += 1
    
    logger.info(f"Sent notifications to {success_count} devices, {failed_count} failed")
    return {'success': success_count, 'failed': failed_count}

def send_service_call_notification(service_call, technician_ids):
    """
    Send notification when technicians are assigned to a service call
    """
    title = f"New Service Call: {service_call.ticket_no}"
    
    client_name = (service_call.client.client_name if service_call.client 
                  else service_call.client_name)
    
    body = f"Assigned to {client_name} - {service_call.fault_reported[:50]}..."
    
    data = {
        'type': 'service_call_assigned',
        'call_id': str(service_call.id),
        'ticket_no': service_call.ticket_no,
        'status': service_call.status,
        'client_name': client_name,
        'service_type': service_call.service_type,
    }
    
    return send_notification_to_users(technician_ids, title, body, data)