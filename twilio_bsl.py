#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twilio-BSL WhatsApp Integration
Independent endpoint for managing WhatsApp conversations via Twilio
Integrates with Wix CHATBOT collection for message storage and sync
"""

import os
import sys
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import requests
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twilio_bsl.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__,
            static_folder='static/twilio',
            template_folder='templates/twilio')
CORS(app)

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+573153369631')

# Wix API Configuration
WIX_BASE_URL = os.getenv('WIX_BASE_URL', 'https://www.bsl.com.co/_functions')
WIX_API_KEY = os.getenv('WIX_API_KEY', '')

# Initialize Twilio client
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
else:
    twilio_client = None
    logger.warning("Twilio credentials not found. Running in mock mode.")

# ============================================================================
# WIX CHATBOT INTEGRATION
# ============================================================================

def obtener_conversaciones_chatbot():
    """
    Fetch all conversations from Wix CHATBOT collection
    Returns list of conversation objects with messages
    """
    try:
        # Since Wix doesn't expose a "get all conversations" endpoint,
        # we'll need to query based on known patterns or implement this
        # For now, return empty list and implement specific conversation fetch
        logger.info("Fetching conversations from Wix CHATBOT")
        return []
    except Exception as e:
        logger.error(f"Error fetching conversations from Wix: {str(e)}")
        return []

def obtener_conversacion_por_celular(celular):
    """
    Fetch conversation for specific phone number from Wix
    Uses the exposed endpoint from funcionesWix/http.js
    """
    try:
        # Normalize phone number (remove whatsapp: prefix if present)
        celular_clean = celular.replace('whatsapp:', '').replace('+', '').strip()

        url = f"{WIX_BASE_URL}/obtenerConversacion"
        params = {'userId': celular_clean}

        logger.info(f"Fetching conversation for {celular_clean}")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"Conversation data retrieved: {len(data.get('mensajes', []))} messages")
            return data
        else:
            logger.error(f"Error fetching conversation: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error fetching conversation: {str(e)}")
        return None

def guardar_mensaje_en_wix(userId, mensaje_data):
    """
    Save message to Wix CHATBOT collection
    Uses the POST endpoint from funcionesWix/http.js
    """
    try:
        url = f"{WIX_BASE_URL}/guardarConversacion"

        payload = {
            "userId": userId,
            "nombre": mensaje_data.get('nombre', 'Usuario'),
            "mensajes": [mensaje_data.get('mensaje', {})],
            "threadId": mensaje_data.get('threadId', ''),
            "ultimoMensajeBot": mensaje_data.get('ultimoMensajeBot', '')
        }

        logger.info(f"Saving message to Wix for userId: {userId}")
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.info("Message saved successfully to Wix")
            return True
        else:
            logger.error(f"Error saving message: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error saving message to Wix: {str(e)}")
        return False

# ============================================================================
# TWILIO MESSAGE HANDLING
# ============================================================================

def enviar_mensaje_whatsapp(to_number, message_body, media_url=None):
    """
    Send WhatsApp message via Twilio

    Args:
        to_number: Recipient phone number (with or without whatsapp: prefix)
        message_body: Text content of the message
        media_url: Optional media URL for images/documents

    Returns:
        Message SID if successful, None otherwise
    """
    try:
        if not twilio_client:
            logger.error("Twilio client not initialized")
            return None

        # Ensure number has whatsapp: prefix
        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        # Prepare message parameters
        message_params = {
            'from_': TWILIO_WHATSAPP_NUMBER,
            'to': to_number,
            'body': message_body
        }

        # Add media if provided
        if media_url:
            message_params['media_url'] = [media_url]

        # Send message
        message = twilio_client.messages.create(**message_params)

        logger.info(f"Message sent successfully. SID: {message.sid}")

        # Save to Wix
        userId = to_number.replace('whatsapp:', '').replace('+', '')
        mensaje_data = {
            'mensaje': {
                'from': 'sistema',
                'mensaje': message_body,
                'timestamp': datetime.now().isoformat()
            }
        }
        guardar_mensaje_en_wix(userId, mensaje_data)

        return message.sid

    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return None

def obtener_mensajes_recientes(limit=50):
    """
    Fetch recent messages from Twilio for the configured WhatsApp number

    Args:
        limit: Maximum number of messages to retrieve

    Returns:
        List of message objects
    """
    try:
        if not twilio_client:
            logger.error("Twilio client not initialized")
            return []

        messages = twilio_client.messages.list(
            from_=TWILIO_WHATSAPP_NUMBER,
            limit=limit
        )

        # Also get incoming messages
        incoming_messages = twilio_client.messages.list(
            to=TWILIO_WHATSAPP_NUMBER,
            limit=limit
        )

        # Combine and sort by date
        all_messages = list(messages) + list(incoming_messages)
        all_messages.sort(key=lambda x: x.date_sent, reverse=True)

        logger.info(f"Retrieved {len(all_messages)} messages from Twilio")
        return all_messages[:limit]

    except Exception as e:
        logger.error(f"Error fetching messages from Twilio: {str(e)}")
        return []

def agrupar_mensajes_por_conversacion(messages):
    """
    Group messages by conversation (phone number)

    Returns:
        Dictionary with phone numbers as keys and message lists as values
    """
    conversaciones = {}

    for msg in messages:
        # Determine the phone number (from or to, depending on direction)
        if msg.from_ == TWILIO_WHATSAPP_NUMBER:
            numero = msg.to
        else:
            numero = msg.from_

        # Remove whatsapp: prefix for grouping
        numero_clean = numero.replace('whatsapp:', '')

        if numero_clean not in conversaciones:
            conversaciones[numero_clean] = []

        conversaciones[numero_clean].append({
            'sid': msg.sid,
            'from': msg.from_,
            'to': msg.to,
            'body': msg.body,
            'date_sent': msg.date_sent.isoformat() if msg.date_sent else None,
            'status': msg.status,
            'direction': 'outbound' if msg.from_ == TWILIO_WHATSAPP_NUMBER else 'inbound',
            'media': msg.num_media if hasattr(msg, 'num_media') else 0
        })

    # Sort messages within each conversation by date
    for numero in conversaciones:
        conversaciones[numero].sort(key=lambda x: x['date_sent'])

    return conversaciones

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/conversaciones', methods=['GET'])
def get_conversaciones():
    """
    Get all conversations grouped by phone number
    Combines Twilio messages with Wix CHATBOT data
    """
    try:
        # Fetch messages from Twilio
        messages = obtener_mensajes_recientes(limit=100)
        conversaciones = agrupar_mensajes_por_conversacion(messages)

        # Enrich with Wix data
        for numero in conversaciones.keys():
            wix_data = obtener_conversacion_por_celular(numero)
            if wix_data:
                conversaciones[numero] = {
                    'twilio_messages': conversaciones[numero],
                    'wix_data': wix_data,
                    'numero': numero,
                    'nombre': wix_data.get('nombre', 'Usuario'),
                    'stopBot': wix_data.get('stopBot', False),
                    'observaciones': wix_data.get('observaciones', '')
                }

        return jsonify({
            'success': True,
            'conversaciones': conversaciones,
            'total': len(conversaciones)
        })

    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/conversacion/<numero>', methods=['GET'])
def get_conversacion(numero):
    """
    Get specific conversation by phone number
    """
    try:
        # Get Wix data
        wix_data = obtener_conversacion_por_celular(numero)

        # Get Twilio messages
        if twilio_client:
            messages = twilio_client.messages.list(limit=50)
            # Filter for this specific number
            numero_whatsapp = f'whatsapp:+{numero}' if not numero.startswith('whatsapp:') else numero

            conversacion_messages = [
                {
                    'sid': msg.sid,
                    'from': msg.from_,
                    'to': msg.to,
                    'body': msg.body,
                    'date_sent': msg.date_sent.isoformat() if msg.date_sent else None,
                    'status': msg.status,
                    'direction': 'outbound' if msg.from_ == TWILIO_WHATSAPP_NUMBER else 'inbound'
                }
                for msg in messages
                if msg.from_ == numero_whatsapp or msg.to == numero_whatsapp
            ]

            conversacion_messages.sort(key=lambda x: x['date_sent'])
        else:
            conversacion_messages = []

        return jsonify({
            'success': True,
            'numero': numero,
            'wix_data': wix_data,
            'twilio_messages': conversacion_messages
        })

    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/enviar-mensaje', methods=['POST'])
def enviar_mensaje():
    """
    Send WhatsApp message via Twilio

    Expected JSON:
    {
        "to": "+573001234567",
        "message": "Hola, ¿cómo estás?",
        "media_url": "https://..." (optional)
    }
    """
    try:
        data = request.json
        to_number = data.get('to')
        message_body = data.get('message')
        media_url = data.get('media_url')

        if not to_number or not message_body:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: to, message'
            }), 400

        # Send message
        message_sid = enviar_mensaje_whatsapp(to_number, message_body, media_url)

        if message_sid:
            return jsonify({
                'success': True,
                'message_sid': message_sid,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to send message'
            }), 500

    except Exception as e:
        logger.error(f"Error in enviar_mensaje: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/webhook/twilio', methods=['POST'])
def twilio_webhook():
    """
    Webhook endpoint for Twilio incoming messages
    This URL should be configured in Twilio console
    """
    try:
        # Get message data from Twilio
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        body = request.form.get('Body')
        message_sid = request.form.get('MessageSid')
        num_media = int(request.form.get('NumMedia', 0))

        logger.info(f"Incoming message from {from_number}: {body}")

        # Save to Wix
        userId = from_number.replace('whatsapp:', '').replace('+', '')
        mensaje_data = {
            'mensaje': {
                'from': 'usuario',
                'mensaje': body,
                'timestamp': datetime.now().isoformat()
            }
        }
        guardar_mensaje_en_wix(userId, mensaje_data)

        # Create TwiML response (optional auto-reply)
        resp = MessagingResponse()
        # resp.message("Mensaje recibido. Un asesor te atenderá pronto.")

        return str(resp), 200

    except Exception as e:
        logger.error(f"Error in Twilio webhook: {str(e)}")
        return str(MessagingResponse()), 500

# ============================================================================
# WEB INTERFACE
# ============================================================================

@app.route('/')
def index():
    """
    Main chat interface
    """
    return render_template('chat.html')

@app.route('/static/twilio/<path:filename>')
def serve_static(filename):
    """
    Serve static files (CSS, JS, images)
    """
    return send_from_directory(app.static_folder, filename)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'service': 'twilio-bsl',
        'timestamp': datetime.now().isoformat(),
        'twilio_configured': twilio_client is not None
    })

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('TWILIO_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    logger.info(f"Starting Twilio-BSL service on port {port}")
    logger.info(f"Twilio WhatsApp Number: {TWILIO_WHATSAPP_NUMBER}")
    logger.info(f"Wix Base URL: {WIX_BASE_URL}")

    app.run(host='0.0.0.0', port=port, debug=debug)
