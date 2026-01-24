"""
Sistema de Chat WhatsApp con Asignación Automática de Conversaciones
=====================================================================

Este módulo maneja el chat de WhatsApp BSL con:
- Autenticación simple de 2 agentes
- Asignación automática round-robin de conversaciones
- Filtrado de conversaciones por agente
- Integración con Twilio y Whapi

Autor: BSL
Fecha: 2026-01-06
"""

from flask import Blueprint, request, jsonify, session, render_template, redirect, send_from_directory
from flask_socketio import emit
from functools import wraps
from datetime import datetime, timezone
import os
import logging
import requests
from requests.exceptions import HTTPError
import uuid
import json as json_module

# Configurar logger
logger = logging.getLogger(__name__)

# ============================================================================
# BLUEPRINT CONFIGURATION
# ============================================================================

chat_bp = Blueprint('chat', __name__, url_prefix='/twilio-chat')

# ============================================================================
# CONFIGURACIÓN TWILIO
# ============================================================================

# Configuración Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+573008021701')
TWILIO_CONTENT_TEMPLATE_SID = os.getenv('TWILIO_CONTENT_TEMPLATE_SID')  # Opcional, para templates
BASE_URL = os.getenv('BASE_URL', 'https://bsl-utilidades-yp78a.ondigitalocean.app')
WIX_BASE_URL = os.getenv('WIX_BASE_URL', 'https://www.bsl.com.co/_functions')

# Número de teléfono de la línea (sin formato whatsapp:)
TWILIO_PHONE_NUMBER = TWILIO_WHATSAPP_FROM.replace('whatsapp:', '').replace('+', '')

# Números excluidos del chat
TWILIO_CHAT_EXCLUDED_NUMBERS_RAW = os.getenv('TWILIO_CHAT_EXCLUDED_NUMBERS', '')
TWILIO_CHAT_EXCLUDED_NUMBERS = set(
    num.strip().replace('+', '').replace(' ', '')
    for num in TWILIO_CHAT_EXCLUDED_NUMBERS_RAW.split(',')
    if num.strip()
)

# ============================================================================
# CONFIGURACIÓN DE AGENTES (NUEVO)
# ============================================================================

AGENTES = {
    'agente1': {
        'password': os.getenv('PASSWORD_AGENTE1', 'password1'),
        'nombre': 'Agente 1',
        'activo': True
    },
    'agente2': {
        'password': os.getenv('PASSWORD_AGENTE2', 'password2'),
        'nombre': 'Agente 2',
        'activo': True
    }
}

# ============================================================================
# INICIALIZAR CLIENTES TWILIO
# ============================================================================

# Intentar importar Twilio
TWILIO_AVAILABLE = False
twilio_client = None

try:
    from twilio.rest import Client
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        TWILIO_AVAILABLE = True
        logger.info("✅ Twilio client initialized successfully")
    else:
        logger.warning("⚠️  Twilio credentials not found - Twilio features disabled")
except ImportError:
    logger.warning("⚠️  Twilio package not installed - Twilio features disabled")
except Exception as e:
    logger.error(f"❌ Error initializing Twilio: {e}")

# Si Twilio no está disponible, mostrar advertencia
if not TWILIO_AVAILABLE:
    logger.warning("⚠️  Twilio not available - WhatsApp features will be disabled")

# ============================================================================
# DECORADORES DE AUTENTICACIÓN (NUEVO)
# ============================================================================

