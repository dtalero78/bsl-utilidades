"""
Push Notifications Module for Expo Push Notifications
Handles registration and sending of push notifications to iOS/Android devices
"""
import requests
import logging
import json
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Archivo para persistir tokens
TOKENS_FILE = os.path.join(os.path.dirname(__file__), 'push_tokens.json')

def load_tokens() -> Dict[str, Dict[str, str]]:
    """Cargar tokens desde archivo JSON"""
    try:
        if os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error cargando tokens: {e}")
        return {}

def save_tokens():
    """Guardar tokens en archivo JSON"""
    try:
        with open(TOKENS_FILE, 'w') as f:
            json.dump(push_tokens, f, indent=2)
        logger.info(f"✅ Tokens guardados en {TOKENS_FILE}")
    except Exception as e:
        logger.error(f"Error guardando tokens: {e}")

# Cargar tokens al iniciar el módulo
push_tokens: Dict[str, Dict[str, str]] = load_tokens()
logger.info(f"📊 Tokens cargados al iniciar: {len(push_tokens)}")

def register_push_token(token: str, platform: str = 'ios') -> bool:
    """
    Register a push notification token

    Args:
        token: Expo push token (format: ExponentPushToken[...])
        platform: Device platform ('ios' or 'android')

    Returns:
        bool: True if successful
    """
    try:
        # Validate token format
        if not token or not token.startswith('ExponentPushToken['):
            logger.error(f"Invalid Expo push token format: {token}")
            return False

        # Store token
        push_tokens[token] = {
            'platform': platform,
            'registered_at': str(__import__('datetime').datetime.now())
        }

        # ✅ Guardar tokens en archivo para persistencia
        save_tokens()

        logger.info(f"✅ Registered push token: {token[:20]}... (platform: {platform})")
        logger.info(f"📊 Total registered tokens: {len(push_tokens)}")

        return True
    except Exception as e:
        logger.error(f"❌ Error registering push token: {e}")
        return False


def send_push_notification(
    title: str,
    body: str,
    data: Optional[Dict] = None,
    tokens: Optional[List[str]] = None
) -> Dict:
    """
    Send push notifications via Expo Push Notification API

    Args:
        title: Notification title
        body: Notification body text
        data: Optional data payload
        tokens: List of tokens to send to (if None, sends to all registered tokens)

    Returns:
        dict: Response from Expo API with success/failure counts
    """
    try:
        # Use provided tokens or all registered tokens
        target_tokens = tokens if tokens else list(push_tokens.keys())

        if not target_tokens:
            logger.warning("⚠️ No push tokens registered, skipping notification")
            return {'success': 0, 'failure': 0}

        # Prepare messages for Expo Push API
        messages = []
        for token in target_tokens:
            messages.append({
                'to': token,
                'title': title,
                'body': body,
                'data': data or {},
                'sound': 'default',
                'priority': 'high',
                'channelId': 'default',
            })

        # Send to Expo Push API
        expo_api_url = 'https://exp.host/--/api/v2/push/send'
        response = requests.post(expo_api_url, json=messages, timeout=10)
        response.raise_for_status()

        result = response.json()
        logger.info(f"✅ Sent push notifications to {len(target_tokens)} device(s)")
        logger.info(f"📊 Expo API response: {result}")

        # Count successes and failures
        success_count = sum(1 for r in result.get('data', []) if r.get('status') == 'ok')
        failure_count = len(result.get('data', [])) - success_count

        return {
            'success': success_count,
            'failure': failure_count,
            'details': result
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error sending push notifications: {e}")
        return {'success': 0, 'failure': len(target_tokens or []), 'error': str(e)}
    except Exception as e:
        logger.error(f"❌ Unexpected error in send_push_notification: {e}")
        return {'success': 0, 'failure': len(target_tokens or []), 'error': str(e)}


def send_new_message_notification(sender_name: str, message_body: str, conversation_id: str) -> Dict:
    """
    Send a push notification for a new message

    Args:
        sender_name: Name of the message sender
        message_body: Text content of the message
        conversation_id: ID of the conversation (phone number)

    Returns:
        dict: Result from send_push_notification
    """
    title = f"Nuevo mensaje de {sender_name}"
    body = message_body[:100]  # Truncate long messages

    data = {
        'type': 'new_message',
        'conversationId': conversation_id,
        'senderName': sender_name,
    }

    return send_push_notification(title=title, body=body, data=data)


def get_registered_tokens_count() -> int:
    """Get the count of registered push tokens"""
    return len(push_tokens)