def require_auth(f):
    """
    Decorator para proteger endpoints que requieren autenticación.
    Redirige a /twilio-chat/login si no hay sesión activa.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json or request.path.startswith('/twilio-chat/api/'):
                return jsonify({'success': False, 'error': 'No autenticado'}), 401
            return redirect('/twilio-chat/login')
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# FUNCIONES DE BASE DE DATOS (NUEVO)
# ============================================================================

def obtener_conexion_pg():
    """
    Helper para obtener conexión PostgreSQL reutilizable.
    Usa las mismas variables de entorno que el resto de la aplicación.
    """
    import psycopg2

    postgres_password = os.getenv("POSTGRES_PASSWORD")
    if not postgres_password:
        raise Exception("POSTGRES_PASSWORD no configurada")

    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
        port=int(os.getenv("POSTGRES_PORT", "25060")),
        user=os.getenv("POSTGRES_USER", "doadmin"),
        password=postgres_password,
        database=os.getenv("POSTGRES_DB", "defaultdb"),
        sslmode="require"
    )

def obtener_agente_asignado(numero_telefono):
    """
    Obtiene el agente asignado a un número de teléfono.

    Args:
        numero_telefono (str): Número de teléfono (formato: +57...)

    Returns:
        str or None: Username del agente asignado o None si no existe
    """
    try:
        conn = obtener_conexion_pg()
        cur = conn.cursor()

        cur.execute(
            "SELECT agente_asignado FROM conversaciones_whatsapp WHERE celular = %s",
            (numero_telefono,)
        )
        result = cur.fetchone()

        cur.close()
        conn.close()

        return result[0] if result else None

    except Exception as e:
        logger.error(f"❌ Error obteniendo agente asignado para {numero_telefono}: {e}")
        return None

def asignar_conversacion_round_robin(numero_telefono):
    """
    Asigna una conversación nueva usando algoritmo round-robin.
    Alterna automáticamente entre agentes activos.

    Args:
        numero_telefono (str): Número de teléfono a asignar

    Returns:
        str or None: Username del agente asignado o None si hubo error
    """
    try:
        conn = obtener_conexion_pg()
        cur = conn.cursor()

        # Obtener contador actual (con bloqueo para evitar race conditions)
        cur.execute(
            "SELECT valor FROM sistema_asignacion WHERE clave = 'contador_round_robin' FOR UPDATE"
        )
        result = cur.fetchone()
        contador = result[0] if result else 0

        # Lista de agentes activos
        agentes_activos = [username for username, info in AGENTES.items() if info['activo']]

        if not agentes_activos:
            raise Exception("No hay agentes activos disponibles")

        # Seleccionar agente usando módulo (round-robin)
        agente_asignado = agentes_activos[contador % len(agentes_activos)]

        # Incrementar contador
        nuevo_contador = contador + 1
        cur.execute(
            "UPDATE sistema_asignacion SET valor = %s, updated_at = CURRENT_TIMESTAMP WHERE clave = 'contador_round_robin'",
            (nuevo_contador,)
        )

        # Verificar si la conversación ya existe
        cur.execute(
            "SELECT id FROM conversaciones_whatsapp WHERE celular = %s",
            (numero_telefono,)
        )
        existe = cur.fetchone()

        if existe:
            # Si existe, actualizar agente_asignado
            cur.execute(
                """
                UPDATE conversaciones_whatsapp
                SET agente_asignado = %s,
                    fecha_asignacion = CURRENT_TIMESTAMP,
                    fecha_ultima_actividad = CURRENT_TIMESTAMP
                WHERE celular = %s
                """,
                (agente_asignado, numero_telefono)
            )
        else:
            # Si no existe, insertar nueva conversación
            cur.execute(
                """
                INSERT INTO conversaciones_whatsapp (celular, agente_asignado, estado)
                VALUES (%s, %s, 'activa')
                """,
                (numero_telefono, agente_asignado)
            )

        conn.commit()
        cur.close()
        conn.close()

        logger.info(f"✅ Conversación {numero_telefono} asignada a {agente_asignado} (contador: {nuevo_contador})")

        return agente_asignado

    except Exception as e:
        logger.error(f"❌ Error en asignación round-robin para {numero_telefono}: {e}")
        if 'conn' in locals():
            conn.rollback()
        return None

def actualizar_actividad_conversacion(numero_telefono):
    """
    Actualiza la fecha de última actividad de una conversación.
    Se llama cada vez que llega un mensaje de una conversación existente.

    Args:
        numero_telefono (str): Número de teléfono
    """
    try:
        conn = obtener_conexion_pg()
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE conversaciones_whatsapp
            SET fecha_ultima_actividad = CURRENT_TIMESTAMP
            WHERE celular = %s
            """,
            (numero_telefono,)
        )

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error actualizando actividad para {numero_telefono}: {e}")

def obtener_conversaciones_por_agente(username):
    """
    Obtiene todas las conversaciones asignadas a un agente específico.

    Args:
        username (str): Username del agente

    Returns:
        list: Lista de números de teléfono asignados al agente
    """
    try:
        conn = obtener_conexion_pg()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT celular
            FROM conversaciones_whatsapp
            WHERE agente_asignado = %s
            ORDER BY fecha_ultima_actividad DESC
            """,
            (username,)
        )

        conversaciones = [row[0] for row in cur.fetchall()]

        cur.close()
        conn.close()

        return conversaciones

    except Exception as e:
        logger.error(f"❌ Error obteniendo conversaciones para agente {username}: {e}")
        return []

# ============================================================================
# REQUESTS SESSION CON RETRY
# ============================================================================

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json as json_module

# Crear sesión con retry automático para Whapi
requests_session = requests.Session()
retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]  # method_whitelist deprecado, usar allowed_methods
)
adapter = HTTPAdapter(max_retries=retry_strategy)
requests_session.mount("https://", adapter)
requests_session.mount("http://", adapter)

# ============================================================================
# FUNCIONES HELPER DE WIX
# ============================================================================

def obtener_conversacion_por_celular(celular):
    """Obtiene conversación desde Wix CHATBOT"""
    try:
        celular_clean = celular.replace('whatsapp:', '').replace('+', '').strip()
        url = f"{WIX_BASE_URL}/obtenerConversacion"
        response = requests.get(url, params={'userId': celular_clean}, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error obteniendo conversación: {str(e)}")
        return None

def guardar_mensaje_en_wix(userId, mensaje_data):
    """Guarda mensaje en Wix CHATBOT"""
    try:
        url = f"{WIX_BASE_URL}/guardarConversacion"
        payload = {
            "userId": userId,
            "nombre": mensaje_data.get('nombre', 'Usuario'),
            "mensajes": [mensaje_data.get('mensaje', {})],
            "threadId": mensaje_data.get('threadId', ''),
            "ultimoMensajeBot": mensaje_data.get('ultimoMensajeBot', '')
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error guardando en Wix: {str(e)}")
        return False

def enviar_mensaje_whatsapp(to_number, message_body, media_url=None):
    """Envía mensaje WhatsApp via Twilio - SOLO Twilio, sin Wix"""
    try:
        if not twilio_client:
            logger.error("Cliente Twilio no inicializado")
            return None

        if not to_number.startswith('whatsapp:'):
            to_number = f'whatsapp:{to_number}'

        message_params = {
            'from_': TWILIO_WHATSAPP_NUMBER,
            'to': to_number,
            'body': message_body
        }

        if media_url:
            message_params['media_url'] = [media_url]

        message = twilio_client.messages.create(**message_params)
        logger.info(f"✅ Mensaje enviado via Twilio. SID: {message.sid}")

        return message.sid
    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# ============================================================================
# FUNCIONES HELPER DE TWILIO WHATSAPP
# ============================================================================

def formatear_numero_twilio(to_number):
    """
    Formatea un número al formato requerido por Twilio: whatsapp:+57XXXXXXXXXX
    """
    formatted_number = to_number
    if not formatted_number.startswith('whatsapp:'):
        if not formatted_number.startswith('+'):
            formatted_number = (
                f'+{formatted_number}' if formatted_number.startswith('57')
                else f'+57{formatted_number}'
            )
        formatted_number = f'whatsapp:{formatted_number}'
    return formatted_number

def obtener_conversaciones_twilio():
    """
    Obtiene todas las conversaciones únicas de Twilio WhatsApp.
    Agrupa mensajes por número de teléfono.
    """
    try:
        if not twilio_client:
            logger.error("❌ Cliente Twilio no inicializado")
            return []

        # Obtener mensajes recientes (últimos 7 días)
        from datetime import timedelta
        fecha_desde = datetime.now(timezone.utc) - timedelta(days=7)

        # Obtener mensajes entrantes y salientes
        messages = twilio_client.messages.list(
            from_=TWILIO_WHATSAPP_FROM,
            date_sent_after=fecha_desde,
            limit=500
        )

        messages_to = twilio_client.messages.list(
            to=TWILIO_WHATSAPP_FROM,
            date_sent_after=fecha_desde,
            limit=500
        )

        # Combinar y agrupar por número
        all_messages = messages + messages_to
        conversaciones = {}

        for msg in all_messages:
            # Determinar el número del cliente (no el nuestro)
            if msg.from_ == TWILIO_WHATSAPP_FROM:
                numero = msg.to.replace('whatsapp:', '').replace('+', '')
            else:
                numero = msg.from_.replace('whatsapp:', '').replace('+', '')

            if numero not in conversaciones:
                conversaciones[numero] = {
                    'id': numero,
                    'name': f'Usuario {numero[-4:]}',
                    'last_message': {
                        'timestamp': 0,
                        'body': ''
                    }
                }

            # Actualizar último mensaje si es más reciente
            msg_timestamp = msg.date_sent.timestamp() if msg.date_sent else 0
            if msg_timestamp > conversaciones[numero]['last_message']['timestamp']:
                conversaciones[numero]['last_message'] = {
                    'timestamp': msg_timestamp,
                    'body': msg.body[:50] if msg.body else '(media)',
                    'type': 'text'
                }

        logger.info(f"✅ Obtenidas {len(conversaciones)} conversaciones de Twilio")
        return list(conversaciones.values())

    except Exception as e:
        logger.error(f"❌ Error obteniendo conversaciones de Twilio: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def obtener_mensajes_twilio(numero):
    """
    Obtiene mensajes de un chat específico de Twilio.

    Args:
        numero: Número de teléfono (sin whatsapp: prefix)
    """
    try:
        if not twilio_client:
            logger.error("❌ Cliente Twilio no inicializado")
            return []

        # Formatear número del cliente
        numero_whatsapp = formatear_numero_twilio(numero)

        # Obtener mensajes enviados al cliente
        messages_to = twilio_client.messages.list(
            from_=TWILIO_WHATSAPP_FROM,
            to=numero_whatsapp,
            limit=100
        )

        # Obtener mensajes recibidos del cliente
        messages_from = twilio_client.messages.list(
            from_=numero_whatsapp,
            to=TWILIO_WHATSAPP_FROM,
            limit=100
        )

        # Combinar y ordenar por fecha
        all_messages = messages_to + messages_from
        all_messages.sort(key=lambda x: x.date_sent or datetime.min.replace(tzinfo=timezone.utc))

        logger.info(f"✅ Obtenidos {len(all_messages)} mensajes de Twilio para {numero}")
        return all_messages

    except Exception as e:
        logger.error(f"❌ Error obteniendo mensajes de Twilio: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def formatear_mensaje_twilio(msg, numero):
    """
    Formatea un mensaje de Twilio al formato esperado por el frontend.

    Args:
        msg: Objeto Message de Twilio
        numero: Número del cliente (sin whatsapp:)
    """
    try:
        # Determinar dirección del mensaje
        from_me = msg.from_ == TWILIO_WHATSAPP_FROM

        # Convertir fecha a ISO string
        date_sent = msg.date_sent.isoformat() if msg.date_sent else datetime.now(timezone.utc).isoformat()

        # Extraer contenido
        body = msg.body or ''
        media_url = None
        media_type = None
        media_mime = None

        # Verificar si tiene media
        if msg.num_media and int(msg.num_media) > 0:
            try:
                media_list = msg.media.list()
                if media_list:
                    media_url = media_list[0].uri
                    media_mime = media_list[0].content_type
                    if 'image' in media_mime:
                        media_type = 'image'
                    elif 'video' in media_mime:
                        media_type = 'video'
                    elif 'audio' in media_mime:
                        media_type = 'audio'
                    else:
                        media_type = 'document'
            except Exception as media_error:
                logger.warning(f"⚠️  Error obteniendo media: {media_error}")

        return {
            'id': msg.sid,
            'chat_id': numero,
            'from': TWILIO_PHONE_NUMBER if from_me else numero,
            'to': numero if from_me else TWILIO_PHONE_NUMBER,
            'body': body,
            'date_sent': date_sent,
            'status': msg.status,
            'direction': 'outbound' if from_me else 'inbound',
            'media_count': int(msg.num_media) if msg.num_media else 0,
            'media_url': media_url,
            'media_type': media_type,
            'media_mime': media_mime,
            'source': 'twilio'
        }
    except Exception as e:
        logger.error(f"❌ Error formateando mensaje de Twilio: {str(e)}")
        return None

def enviar_mensaje_twilio(to_number, message_body, media_url=None):
    """
    Envía un mensaje de WhatsApp usando Twilio (texto libre).
    IMPORTANTE: Solo funciona dentro de las 24 horas después de que el cliente envíe un mensaje.

    Args:
        to_number: Número de destino
        message_body: Texto del mensaje
        media_url: URL del archivo multimedia (opcional)

    Returns:
        str: SID del mensaje si fue exitoso, None si hubo error
    """
    try:
        if not twilio_client:
            logger.error("❌ Cliente Twilio no inicializado")
            return None

        # Formatear número
        formatted_number = formatear_numero_twilio(to_number)

        # Preparar parámetros del mensaje
        message_params = {
            'body': message_body,
            'from_': TWILIO_WHATSAPP_FROM,
            'to': formatted_number,
            'status_callback': f'{BASE_URL}/twilio-chat/webhook/twilio/status'
        }

        # Agregar media si existe
        if media_url:
            message_params['media_url'] = [media_url]

        # Enviar mensaje
        message = twilio_client.messages.create(**message_params)

        logger.info(f"✅ Mensaje enviado via Twilio. SID: {message.sid}")
        return message.sid

    except Exception as e:
        logger.error(f"❌ Error enviando mensaje via Twilio: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def enviar_mensaje_twilio_template(to_number, template_sid, variables=None):
    """
    Envía un mensaje de WhatsApp usando Twilio con Content Template.
    Usado para notificaciones automáticas pre-aprobadas (fuera de ventana 24h).

    Args:
        to_number: Número de destino
        template_sid: SID del template (HXxxxxxxxxxx)
        variables: Diccionario con variables del template {"1": "valor1", "2": "valor2"}

    Returns:
        dict: {success, sid, status} o {success: False, error}
    """
    try:
        if not twilio_client:
            logger.error("❌ Cliente Twilio no inicializado")
            return {'success': False, 'error': 'Cliente Twilio no inicializado'}

        # Formatear número
        formatted_number = formatear_numero_twilio(to_number)

        # Preparar parámetros del mensaje
        message_params = {
            'content_sid': template_sid,
            'from_': TWILIO_WHATSAPP_FROM,
            'to': formatted_number,
            'status_callback': f'{BASE_URL}/twilio-chat/webhook/twilio/status'
        }

        # Agregar variables si existen
        if variables:
            message_params['content_variables'] = json_module.dumps(variables)

        # Enviar mensaje
        message = twilio_client.messages.create(**message_params)

        logger.info(f"✅ Template enviado via Twilio. SID: {message.sid}")
        return {'success': True, 'sid': message.sid, 'status': message.status}

    except Exception as e:
        logger.error(f"❌ Error enviando template via Twilio: {str(e)}")
        return {'success': False, 'error': str(e)}

# ============================================================================
# FUNCIÓN HELPER PARA VERIFICAR NÚMEROS EXCLUIDOS
# ============================================================================

def is_numero_excluido(numero):
    """Verifica si un número está en la lista de excluidos"""
    numero_clean = numero.replace('whatsapp:', '').replace('+', '').replace(' ', '').replace('-', '')
    return numero_clean in TWILIO_CHAT_EXCLUDED_NUMBERS

# ============================================================================
# FUNCIONES DE NOTIFICACIONES (WEBSOCKET & PUSH)
# ============================================================================

# Variable global para socketio (se inyecta desde descargar_bsl.py)
_socketio_instance = None

def set_socketio_instance(socketio):
    """Inyecta la instancia de socketio desde la app principal"""
    global _socketio_instance
    _socketio_instance = socketio
    logger.info("✅ Instancia de Socket.IO configurada en chat_whatsapp")

def broadcast_websocket_event(event_type, data):
    """Envía un evento a todos los clientes conectados vía WebSocket"""
    try:
        if _socketio_instance:
            _socketio_instance.emit(event_type, data, namespace='/twilio-chat')
            logger.info(f"📡 Evento WebSocket enviado: {event_type}")
        else:
            logger.warning(f"⚠️ Socket.IO no inicializado, no se pudo enviar evento: {event_type}")
    except Exception as e:
        logger.error(f"❌ Error enviando evento WebSocket: {e}")

def register_push_token(token, platform='ios'):
    """Registra un token de notificaciones push (stub)"""
    # TODO: Implementar almacenamiento de tokens push si se requiere en el futuro
    logger.info(f"📱 Push token registrado: {token[:20]}... (platform: {platform})")
    return True

def send_new_message_notification(sender_name, message_body, conversation_id):
    """Envía notificación push de nuevo mensaje (stub)"""
    # TODO: Implementar envío de push notifications si se requiere en el futuro
    logger.info(f"🔔 Push notification: {sender_name} - {message_body[:30]}...")
    return True

# ============================================================================
# ENDPOINTS DE AUTENTICACIÓN
# ============================================================================

@chat_bp.route('/login', methods=['GET'])
def twilio_login_page():
    """Página de login para agentes"""
    if session.get('logged_in'):
        return redirect('/twilio-chat')
    return render_template('twilio/login.html')

@chat_bp.route('/api/login', methods=['POST'])
def twilio_login():
    """API de login para agentes"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if username in AGENTES and AGENTES[username]['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            session['nombre_agente'] = AGENTES[username]['nombre']
            logger.info(f"✅ Login exitoso: {username}")
            return jsonify({'success': True, 'username': username, 'nombre': AGENTES[username]['nombre']})

        logger.warning(f"❌ Login fallido: {username}")
        return jsonify({'success': False, 'error': 'Credenciales inválidas'}), 401

    except Exception as e:
        logger.error(f"❌ Error en login: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@chat_bp.route('/api/logout', methods=['POST'])
def twilio_logout():
    """Cerrar sesión del agente"""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"✅ Logout: {username}")
    return jsonify({'success': True})

@chat_bp.route('/api/session', methods=['GET'])
def twilio_check_session():
    """Verificar sesión activa"""
    if session.get('logged_in'):
        return jsonify({
            'logged_in': True,
            'username': session.get('username'),
            'nombre': session.get('nombre_agente')
        })
    return jsonify({'logged_in': False}), 401

# ============================================================================
# ENDPOINTS PRINCIPALES DEL CHAT
# ============================================================================

@chat_bp.route('')
@require_auth
def twilio_chat_interface():
    """Interfaz principal del chat WhatsApp"""
    return render_template('twilio/chat.html')

@chat_bp.route('/health')
def twilio_health():
    """Health check del servicio Twilio"""
    return jsonify({
        'status': 'healthy',
        'service': 'twilio-bsl',
        'timestamp': datetime.now().isoformat(),
        'twilio_configured': twilio_client is not None
    })

@chat_bp.route('/debug/db-status')
def twilio_db_status():
    """Diagnóstico del estado de la base de datos"""
    try:
        import psycopg2
        from psycopg2 import sql as psycopg2_sql

        result = {
            'timestamp': datetime.now().isoformat(),
            'env_vars': {},
            'connection': False,
            'tables': [],
            'sql_file_exists': False,
            'sql_file_path': None,
            'errors': []
        }

        # Verificar variables de entorno
        env_vars = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_USER', 'POSTGRES_DB']
        for var in env_vars:
            value = os.getenv(var)
            result['env_vars'][var] = '✅ SET' if value else '❌ NOT SET'
            if var == 'POSTGRES_HOST' and value:
                result['env_vars'][f'{var}_value'] = value

        # Verificar archivo SQL
        sql_path = os.path.join(os.path.dirname(__file__), 'sql', 'init_conversaciones_whatsapp.sql')
        result['sql_file_path'] = sql_path
        result['sql_file_exists'] = os.path.exists(sql_path)

        if result['sql_file_exists']:
            with open(sql_path, 'r', encoding='utf-8') as f:
                content = f.read()
                result['sql_file_size'] = len(content)
                result['sql_has_create_table'] = 'CREATE TABLE' in content

        # Intentar conexión a PostgreSQL
        try:
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST"),
                port=int(os.getenv("POSTGRES_PORT", "25060")),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                database=os.getenv("POSTGRES_DB"),
                sslmode="require"
            )
            result['connection'] = True

            # Verificar tablas existentes
            cur = conn.cursor()
            cur.execute("""
                SELECT table_name,
                       (SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_name = t.table_name AND table_schema = 'public') as column_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                AND table_name IN ('conversaciones_whatsapp', 'sistema_asignacion')
            """)

            for row in cur.fetchall():
                result['tables'].append({
                    'name': row[0],
                    'column_count': row[1]
                })

            # Si existe conversaciones_whatsapp, obtener un ejemplo de registro
            if any(t['name'] == 'conversaciones_whatsapp' for t in result['tables']):
                cur.execute("SELECT COUNT(*) FROM conversaciones_whatsapp")
                count = cur.fetchone()[0]
                result['conversaciones_count'] = count

            cur.close()
            conn.close()

        except Exception as db_error:
            result['errors'].append(f"DB Connection Error: {str(db_error)}")

        # Determinar status general
        if result['connection'] and len(result['tables']) == 2:
            result['status'] = 'healthy'
        elif result['connection'] and len(result['tables']) > 0:
            result['status'] = 'partial'
        elif result['connection']:
            result['status'] = 'connected_no_tables'
        else:
            result['status'] = 'unhealthy'

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@chat_bp.route('/api/conversaciones')
@require_auth
def twilio_get_conversaciones():
    """Obtiene todas las conversaciones - FILTRADAS por agente asignado"""
    try:
        username = session.get('username')

        # Obtener números asignados a este agente
        numeros_asignados = obtener_conversaciones_por_agente(username)
        numeros_set = set(numeros_asignados)

        logger.info(f"📱 Agente {username} tiene {len(numeros_asignados)} conversaciones asignadas")

        # Parámetros de paginación
        limit = request.args.get('limit', default=30, type=int)
        offset = request.args.get('offset', default=0, type=int)

        conversaciones = {}

        # ==================== OBTENER MENSAJES DE WHAPI ====================
        try:
            logger.info("📱 Obteniendo conversaciones de Whapi...")
            chats_whapi = obtener_conversaciones_whapi()
            logger.info(f"✅ Total de chats Whapi obtenidos: {len(chats_whapi)}")

            for chat in chats_whapi:
                chat_id = chat.get('id', '')
                # Limpiar el chat_id para obtener solo el número
                numero_clean = chat_id.replace('@s.whatsapp.net', '').replace('@g.us', '')

                # ========== FILTRO DE ASIGNACIÓN ==========
                # Normalizar número para comparar (SIN el + para que coincida con la BD)
                numero_normalizado = numero_clean.lstrip('+')

                # Solo mostrar conversaciones asignadas a este agente
                if numero_normalizado not in numeros_set:
                    continue
                # ==========================================

                # Saltar números excluidos
                if is_numero_excluido(numero_clean):
                    continue

                # Obtener nombre del contacto
                nombre = chat.get('name', f"Usuario {numero_clean[-4:]}")

                # Obtener foto de perfil de Whapi desde los datos del chat
                foto_perfil = obtener_foto_perfil_whapi(chat)

                if numero_clean not in conversaciones:
                    conversaciones[numero_clean] = {
                        'numero': numero_clean,
                        'nombre': nombre,
                        'messages': [],
                        'last_message_time': None,
                        'last_message_preview': '',
                        'source': 'whapi',
                        'profile_picture': foto_perfil
                    }

                # Obtener último mensaje del chat
                last_msg = chat.get('last_message', {})
                if last_msg:
                    last_msg_time = last_msg.get('timestamp', 0)
                    last_msg_text = last_msg.get('text', {}).get('body', '') if last_msg.get('type') == 'text' else '(media)'

                    # Crear timestamp comparable
                    from datetime import datetime, timezone
                    if isinstance(last_msg_time, int):
                        # Convertir a UTC aware datetime
                        last_msg_datetime = datetime.fromtimestamp(last_msg_time, tz=timezone.utc)
                    else:
                        last_msg_datetime = datetime.now(timezone.utc)

                    # Actualizar último mensaje si es más reciente
                    existing_time = conversaciones[numero_clean]['last_message_time']
                    if existing_time and existing_time.tzinfo is None:
                        existing_time = existing_time.replace(tzinfo=timezone.utc)

                    if not existing_time or last_msg_datetime > existing_time:
                        conversaciones[numero_clean]['last_message_time'] = last_msg_datetime
                        conversaciones[numero_clean]['last_message_preview'] = last_msg_text[:50]

                        # Actualizar actividad en BD
                        actualizar_actividad_conversacion(numero_normalizado)

        except Exception as e:
            logger.error(f"⚠️ Error obteniendo conversaciones de Whapi: {str(e)}")

        # ==================== FORMATEAR RESPUESTA ====================
        # Convertir a lista y ordenar por fecha de último mensaje (más reciente primero)
        conversaciones_lista = []
        for numero, data in conversaciones.items():
            conversaciones_lista.append({
                'numero': numero,
                'nombre': data['nombre'],
                'last_message': data['last_message_preview'],
                'last_message_time': data['last_message_time'].isoformat() if data['last_message_time'] else None,
                'last_message_time_raw': data['last_message_time'],
                'source': data['source'],
                'profile_picture': data.get('profile_picture'),
                'message_count': len(data['messages'])
            })

        # Ordenar por fecha de último mensaje (más reciente primero)
        conversaciones_lista.sort(key=lambda x: x['last_message_time_raw'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        # Aplicar paginación
        total_conversaciones = len(conversaciones_lista)
        conversaciones_paginadas = conversaciones_lista[offset:offset+limit]

        # Convertir lista ordenada a diccionario para mantener compatibilidad con frontend
        conversaciones_formateadas = {}
        for conv in conversaciones_paginadas:
            numero = conv.pop('numero')
            conv.pop('last_message_time_raw')
            conversaciones_formateadas[numero] = conv
            conversaciones_formateadas[numero]['numero'] = numero

        logger.info(f"✅ Conversaciones: {len(conversaciones_formateadas)}/{total_conversaciones} (offset={offset}, limit={limit})")

        return jsonify({
            'success': True,
            'conversaciones': conversaciones_formateadas,
            'total': total_conversaciones,
            'count': len(conversaciones_formateadas),
            'offset': offset,
            'limit': limit,
            'has_more': (offset + limit) < total_conversaciones,
            'agente': username
        })
    except Exception as e:
        logger.error(f"❌ Error obteniendo conversaciones: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@chat_bp.route('/api/conversacion/<numero>')
@require_auth
def twilio_get_conversacion(numero):
    """Obtiene conversación específica - SOLO de la línea 3008021701 (Whapi)"""
    try:
        username = session.get('username')

        # Verificar que el agente tenga permiso para ver esta conversación
        # Normalizar SIN el + para que coincida con la BD
        numero_normalizado = numero.replace('whatsapp:', '').replace('+', '').strip()
        agente_asignado = obtener_agente_asignado(numero_normalizado)

        if agente_asignado != username:
            logger.warning(f"⚠️ Agente {username} intentó acceder a conversación de {agente_asignado}: {numero}")
            return jsonify({'success': False, 'error': 'No tienes permiso para ver esta conversación'}), 403

        # Parámetros de paginación
        limit = request.args.get('limit', default=50, type=int)
        offset = request.args.get('offset', default=0, type=int)

        logger.info(f"📱 Obteniendo conversación para número: {numero} (offset={offset}, limit={limit})")

        conversacion_messages = []

        # ==================== OBTENER MENSAJES DE WHAPI ====================
        try:
            # Construir chat_id para Whapi
            numero_clean = numero.replace('whatsapp:', '').replace('+', '')
            chat_id = f"{numero_clean}@s.whatsapp.net"

            logger.info(f"📱 Buscando mensajes Whapi para: {chat_id}")
            mensajes_whapi = obtener_mensajes_whapi(chat_id)

            for msg in mensajes_whapi:
                mensaje_formateado = formatear_mensaje_whapi(msg, numero_clean)
                if mensaje_formateado:
                    conversacion_messages.append(mensaje_formateado)

            logger.info(f"✅ Mensajes Whapi encontrados: {len([m for m in conversacion_messages if m.get('source') == 'whapi'])}")
        except Exception as e:
            logger.error(f"⚠️ Error obteniendo mensajes de Whapi: {str(e)}")

        # ==================== ORDENAR Y FORMATEAR ====================
        # Ordenar cronológicamente todos los mensajes (más antiguos primero)
        conversacion_messages.sort(key=lambda x: x.get('date_sent', ''))

        # Aplicar paginación (desde el final - mensajes más recientes)
        total_messages = len(conversacion_messages)

        # Calcular índices para paginación inversa
        start_index = max(0, total_messages - offset - limit)
        end_index = total_messages - offset

        mensajes_paginados = conversacion_messages[start_index:end_index]

        logger.info(f"✅ Mensajes: {len(mensajes_paginados)}/{total_messages} (offset={offset}, limit={limit})")

        return jsonify({
            'success': True,
            'numero': numero,
            'twilio_messages': mensajes_paginados,
            'total': total_messages,
            'count': len(mensajes_paginados),
            'offset': offset,
            'limit': limit,
            'has_more': start_index > 0,
            'source': 'whapi'
        })
    except Exception as e:
        logger.error(f"❌ Error obteniendo conversación: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@chat_bp.route('/api/register-push-token', methods=['POST'])
@require_auth
def register_push_token_endpoint():
    """Register Expo push notification token"""
    try:
        data = request.json
        token = data.get('token')
        platform = data.get('platform', 'ios')

        if not token:
            return jsonify({'success': False, 'error': 'Token is required'}), 400

        success = register_push_token(token, platform)

        if success:
            return jsonify({'success': True, 'message': 'Token registered successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to register token'}), 500

    except Exception as e:
        logger.error(f"Error registering push token: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@chat_bp.route('/api/marcar-leido/<numero>', methods=['POST'])
@require_auth
def marcar_conversacion_leida(numero):
    """Marca una conversación como leída"""
    try:
        logger.info(f"📖 Marcando conversación como leída: {numero}")

        # Notificar via WebSocket que la conversación fue marcada como leída
        broadcast_websocket_event('conversation_read', {
            'numero': numero,
            'timestamp': datetime.now().isoformat()
        })

        return jsonify({
            'success': True,
            'message': f'Conversación {numero} marcada como leída'
        })
    except Exception as e:
        logger.error(f"❌ Error marcando conversación como leída: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@chat_bp.route('/api/enviar-mensaje', methods=['POST'])
@require_auth
def twilio_enviar_mensaje():
    """Envía mensaje WhatsApp - Solo via Whapi (línea 3008021701)"""
    try:
        username = session.get('username')
        data = request.json
        to_number = data.get('to')
        message_body = data.get('message')
        media_url = data.get('media_url')

        if not to_number or not message_body:
            return jsonify({
                'success': False,
                'error': 'Faltan campos requeridos: to, message'
            }), 400

        # Verificar que el agente tenga permiso para esta conversación
        # Normalizar número SIN + para que coincida con la BD
        numero_normalizado = to_number.replace('whatsapp:', '').replace('+', '').strip()
        agente_asignado = obtener_agente_asignado(numero_normalizado)

        if agente_asignado != username:
            logger.warning(f"⚠️ Agente {username} intentó enviar mensaje a conversación de {agente_asignado}: {to_number}")
            return jsonify({'success': False, 'error': 'No tienes permiso para enviar mensajes a esta conversación'}), 403

        # Enviar via Whapi (línea 3008021701)
        message_id = enviar_mensaje_whapi(to_number, message_body, media_url)

        if message_id:
            logger.info(f"✅ Mensaje enviado a {to_number} via Whapi por agente {username}. Esperando confirmación de webhook.")

            return jsonify({
                'success': True,
                'message_id': message_id,
                'source': 'whapi',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Error al enviar mensaje via Whapi'
            }), 500
    except Exception as e:
        logger.error(f"❌ Error en enviar_mensaje: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# WEBHOOKS
# ============================================================================

@chat_bp.route('/webhook/whapi', methods=['GET', 'POST'])
def whapi_webhook():
    """Webhook para mensajes entrantes de Whapi - Con asignación automática round-robin"""
    try:
        # Si es GET, responder para validación de Whapi
        if request.method == 'GET':
            return jsonify({'success': True, 'status': 'webhook_ready', 'service': 'whapi'}), 200

        # Whapi envía JSON en lugar de form data
        data = request.get_json()

        logger.info("="*60)
        logger.info("📨 MENSAJE ENTRANTE DE WHAPI")
        logger.info(f"   Payload completo: {json_module.dumps(data, indent=2)}")
        logger.info("="*60)

        # ========== ASIGNACIÓN AUTOMÁTICA ROUND-ROBIN ==========
        messages = data.get('messages', [])

        if messages:
            for msg in messages:
                chat_id = msg.get('chat_id', '')
                from_number = msg.get('from', '')

                # Extraer número limpio (SIN el +, como está en la BD)
                numero_clean = chat_id.replace('@s.whatsapp.net', '').replace('@g.us', '')
                # Remover + si existe para que coincida con la BD
                numero_normalizado = numero_clean.lstrip('+')

                # Verificar asignación existente
                agente = obtener_agente_asignado(numero_normalizado)

                if not agente:
                    # Primera vez - Asignar con round-robin
                    agente = asignar_conversacion_round_robin(numero_normalizado)
                    logger.info(f"🆕 Nueva conversación {numero_normalizado} → {agente}")
                else:
                    # Conversación existente - Actualizar actividad
                    actualizar_actividad_conversacion(numero_normalizado)
                    logger.info(f"📝 Conversación existente {numero_normalizado} → {agente}")
        # ======================================================

        # Extraer información del mensaje de Whapi
        event = data.get('event', {})

        if messages:
            for msg in messages:
                chat_id = msg.get('chat_id', '')
                from_number = msg.get('from', '')
                message_id = msg.get('id', '')
                message_type = msg.get('type', 'text')

                # Extraer el cuerpo del mensaje según el tipo
                if message_type == 'text':
                    body = msg.get('text', {}).get('body', '')
                else:
                    body = f'(media: {message_type})'

                from_me = msg.get('from_me', False)
                timestamp = msg.get('timestamp', 0)

                # Convertir timestamp UNIX a ISO string para frontend
                from datetime import datetime
                if isinstance(timestamp, (int, float)):
                    timestamp_iso = datetime.fromtimestamp(timestamp).isoformat()
                else:
                    timestamp_iso = timestamp

                logger.info("📱 Procesando mensaje de Whapi:")
                logger.info(f"   ID: {message_id}")
                logger.info(f"   Chat ID: {chat_id}")
                logger.info(f"   De: {from_number}")
                logger.info(f"   Tipo: {message_type}")
                logger.info(f"   Mensaje: {body}")
                logger.info(f"   From me: {from_me}")

                # Extraer número limpio
                numero_clean = chat_id.replace('@s.whatsapp.net', '').replace('@g.us', '')

                # Determinar dirección del mensaje
                direction = 'outbound' if from_me else 'inbound'

                # Enviar notificación WebSocket para TODOS los mensajes
                broadcast_websocket_event('new_message', {
                    'numero': numero_clean,
                    'from': WHAPI_PHONE_NUMBER if from_me else from_number,
                    'to': numero_clean if from_me else WHAPI_PHONE_NUMBER,
                    'body': body,
                    'message_id': message_id,
                    'chat_id': chat_id,
                    'type': message_type,
                    'timestamp': timestamp_iso,
                    'direction': direction,
                    'source': 'whapi'
                })

                logger.info(f"✅ Notificación WebSocket enviada para mensaje {direction} de Whapi: {numero_clean}")

                # Solo enviar push notification para mensajes entrantes
                if not from_me:
                    try:
                        send_new_message_notification(
                            sender_name=numero_clean,
                            message_body=body or '(media)',
                            conversation_id=numero_clean
                        )
                    except Exception as push_error:
                        logger.error(f"⚠️ Error enviando push notification: {push_error}")

        return jsonify({'success': True}), 200

    except Exception as e:
        logger.error(f"❌ Error en webhook Whapi: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

def whapi_webhook_statuses():
    """Procesa cambios de estado de mensajes (read receipts, delivery)"""
    try:
        data = request.get_json()

        logger.info("="*60)
        logger.info("📨 EVENTO WHAPI: CAMBIO DE ESTADO DE MENSAJE")
        logger.info(f"   Payload: {json_module.dumps(data, indent=2)}")
        logger.info("="*60)

        statuses = data.get('statuses', [])

        if not statuses:
            return jsonify({'success': True}), 200

        # Procesar cada cambio de estado
        for status_update in statuses:
            message_id = status_update.get('id', '')
            status_code = status_update.get('code', 0)
            status_text = status_update.get('status', '')
            recipient_id = status_update.get('recipient_id', '')
            timestamp = status_update.get('timestamp', 0)

            # Limpiar el recipient_id para obtener el número
            numero_clean = recipient_id.replace('@s.whatsapp.net', '').replace('@g.us', '')

            # Convertir timestamp UNIX a ISO
            from datetime import datetime
            if timestamp:
                timestamp_int = int(timestamp) if isinstance(timestamp, str) else timestamp
                timestamp_iso = datetime.fromtimestamp(timestamp_int).isoformat()
            else:
                timestamp_iso = None

            logger.info("📱 Procesando cambio de estado:")
            logger.info(f"   Mensaje ID: {message_id}")
            logger.info(f"   Estado: {status_text} (code: {status_code})")
            logger.info(f"   Contacto: {numero_clean}")
            logger.info(f"   Timestamp: {timestamp_iso}")

            # Emitir evento WebSocket para actualizar estado de mensaje
            broadcast_websocket_event('message_status', {
                'message_id': message_id,
                'numero': numero_clean,
                'status': status_text,
                'status_code': status_code,
                'timestamp': timestamp_iso,
                'source': 'whapi'
            })

            logger.info(f"✅ WebSocket event 'message_status' enviado para {numero_clean}")

            # Si es un mensaje leído, actualizar la conversación
            if status_text == 'read' or status_code == 4:
                broadcast_websocket_event('conversation_update', {
                    'numero': numero_clean,
                    'last_read_timestamp': timestamp_iso,
                    'event_type': 'message_read',
                    'source': 'whapi'
                })
                logger.info(f"✅ WebSocket event 'conversation_update' enviado (read): {numero_clean}")

        return jsonify({'success': True}), 200

    except Exception as e:
        logger.error(f"❌ Error procesando cambio de estado Whapi: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

def whapi_webhook_chats():
    """Procesa actualizaciones de chat - DESHABILITADO"""
    try:
        logger.info("📨 Webhook de chat recibido (ignorado - funcionalidad deshabilitada)")
        return jsonify({'success': True}), 200

    except Exception as e:
        logger.error(f"❌ Error procesando webhook de chat Whapi: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Rutas adicionales de Whapi (envía eventos a diferentes paths)
@chat_bp.route('/webhook/whapi/messages', methods=['GET', 'POST', 'PATCH'])
@chat_bp.route('/webhook/whapi/statuses', methods=['GET', 'POST'])
@chat_bp.route('/webhook/whapi/chats', methods=['GET', 'POST', 'PATCH'])
def whapi_webhook_events():
    """Webhook para eventos específicos de Whapi"""
    path = request.path

    if 'messages' in path:
        return whapi_webhook()
    elif 'statuses' in path:
        return whapi_webhook_statuses()
    elif 'chats' in path:
        return whapi_webhook_chats()

    return jsonify({'error': 'Unknown event type'}), 400

# Servir archivos estáticos
@chat_bp.route('/static/<path:filename>')
def twilio_static(filename):
    """Servir archivos estáticos CSS/JS para Twilio"""
    from flask import send_from_directory
    return send_from_directory('static/twilio', filename)

# ============================================================================
# FUNCIÓN PARA REGISTRAR SOCKET.IO HANDLERS
# ============================================================================

def register_socketio_handlers(socketio):
    """Registra los handlers de Socket.IO para el namespace /twilio-chat"""

    @socketio.on('connect', namespace='/twilio-chat')
    def handle_connect():
        logger.info(f"✅ Cliente conectado a Socket.IO (namespace: /twilio-chat)")
        emit('connection_status', {'status': 'connected', 'timestamp': datetime.now().isoformat()})

    @socketio.on('disconnect', namespace='/twilio-chat')
    def handle_disconnect():
        logger.info(f"❌ Cliente desconectado de Socket.IO (namespace: /twilio-chat)")

    @socketio.on('join_conversation', namespace='/twilio-chat')
    def handle_join_conversation(data):
        numero = data.get('numero')
        logger.info(f"👤 Cliente se unió a conversación: {numero}")
        emit('joined_conversation', {'numero': numero, 'timestamp': datetime.now().isoformat()})

    logger.info("📡 Socket.IO handlers registrados para /twilio-chat")

logger.info("📦 Chat WhatsApp module loaded - All endpoints OK")
