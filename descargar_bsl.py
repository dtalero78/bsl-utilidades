import os
import requests
import base64
from flask import Flask, request, jsonify, send_file, send_from_directory, redirect, render_template, make_response, Response, stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_compress import Compress
from dotenv import load_dotenv
import traceback
from jinja2 import Template
import uuid
from datetime import datetime, timedelta
import tempfile
import csv
import io
import logging
import subprocess
import json as json_module
import time
import queue
import threading
import locale

# Configurar locale español para fechas
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'es_CO.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')  # Windows
        except locale.Error:
            pass  # Fallback: usar diccionario manual
from do_spaces_uploader import subir_imagen_a_do_spaces
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from push_notifications import register_push_token, send_new_message_notification
from openai import OpenAI

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Diccionario de meses en español (fallback si locale no está disponible)
MESES_ESPANOL = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
    5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
    9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
}

# ===== MAPEO DE NOMBRES DE EXÁMENES (Variantes -> Nombre oficial de tabla examenes en PostgreSQL) =====
# Los nombres normalizados deben coincidir EXACTAMENTE con la tabla "examenes" de PostgreSQL
MAPEO_EXAMENES = {
    # AUDIOMETRÍA
    "Audiometría": "AUDIOMETRÍA",
    "AUDIOMETRÍA": "AUDIOMETRÍA",
    "audiometría": "AUDIOMETRÍA",

    # OPTOMETRÍA
    "Optometría": "OPTOMETRÍA",
    "OPTOMETRÍA": "OPTOMETRÍA",
    "optometría": "OPTOMETRÍA",

    # VISIOMETRÍA
    "Visiometría": "VISIOMETRÍA",
    "VISIOMETRÍA": "VISIOMETRÍA",
    "visiometría": "VISIOMETRÍA",

    # SCL-90
    "SCL-90": "SCL-90",
    "Scl-90": "SCL-90",
    "scl-90": "SCL-90",

    # CUADRO HEMÁTICO
    "Cuadro Hemático": "CUADRO HEMÁTICO",
    "CUADRO HEMÁTICO": "CUADRO HEMÁTICO",

    # EXAMEN MÉDICO OCUPACIONAL / AUDIOMETRÍA / VISIOMETRÍA
    "EXAMEN MÉDICO OCUPACIONAL / AUDIOMETRÍA / VISIOMETRÍA": "EXAMEN MÉDICO OCUPACIONAL / AUDIOMETRÍA / VISIOMETRÍA",
    "Examen Médico Ocupacional / Audiometría / Visiometría": "EXAMEN MÉDICO OCUPACIONAL / AUDIOMETRÍA / VISIOMETRÍA",

    # ELECTROCARDIOGRAMA
    "Electrocardiograma": "ELECTROCARDIOGRAMA",
    "ELECTROCARDIOGRAMA": "ELECTROCARDIOGRAMA",

    # ÉNFASIS CARDIOVASCULAR
    "Énfasis Cardiovascular": "ÉNFASIS CARDIOVASCULAR",
    "É. Cardiovascular": "ÉNFASIS CARDIOVASCULAR",
    "ÉNFASIS CARDIOVASCULAR": "ÉNFASIS CARDIOVASCULAR",

    # ESPIROMETRÍA
    "Espirometría": "ESPIROMETRÍA",
    "ESPIROMETRÍA": "ESPIROMETRÍA",

    # EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR
    "Examen Médico Osteomuscular": "EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR",
    "Examen Médico Ocupacional Osteomuscular": "EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR",
    "EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR": "EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR",

    # OSTEOMUSCULAR
    "Osteomuscular": "OSTEOMUSCULAR",
    "OSTEOMUSCULAR": "OSTEOMUSCULAR",

    # EXAMEN DE ALTURAS
    "Examen de Alturas": "EXAMEN DE ALTURAS",
    "EXAMEN DE ALTURAS": "EXAMEN DE ALTURAS",

    # GLICEMIA
    "Glicemia": "GLICEMIA",
    "GLICEMIA": "GLICEMIA",

    # GLUCOSA EN SANGRE
    "Glucosa en Sangre": "GLUCOSA EN SANGRE",
    "GLUCOSA EN SANGRE": "GLUCOSA EN SANGRE",

    # HEMOGRAMA
    "Hemograma": "HEMOGRAMA",
    "HEMOGRAMA": "HEMOGRAMA",

    # KOH / COPROLÓGICO / FROTIS FARÍNGEO
    "KOH / Coprológico / Frotis Faríngeo": "KOH / COPROLÓGICO / FROTIS FARÍNGEO",
    "KOH / COPROLÓGICO / FROTIS FARÍNGEO": "KOH / COPROLÓGICO / FROTIS FARÍNGEO",

    # MANIPULACIÓN DE ALIMENTOS
    "Manipulación de Alimentos": "MANIPULACIÓN DE ALIMENTOS",
    "MANIPULACIÓN DE ALIMENTOS": "MANIPULACIÓN DE ALIMENTOS",

    # PERFIL LIPÍDICO
    "Perfil Lipídico": "PERFIL LIPÍDICO",
    "PERFIL LIPÍDICO": "PERFIL LIPÍDICO",

    # PANEL DE DROGAS
    "Panel de Drogas": "PANEL DE DROGAS",
    "PANEL DE DROGAS": "PANEL DE DROGAS",

    # PARCIAL DE ORINA
    "Parcial de Orina": "PARCIAL DE ORINA",
    "PARCIAL DE ORINA": "PARCIAL DE ORINA",

    # PERFIL LIPÍDICO COMPLETO
    "Perfil Lipídico Completo": "PERFIL LIPÍDICO COMPLETO",
    "PERFIL LIPÍDICO COMPLETO": "PERFIL LIPÍDICO COMPLETO",

    # ÉNFASIS DERMATOLÓGICO
    "Énfasis Dermatológico": "ÉNFASIS DERMATOLÓGICO",
    "ÉNFASIS DERMATOLÓGICO": "ÉNFASIS DERMATOLÓGICO",

    # ÉNFASIS VASCULAR
    "Énfasis Vascular": "ÉNFASIS VASCULAR",
    "É. VASCULAR": "ÉNFASIS VASCULAR",
    "ÉNFASIS VASCULAR": "ÉNFASIS VASCULAR",

    # PRUEBA PSICOSENSOMÉTRICA
    "Prueba Psicosensométrica": "PRUEBA PSICOSENSOMÉTRICA",
    "PRUEBA PSICOSENSOMÉTRICA": "PRUEBA PSICOSENSOMÉTRICA",
    "Psicosensométrica": "PRUEBA PSICOSENSOMÉTRICA",
    "PSICOSENSOMÉTRICA": "PRUEBA PSICOSENSOMÉTRICA",
    "Prueba Psicosensometrica": "PRUEBA PSICOSENSOMÉTRICA",
    "PRUEBA PSICOSENSOMETRICA": "PRUEBA PSICOSENSOMÉTRICA",

    # PERFIL PSICOLÓGICO ADC
    "Perfil Psicológico ADC": "PERFIL PSICOLÓGICO ADC",
    "PERFIL PSICOLÓGICO ADC": "PERFIL PSICOLÓGICO ADC",
    "Perfil Psicologico ADC": "PERFIL PSICOLÓGICO ADC",
}

def normalizar_examen(nombre_examen):
    """Normaliza el nombre del examen para que funcione con Wix o PostgreSQL"""
    return MAPEO_EXAMENES.get(nombre_examen.strip(), nombre_examen.strip())

def normalizar_lista_examenes(examenes):
    """
    Convierte el campo examenes a lista si viene como string (PostgreSQL).
    En Wix viene como array, en PostgreSQL viene como string separado por comas.

    Args:
        examenes: lista o string de exámenes
    Returns:
        lista de exámenes normalizados
    """
    if examenes is None:
        return []

    # Si es string, convertir a lista separando por comas
    if isinstance(examenes, str):
        if not examenes.strip():
            return []
        # Separar por coma y limpiar espacios
        lista = [e.strip() for e in examenes.split(',') if e.strip()]
        return lista

    # Si ya es lista, retornarla tal cual
    if isinstance(examenes, list):
        return examenes

    return []

def formatear_fecha_espanol(fecha):
    """
    Formatea una fecha en español: '02 de diciembre de 2025'
    Funciona independientemente del locale del sistema.

    Args:
        fecha: objeto datetime o string ISO format
    Returns:
        String con fecha formateada en español
    """
    if isinstance(fecha, str):
        try:
            fecha = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
        except ValueError:
            return fecha  # Retornar original si no se puede parsear

    dia = fecha.day
    mes = MESES_ESPANOL.get(fecha.month, fecha.strftime('%B'))
    anio = fecha.year
    return f"{dia:02d} de {mes} de {anio}"

# Configurar sesión de requests con retry automático
def crear_sesion_con_retry():
    """Crea una sesión de requests con retry automático para mayor resiliencia"""
    session = requests.Session()
    retry = Retry(
        total=3,  # 3 intentos total
        backoff_factor=0.3,  # Espera 0.3s, 0.6s, 1.2s entre intentos
        status_forcelist=[500, 502, 503, 504],  # Retry en errores de servidor
        allowed_methods=["GET", "POST", "PUT", "DELETE"]  # Métodos a reintentar
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Sesión global con retry
requests_session = crear_sesion_con_retry()
logger.info("✅ Sesión de requests configurada con retry automático (3 intentos)")

# Intentar importar Twilio (opcional)
try:
    from twilio.rest import Client as TwilioClient
    from twilio.twiml.messaging_response import MessagingResponse
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    TwilioClient = None
    MessagingResponse = None

load_dotenv(override=True)

app = Flask(__name__, static_folder="static", template_folder="templates")

# Configurar secret key para sesiones
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())

# ============================================================================
# REGISTRAR BLUEPRINT DEL CHAT WHATSAPP
# ============================================================================

from chat_whatsapp import chat_bp, register_socketio_handlers, set_socketio_instance

# Registrar el Blueprint del chat
app.register_blueprint(chat_bp)
logger.info("✅ Blueprint de chat WhatsApp registrado en /twilio-chat")

# Inicializar SocketIO para WebSockets con configuración de keep-alive
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=30,  # Reducido de 60s a 30s para detectar desconexiones iOS más rápido
    ping_interval=25,  # Enviar ping cada 25 segundos
    max_http_buffer_size=1e8,  # 100 MB buffer
    always_connect=True,
    transports=['websocket', 'polling']
)

# Inyectar instancia de socketio al módulo de chat
set_socketio_instance(socketio)

# Registrar Socket.IO handlers del chat
register_socketio_handlers(socketio)

# Inicializar compresión gzip automática
compress = Compress()
compress.init_app(app)
logger.info("✅ Compresión gzip habilitada para respuestas >1KB")

# Configurar CORS para todas las aplicaciones
CORS(app, resources={
    r"/": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"], "methods": ["GET", "OPTIONS"]},
    r"/generar-pdf": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"]},
    r"/subir-pdf-directo": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"]},
    r"/descargar-pdf-drive/*": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"], "methods": ["GET", "OPTIONS"]},
    r"/descargar-pdf-empresas": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"], "methods": ["GET", "POST", "OPTIONS"]},
    r"/generar-certificado-medico": {"origins": "*", "methods": ["POST", "OPTIONS"]},  # Permitir cualquier origen para Wix
    r"/generar-certificado-medico-puppeteer": {"origins": "*", "methods": ["POST", "OPTIONS"]},  # Endpoint con Puppeteer
    r"/generar-certificado-desde-wix-puppeteer/*": {"origins": "*", "methods": ["GET", "OPTIONS"]},  # Endpoint Wix con Puppeteer
    r"/generar-certificado-alegra/*": {"origins": "*", "methods": ["GET", "OPTIONS"]},  # Endpoint Alegra con iLovePDF
    r"/api/generar-certificado-alegra/*": {"origins": "*", "methods": ["GET", "OPTIONS"]},  # API Alegra con iLovePDF
    r"/preview-certificado-alegra/*": {"origins": "*", "methods": ["GET", "OPTIONS"]},  # Preview Alegra con FORMULARIO
    r"/images/*": {"origins": "*", "methods": ["GET", "OPTIONS"]},  # Servir imágenes públicamente
    r"/temp-html/*": {"origins": "*", "methods": ["GET", "OPTIONS"]},  # Servir archivos HTML temporales para Puppeteer
    r"/api/formularios": {"origins": "*", "methods": ["GET", "OPTIONS"]},  # API para obtener formularios
    r"/api/actualizar-formulario": {"origins": "*", "methods": ["POST", "OPTIONS"]},  # API para actualizar formularios
    r"/ver-formularios.html": {"origins": "*", "methods": ["GET", "OPTIONS"]}  # Página para ver y editar formularios
})

# Configuración de carpetas por empresa
EMPRESA_FOLDERS = {
    "BSL": os.getenv("GOOGLE_DRIVE_FOLDER_ID_BSL", os.getenv("GOOGLE_DRIVE_FOLDER_ID")),  # Backward compatibility
    "LGS": os.getenv("GOOGLE_DRIVE_FOLDER_ID_LGS", "1lP8EMIgqZHEVs0JRE6cgXWihx6M7Jxjf"),
    "TTEC": os.getenv("GOOGLE_DRIVE_FOLDER_ID_TTEC", "1PIlvAmv3EUQFy9F3V_YK_QxSJ1-omEDw")
}

# Configuración de dominios, rutas y selectores PDF por empresa
EMPRESA_CONFIG = {
    "BSL": {
        "domain": "https://www.bsl.com.co",
        "path": "/descarga-whp/",
        "query_params": "",
        "pdf_selector": None  # Sin selector, captura toda la página
    },
    "LGS": {
        "domain": "https://www.lgsplataforma.com",
        "path": "/contrato-imprimir/",
        "query_params": "?forReview=",
        "pdf_selector": "#text1"  # Selector del elemento HTML embed que contiene el contrato
    }
}

# Empresas que NO muestran el concepto médico si no han pagado
EMPRESAS_SIN_SOPORTE = [
    "SITEL", "KM2", "TTEC", "CP360", "SALVATECH", "PARTICULAR",
    "STORI", "OMEGA", "EVERTEC", "ZIMMER", "HUNTY", "FDN",
    "SIIGO", "RIPPLING", "RESSOLVE", "CENTRAL", "EVERTECBOGOTA", "ATR",
    "AVANTO", "HEALTHATOM"
]

# Tipos de examen que NUNCA muestran aviso de soporte
TIPOS_EXAMEN_SIN_AVISO = ["PostIncapacidad", "Post Incapacidad", "Periódico"]

# Para compatibilidad con código existente
EMPRESA_DOMAINS = {
    "BSL": EMPRESA_CONFIG["BSL"]["domain"],
    "LGS": EMPRESA_CONFIG["LGS"]["domain"]
}

# Dominios adicionales para plataformas
PLATAFORMA_DOMAINS = {
    "LGS": "https://www.lgsplataforma.com"
}

# --- Token OAuth (si usas Google Drive con OAuth, puedes dejar este bloque) ---
TOKEN_B64 = os.getenv("GOOGLE_OAUTH_TOKEN_B64")
TOKEN_PATH = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token_drive_oauth.pkl")
if TOKEN_B64 and not os.path.exists(TOKEN_PATH):
    with open(TOKEN_PATH, "wb") as f:
        f.write(base64.b64decode(TOKEN_B64))

API2PDF_KEY = os.getenv("API2PDF_KEY")
ILOVEPDF_PUBLIC_KEY = os.getenv("ILOVEPDF_PUBLIC_KEY")
DEST = os.getenv("STORAGE_DESTINATION", "drive")  # drive, drive-oauth, gcs

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("✅ OpenAI client inicializado correctamente")
else:
    logger.warning("⚠️ OPENAI_API_KEY no configurada - las recomendaciones de IA no estarán disponibles")

# --- Importar funciones para almacenamiento externo ---
if DEST == "drive":
    from drive_uploader import subir_pdf_a_drive
elif DEST == "drive-oauth":
    from upload_to_drive_oauth import subir_pdf_a_drive_oauth
elif DEST == "gcs":
    from gcs_uploader import subir_pdf_a_gcs
else:
    raise Exception(f"Destino {DEST} no soportado")

def determinar_empresa(request):
    """Determina la empresa basándose en el origen de la solicitud o parámetro"""
    
    # ✅ PRIORIDAD 1: Verificar si viene como parámetro en el JSON
    if request.content_type == 'application/json':
        try:
            data = request.get_json() or {}
            empresa = data.get('empresa', '').upper()
            if empresa in EMPRESA_FOLDERS:
                print(f"🏢 Empresa detectada del JSON: {empresa}")
                return empresa
        except:
            pass
    
    # ✅ PRIORIDAD 2: Verificar el header Origin
    origin = request.headers.get('Origin', '')
    if 'bsl.com.co' in origin:
        print(f"🏢 Empresa detectada del Origin: BSL")
        return 'BSL'
    elif 'lgs.com.co' in origin or 'lgsplataforma.com' in origin:
        print(f"🏢 Empresa detectada del Origin: LGS")
        return 'LGS'
    
    # ✅ PRIORIDAD 3: Verificar el header Referer como fallback
    referer = request.headers.get('Referer', '')
    if 'bsl.com.co' in referer:
        print(f"🏢 Empresa detectada del Referer: BSL")
        return 'BSL'
    elif 'lgs.com.co' in referer or 'lgsplataforma.com' in referer:
        print(f"🏢 Empresa detectada del Referer: LGS")
        return 'LGS'
    
    # ✅ DEFAULT: BSL para backward compatibility
    print(f"🏢 Empresa por defecto: BSL")
    return 'BSL'

def construir_url_documento(empresa, documento):
    """Construye la URL completa del documento para convertir a PDF"""
    empresa_config = EMPRESA_CONFIG.get(empresa)
    if not empresa_config:
        raise Exception(f"No se encontró configuración para la empresa {empresa}")
        
    domain = empresa_config["domain"]
    path = empresa_config["path"]
    query_params = empresa_config.get("query_params", "")
    
    url_obj = f"{domain}{path}{documento}{query_params}"
    return url_obj

def construir_payload_api2pdf(empresa, url_obj, documento):
    """Construye el payload para API2PDF según la configuración de la empresa"""
    empresa_config = EMPRESA_CONFIG.get(empresa)
    pdf_selector = empresa_config.get("pdf_selector")
    
    # Payload base
    api_payload = {
        "url": url_obj, 
        "inlinePdf": False, 
        "fileName": f"{documento}.pdf"
    }
    
    # Solo agregar opciones de selector si la empresa lo requiere
    if pdf_selector:
        print(f"📄 Usando selector específico para {empresa}: {pdf_selector}")
        api_payload["options"] = {
            "selector": pdf_selector,
            "printBackground": True,
            "delay": 10000,  # Mismo delay que usa Wix
            "scale": 0.75,   # Misma escala que usa Wix
            "format": "A4",
            "margin": {
                "top": "1cm",
                "bottom": "1cm", 
                "left": "1cm",
                "right": "1cm"
            }
        }
    else:
        print(f"📄 Capturando página completa para {empresa}")
    
    return api_payload

# ============== FUNCIONES AUXILIARES ==============

def obtener_datos_formulario_postgres(wix_id):
    """
    Obtiene TODOS los datos del formulario desde PostgreSQL usando el wix_id.

    Args:
        wix_id: ID de Wix del registro de HistoriaClinica

    Returns:
        dict: Diccionario con todos los datos del formulario si existe, None si no existe o hay error
              {
                  'foto': str (data URI),
                  'edad': int,
                  'genero': str,
                  'estadoCivil': str,
                  'hijos': str,
                  'email': str,
                  'profesionUOficio': str,
                  'ciudadDeResidencia': str,
                  'fechaNacimiento': str
              }
    """
    try:
        import psycopg2

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            print("⚠️  POSTGRES_PASSWORD no configurada, no se consultará PostgreSQL")
            return None

        # Conectar a PostgreSQL
        print(f"🔌 [PostgreSQL] Conectando para buscar datos del formulario con wix_id: {wix_id}")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor()

        # Buscar todos los datos del formulario por wix_id
        cur.execute("""
            SELECT
                foto,
                edad,
                genero,
                estado_civil,
                hijos,
                email,
                profesion_oficio,
                ciudad_residencia,
                fecha_nacimiento,
                primer_nombre,
                primer_apellido,
                firma,
                eps,
                arl,
                pensiones,
                nivel_educativo,
                foto_url,
                celular
            FROM formularios
            WHERE wix_id = %s
            LIMIT 1;
        """, (wix_id,))

        row = cur.fetchone()

        # Si no se encontró por wix_id, buscar por numero_id
        if not row:
            print(f"ℹ️  [PostgreSQL] No se encontró por wix_id, buscando numero_id en HistoriaClinica...")

            # Primero obtener el numero_id desde HistoriaClinica
            cur.execute("""
                SELECT "numeroId" FROM "HistoriaClinica" WHERE _id = %s LIMIT 1;
            """, (wix_id,))
            historia_row = cur.fetchone()

            if historia_row and historia_row[0]:
                numero_id = historia_row[0]
                print(f"🔍 [PostgreSQL] Encontrado numero_id: {numero_id}, buscando en formularios...")

                # Buscar en formularios por numero_id (ordenar por fecha para tomar el más reciente)
                cur.execute("""
                    SELECT
                        foto,
                        edad,
                        genero,
                        estado_civil,
                        hijos,
                        email,
                        profesion_oficio,
                        ciudad_residencia,
                        fecha_nacimiento,
                        primer_nombre,
                        primer_apellido,
                        firma,
                        eps,
                        arl,
                        pensiones,
                        nivel_educativo,
                        foto_url,
                        celular
                    FROM formularios
                    WHERE numero_id = %s
                    ORDER BY COALESCE(updated_at, fecha_registro) DESC
                    LIMIT 1;
                """, (numero_id,))
                row = cur.fetchone()

        cur.close()
        conn.close()

        if not row:
            print(f"ℹ️  [PostgreSQL] No se encontró registro con wix_id: {wix_id} ni por numero_id")
            return None

        foto, edad, genero, estado_civil, hijos, email, profesion_oficio, ciudad_residencia, fecha_nacimiento, primer_nombre, primer_apellido, firma, eps, arl, pensiones, nivel_educativo, foto_url, celular = row

        print(f"✅ [PostgreSQL] Datos del formulario encontrados para {primer_nombre} {primer_apellido}")

        # Construir diccionario con los datos
        datos_formulario = {}

        # Foto - Priorizar foto_url (URL pública de DO Spaces) sobre foto (data URI base64)
        if foto_url and foto_url.startswith("http"):
            print(f"📸 [PostgreSQL] Usando foto_url (DO Spaces): {foto_url[:80]}...")
            datos_formulario['foto'] = foto_url
        elif foto and foto.startswith("data:image/"):
            foto_size_kb = len(foto) / 1024
            print(f"📸 [PostgreSQL] Usando foto base64: {foto_size_kb:.1f} KB")
            datos_formulario['foto'] = foto
        else:
            print(f"ℹ️  [PostgreSQL] Sin foto válida")
            datos_formulario['foto'] = None

        # Otros campos
        if edad:
            datos_formulario['edad'] = edad
            print(f"👤 [PostgreSQL] Edad: {edad}")

        if genero:
            datos_formulario['genero'] = genero
            print(f"👤 [PostgreSQL] Género: {genero}")

        if estado_civil:
            datos_formulario['estadoCivil'] = estado_civil
            print(f"👤 [PostgreSQL] Estado civil: {estado_civil}")

        if hijos:
            datos_formulario['hijos'] = hijos
            print(f"👶 [PostgreSQL] Hijos: {hijos}")

        if email:
            datos_formulario['email'] = email
            print(f"📧 [PostgreSQL] Email: {email}")

        if celular:
            datos_formulario['celular'] = celular
            print(f"📞 [PostgreSQL] Teléfono: {celular}")

        if profesion_oficio:
            datos_formulario['profesionUOficio'] = profesion_oficio
            print(f"💼 [PostgreSQL] Profesión: {profesion_oficio}")

        if ciudad_residencia:
            datos_formulario['ciudadDeResidencia'] = ciudad_residencia
            print(f"🏙️  [PostgreSQL] Ciudad: {ciudad_residencia}")

        if fecha_nacimiento:
            # Convertir fecha de nacimiento a formato string legible
            if isinstance(fecha_nacimiento, str):
                try:
                    from datetime import datetime
                    fecha_obj = datetime.fromisoformat(fecha_nacimiento.replace('Z', '+00:00'))
                    datos_formulario['fechaNacimiento'] = formatear_fecha_espanol(fecha_obj)
                except:
                    datos_formulario['fechaNacimiento'] = fecha_nacimiento
            else:
                # Si es un objeto datetime de PostgreSQL
                datos_formulario['fechaNacimiento'] = formatear_fecha_espanol(fecha_nacimiento)
            print(f"🎂 [PostgreSQL] Fecha de nacimiento: {datos_formulario['fechaNacimiento']}")

        # Firma del paciente (validar que sea data URI)
        if firma and firma.startswith("data:image/"):
            firma_size_kb = len(firma) / 1024
            print(f"✍️  [PostgreSQL] Firma encontrada: {firma_size_kb:.1f} KB")
            datos_formulario['firma'] = firma
        else:
            print(f"ℹ️  [PostgreSQL] Sin firma válida")
            datos_formulario['firma'] = None

        # Campos de seguridad social
        if eps:
            datos_formulario['eps'] = eps
            print(f"🏥 [PostgreSQL] EPS: {eps}")

        if arl:
            datos_formulario['arl'] = arl
            print(f"🛡️  [PostgreSQL] ARL: {arl}")

        if pensiones:
            datos_formulario['pensiones'] = pensiones
            print(f"💰 [PostgreSQL] Pensiones: {pensiones}")

        if nivel_educativo:
            datos_formulario['nivelEducativo'] = nivel_educativo
            print(f"🎓 [PostgreSQL] Nivel educativo: {nivel_educativo}")

        return datos_formulario

    except ImportError:
        print("⚠️  [PostgreSQL] psycopg2 no está instalado, no se puede consultar PostgreSQL")
        return None
    except Exception as e:
        print(f"❌ [PostgreSQL] Error al consultar datos del formulario: {e}")
        import traceback
        traceback.print_exc()
        return None


def obtener_foto_desde_postgres(wix_id):
    """
    Función de compatibilidad: Obtiene solo la foto desde PostgreSQL.
    (Wrapper de obtener_datos_formulario_postgres)
    """
    datos = obtener_datos_formulario_postgres(wix_id)
    return datos.get('foto') if datos else None


def obtener_estado_pago_postgres(wix_id):
    """
    Consulta el estado de pago desde PostgreSQL en la tabla HistoriaClinica.

    Args:
        wix_id: ID de Wix del registro (_id en HistoriaClinica)

    Returns:
        dict: {'pagado': bool, 'pvEstado': str, 'fecha_pago': datetime} o None si no existe
    """
    try:
        import psycopg2

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            print("⚠️  [PostgreSQL] POSTGRES_PASSWORD no configurada")
            return None

        print(f"🔌 [PostgreSQL] Consultando estado de pago para wix_id: {wix_id}")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor()

        cur.execute("""
            SELECT pagado, "pvEstado", fecha_pago
            FROM "HistoriaClinica"
            WHERE _id = %s
            LIMIT 1;
        """, (wix_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            print(f"ℹ️  [PostgreSQL] No se encontró registro con wix_id: {wix_id}")
            return None

        pagado, pv_estado, fecha_pago = row

        print(f"💳 [PostgreSQL] Estado de pago encontrado:")
        print(f"   pagado: {pagado}")
        print(f"   pvEstado: '{pv_estado}'")
        print(f"   fecha_pago: {fecha_pago}")

        return {
            'pagado': pagado or False,
            'pvEstado': pv_estado or '',
            'fecha_pago': fecha_pago
        }

    except ImportError:
        print("⚠️  [PostgreSQL] psycopg2 no está instalado")
        return None
    except Exception as e:
        print(f"❌ [PostgreSQL] Error al consultar estado de pago: {e}")
        import traceback
        traceback.print_exc()
        return None


def obtener_datos_historia_clinica_postgres(wix_id):
    """
    Consulta los datos de HistoriaClinica desde PostgreSQL incluyendo exámenes.

    Args:
        wix_id: ID del registro (_id en HistoriaClinica)

    Returns:
        dict: Datos de la historia clínica o None si no existe
    """
    try:
        import psycopg2

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            print("⚠️  [PostgreSQL] POSTGRES_PASSWORD no configurada")
            return None

        print(f"🔌 [PostgreSQL] Consultando HistoriaClinica para wix_id: {wix_id}")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor()

        cur.execute("""
            SELECT
                _id, "numeroId", "primerNombre", "segundoNombre", "primerApellido", "segundoApellido",
                celular, email,
                "codEmpresa", empresa, cargo, "tipoExamen", examenes,
                "mdAntecedentes", "mdObservacionesCertificado", "mdRecomendacionesMedicasAdicionales",
                "mdConceptoFinal", "mdDx1", "mdDx2", talla, peso,
                "fechaAtencion", "fechaConsulta", atendido, "pvEstado", medico, ciudad,
                pagado, fecha_pago
            FROM "HistoriaClinica"
            WHERE _id = %s
            LIMIT 1;
        """, (wix_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            print(f"ℹ️  [PostgreSQL] No se encontró registro en HistoriaClinica con wix_id: {wix_id}")
            return None

        # Mapear columnas a diccionario (solo columnas que existen en la tabla)
        columnas = [
            '_id', 'numeroId', 'primerNombre', 'segundoNombre', 'primerApellido', 'segundoApellido',
            'celular', 'email',
            'codEmpresa', 'empresa', 'cargo', 'tipoExamen', 'examenes',
            'mdAntecedentes', 'mdObservacionesCertificado', 'mdRecomendacionesMedicasAdicionales',
            'mdConceptoFinal', 'mdDx1', 'mdDx2', 'talla', 'peso',
            'fechaAtencion', 'fechaConsulta', 'atendido', 'pvEstado', 'medico', 'ciudad',
            'pagado', 'fecha_pago'
        ]

        datos = {}
        for i, col in enumerate(columnas):
            datos[col] = row[i]

        print(f"✅ [PostgreSQL] Datos de HistoriaClinica encontrados:")
        print(f"   Paciente: {datos.get('primerNombre')} {datos.get('primerApellido')}")
        print(f"   Exámenes: {datos.get('examenes')}")
        print(f"   Pagado: {datos.get('pagado')}, pvEstado: {datos.get('pvEstado')}")

        return datos

    except ImportError:
        print("⚠️  [PostgreSQL] psycopg2 no está instalado")
        return None
    except Exception as e:
        print(f"❌ [PostgreSQL] Error al consultar HistoriaClinica: {e}")
        import traceback
        traceback.print_exc()
        return None


def obtener_visiometria_postgres(orden_id):
    """
    Consulta los datos de visiometría desde PostgreSQL usando el orden_id (wix_id).

    Args:
        orden_id: ID de la orden (_id de HistoriaClinica)

    Returns:
        dict: Datos de visiometría formateados para el template o None si no existe
    """
    try:
        import psycopg2

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            print("⚠️  [PostgreSQL] POSTGRES_PASSWORD no configurada para visiometría")
            return None

        print(f"🔌 [PostgreSQL] Consultando visiometrias_virtual para orden_id: {orden_id}")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor()

        cur.execute("""
            SELECT
                snellen_correctas, snellen_total, snellen_porcentaje,
                landolt_correctas, landolt_total, landolt_porcentaje,
                ishihara_correctas, ishihara_total, ishihara_porcentaje,
                concepto
            FROM visiometrias_virtual
            WHERE orden_id = %s
            LIMIT 1;
        """, (orden_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            print(f"ℹ️  [PostgreSQL] No se encontró visiometría para orden_id: {orden_id}")
            return None

        # Formatear resultado numérico para el template
        snellen_correctas, snellen_total, snellen_porcentaje = row[0], row[1], row[2]
        landolt_correctas, landolt_total, landolt_porcentaje = row[3], row[4], row[5]
        ishihara_correctas, ishihara_total, ishihara_porcentaje = row[6], row[7], row[8]
        concepto = row[9]

        resultado_numerico = f"""Snellen: {snellen_correctas}/{snellen_total} ({snellen_porcentaje}%)
Landolt: {landolt_correctas}/{landolt_total} ({landolt_porcentaje}%)
Ishihara: {ishihara_correctas}/{ishihara_total} ({ishihara_porcentaje}%)"""

        datos_visual = {
            "resultadoNumerico": resultado_numerico,
            "concepto": concepto,
            "snellen": {"correctas": snellen_correctas, "total": snellen_total, "porcentaje": snellen_porcentaje},
            "landolt": {"correctas": landolt_correctas, "total": landolt_total, "porcentaje": landolt_porcentaje},
            "ishihara": {"correctas": ishihara_correctas, "total": ishihara_total, "porcentaje": ishihara_porcentaje}
        }

        print(f"✅ [PostgreSQL] Datos de visiometría virtual encontrados: Snellen {snellen_porcentaje}%, Landolt {landolt_porcentaje}%, Ishihara {ishihara_porcentaje}%")
        return datos_visual

    except ImportError:
        print("⚠️  [PostgreSQL] psycopg2 no está instalado para visiometría")
        return None
    except Exception as e:
        print(f"❌ [PostgreSQL] Error al consultar visiometría virtual: {e}")
        import traceback
        traceback.print_exc()
        return None


def obtener_optometria_postgres(orden_id):
    """
    Consulta los datos de optometría profesional desde PostgreSQL usando el orden_id (wix_id).
    Esta función consulta la tabla 'visiometrias' que tiene datos de exámenes profesionales.

    Args:
        orden_id: ID de la orden (_id de HistoriaClinica)

    Returns:
        dict: Datos de optometría formateados para el template o None si no existe
    """
    try:
        import psycopg2

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            print("⚠️  [PostgreSQL] POSTGRES_PASSWORD no configurada para optometría")
            return None

        print(f"🔌 [PostgreSQL] Consultando tabla visiometrias (optometría) para orden_id: {orden_id}")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor()

        cur.execute("""
            SELECT
                vl_od_sin_correccion, vl_od_con_correccion,
                vl_oi_sin_correccion, vl_oi_con_correccion,
                vl_ao_sin_correccion, vl_ao_con_correccion,
                vc_od_sin_correccion, vc_od_con_correccion,
                vc_oi_sin_correccion, vc_oi_con_correccion,
                vc_ao_sin_correccion, vc_ao_con_correccion,
                ishihara, vision_cromatica,
                diagnostico, observaciones
            FROM visiometrias
            WHERE orden_id = %s
            LIMIT 1;
        """, (orden_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            print(f"ℹ️  [PostgreSQL] No se encontró optometría para orden_id: {orden_id}")
            return None

        # Extraer valores
        vl_od_sc, vl_od_cc = row[0] or '', row[1] or ''
        vl_oi_sc, vl_oi_cc = row[2] or '', row[3] or ''
        vl_ao_sc, vl_ao_cc = row[4] or '', row[5] or ''
        vc_od_sc, vc_od_cc = row[6] or '', row[7] or ''
        vc_oi_sc, vc_oi_cc = row[8] or '', row[9] or ''
        vc_ao_sc, vc_ao_cc = row[10] or '', row[11] or ''
        ishihara = row[12] or ''
        vision_cromatica = row[13] or ''
        diagnostico = row[14] or ''
        observaciones = row[15] or ''

        # Formatear resultado numérico para el template
        resultado_numerico = f"""VISIÓN LEJANA (VL):
  OD: SC {vl_od_sc} / CC {vl_od_cc}
  OI: SC {vl_oi_sc} / CC {vl_oi_cc}
  AO: SC {vl_ao_sc} / CC {vl_ao_cc}

VISIÓN CERCANA (VC):
  OD: SC {vc_od_sc} / CC {vc_od_cc}
  OI: SC {vc_oi_sc} / CC {vc_oi_cc}
  AO: SC {vc_ao_sc} / CC {vc_ao_cc}

Ishihara: {ishihara}
Visión Cromática: {vision_cromatica}

Diagnóstico: {diagnostico}"""

        if observaciones:
            resultado_numerico += f"\nObservaciones: {observaciones}"

        datos_visual = {
            "resultadoNumerico": resultado_numerico,
            "diagnostico": diagnostico,
            "ishihara": ishihara,
            "vision_cromatica": vision_cromatica,
            "tipo": "optometria_profesional"
        }

        print(f"✅ [PostgreSQL] Datos de optometría profesional encontrados: {diagnostico}")
        return datos_visual

    except ImportError:
        print("⚠️  [PostgreSQL] psycopg2 no está instalado para optometría")
        return None
    except Exception as e:
        print(f"❌ [PostgreSQL] Error al consultar optometría: {e}")
        import traceback
        traceback.print_exc()
        return None


def obtener_audiometria_postgres(orden_id):
    """
    Consulta los datos de audiometría desde PostgreSQL usando el orden_id (wix_id).

    Args:
        orden_id: ID de la orden (_id de HistoriaClinica)

    Returns:
        dict: Datos de audiometría formateados para el template o None si no existe
    """
    try:
        import psycopg2

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            print("⚠️  [PostgreSQL] POSTGRES_PASSWORD no configurada para audiometría")
            return None

        print(f"🔌 [PostgreSQL] Consultando audiometrias para orden_id: {orden_id}")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor()

        cur.execute("""
            SELECT
                aereo_od_250, aereo_od_500, aereo_od_1000, aereo_od_2000,
                aereo_od_3000, aereo_od_4000, aereo_od_6000, aereo_od_8000,
                aereo_oi_250, aereo_oi_500, aereo_oi_1000, aereo_oi_2000,
                aereo_oi_3000, aereo_oi_4000, aereo_oi_6000, aereo_oi_8000,
                diagnostico_od, diagnostico_oi, interpretacion, recomendaciones
            FROM audiometrias
            WHERE orden_id = %s
            LIMIT 1;
        """, (orden_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            print(f"ℹ️  [PostgreSQL] No se encontró audiometría para orden_id: {orden_id}")
            return None

        # Extraer valores - convertir None a 0 para los valores numéricos
        def safe_int(val):
            if val is None or val == '':
                return 0
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0

        # Frecuencias para el audiograma (sin 125 Hz en esta tabla)
        frecuencias = [250, 500, 1000, 2000, 3000, 4000, 6000, 8000]

        datosParaTabla = []
        for i, freq in enumerate(frecuencias):
            datosParaTabla.append({
                "frecuencia": freq,
                "oidoDerecho": safe_int(row[i]),      # aereo_od_250 a aereo_od_8000
                "oidoIzquierdo": safe_int(row[i + 8]) # aereo_oi_250 a aereo_oi_8000
            })

        diagnostico_od = row[16] or ''
        diagnostico_oi = row[17] or ''
        interpretacion = row[18] or ''
        recomendaciones = row[19] or ''

        # Función auxiliar para clasificar pérdida auditiva
        def clasificar_perdida(valores_db):
            """Clasifica la pérdida auditiva según promedio de frecuencias"""
            # Calcular promedio de frecuencias conversacionales (500, 1000, 2000, 4000 Hz)
            # Índices: 250(0), 500(1), 1000(2), 2000(3), 3000(4), 4000(5), 6000(6), 8000(7)
            try:
                promedio = (valores_db[1] + valores_db[2] + valores_db[3] + valores_db[5]) / 4
                if promedio <= 25:
                    return "Audición Normal"
                elif promedio <= 40:
                    return "Hipoacusia Leve"
                elif promedio <= 55:
                    return "Hipoacusia Moderada"
                elif promedio <= 70:
                    return "Hipoacusia Moderadamente Severa"
                elif promedio <= 90:
                    return "Hipoacusia Severa"
                else:
                    return "Hipoacusia Profunda"
            except:
                return "Audición Normal"

        # Si no hay diagnóstico manual, generar análisis automático
        if not diagnostico_od and not diagnostico_oi and not interpretacion:
            # Extraer valores OD y OI
            valores_od = [safe_int(row[i]) for i in range(8)]  # aereo_od_250 a aereo_od_8000
            valores_oi = [safe_int(row[i + 8]) for i in range(8)]  # aereo_oi_250 a aereo_oi_8000

            clasificacion_od = clasificar_perdida(valores_od)
            clasificacion_oi = clasificar_perdida(valores_oi)

            diagnostico_od = clasificacion_od
            diagnostico_oi = clasificacion_oi

            # Generar interpretación
            if clasificacion_od == "Audición Normal" and clasificacion_oi == "Audición Normal":
                interpretacion = "Ambos oídos presentan audición dentro de parámetros normales."
            else:
                interpretacion = f"Oído Derecho: {clasificacion_od}. Oído Izquierdo: {clasificacion_oi}."

        # Construir diagnóstico combinado
        diagnostico_partes = []
        if diagnostico_od:
            diagnostico_partes.append(f"OD: {diagnostico_od}")
        if diagnostico_oi:
            diagnostico_partes.append(f"OI: {diagnostico_oi}")
        if interpretacion:
            diagnostico_partes.append(interpretacion)

        diagnostico_final = ". ".join(diagnostico_partes) if diagnostico_partes else "Audiometría realizada"

        datos_audiometria = {
            "datosParaTabla": datosParaTabla,
            "diagnostico": diagnostico_final,
            "diagnostico_od": diagnostico_od,
            "diagnostico_oi": diagnostico_oi,
            "recomendaciones": recomendaciones
        }

        print(f"✅ [PostgreSQL] Datos de audiometría encontrados: OD={diagnostico_od}, OI={diagnostico_oi}")
        return datos_audiometria

    except ImportError:
        print("⚠️  [PostgreSQL] psycopg2 no está instalado para audiometría")
        return None
    except Exception as e:
        print(f"❌ [PostgreSQL] Error al consultar audiometría: {e}")
        import traceback
        traceback.print_exc()
        return None


def descargar_imagen_wix_con_puppeteer(wix_url):
    """
    Descarga una imagen de Wix usando Puppeteer (fallback cuando requests falla con 403)

    Args:
        wix_url: URL de la imagen en Wix CDN

    Returns:
        tuple: (image_bytes, content_type) o (None, None) si falla
    """
    try:
        print(f"🎭 Intentando descargar con Puppeteer: {wix_url}")

        # Obtener directorio del proyecto
        project_dir = os.path.dirname(os.path.abspath(__file__))

        # Crear script de Puppeteer para descargar la imagen
        # NUEVA ESTRATEGIA: Crear página HTML que cargue la imagen como <img>
        # Esto asegura que el evento 'response' capture correctamente el buffer
        puppeteer_script = f"""
const puppeteer = require('{project_dir}/node_modules/puppeteer');
const fs = require('fs');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ]
    }});

    const page = await browser.newPage();

    let imageBuffer = null;
    let contentType = 'image/jpeg';

    try {{
        // Interceptar TODAS las respuestas de imágenes
        page.on('response', async (response) => {{
            const url = response.url();
            const headers = response.headers();
            const ct = headers['content-type'] || '';

            // Solo capturar si es nuestra imagen
            if (url === '{wix_url}' && ct.startsWith('image/')) {{
                try {{
                    imageBuffer = await response.buffer();
                    contentType = ct;
                    console.log('✅ Imagen capturada desde response:', imageBuffer.length, 'bytes, tipo:', contentType);
                }} catch (err) {{
                    console.error('❌ Error capturando buffer:', err.message);
                }}
            }}
        }});

        // Crear página HTML simple que cargue la imagen (SIN crossorigin)
        const html = `
        <!DOCTYPE html>
        <html>
        <head><title>Wix Image Loader</title></head>
        <body>
            <h1>Loading image...</h1>
            <img id="target" style="max-width: 100%;" />
            <script>
                console.log('Setting image src...');
                document.getElementById('target').src = '{wix_url}';
                document.getElementById('target').onload = function() {{
                    console.log('Image loaded! Width:', this.naturalWidth, 'Height:', this.naturalHeight);
                }};
                document.getElementById('target').onerror = function(e) {{
                    console.error('Image load error:', e);
                }};
            </script>
        </body>
        </html>
        `;

        // Cargar HTML con la imagen
        await page.setContent(html, {{ waitUntil: 'domcontentloaded' }});

        // Esperar un poco para que la imagen empiece a cargar
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Esperar a que la imagen se cargue completamente (con más tiempo)
        await page.waitForFunction(
            () => {{
                const img = document.getElementById('target');
                return img && img.complete && img.naturalWidth > 0;
            }},
            {{ timeout: 30000 }}
        );

        console.log('✅ Imagen cargada en DOM');

        await browser.close();

        // Guardar en archivo temporal
        if (imageBuffer && imageBuffer.length > 100) {{
            const tempFile = '/tmp/wix-image-' + Date.now() + '.bin';
            fs.writeFileSync(tempFile, imageBuffer);
            fs.writeFileSync(tempFile + '.type', contentType);
            console.log(tempFile);
        }} else {{
            console.error('❌ No se pudo capturar la imagen o tamaño inválido (', imageBuffer ? imageBuffer.length : 0, 'bytes)');
            process.exit(1);
        }}
    }} catch (err) {{
        console.error('❌ Error descargando imagen:', err.message);
        await browser.close();
        process.exit(1);
    }}
}})();
"""

        # Guardar script en archivo temporal en el directorio actual (para acceder a node_modules)
        script_filename = f"/tmp/puppeteer-download-{uuid.uuid4().hex[:8]}.js"
        with open(script_filename, 'w') as f:
            f.write(puppeteer_script)

        try:
            # Ejecutar script de Puppeteer desde el directorio del proyecto
            project_dir = os.path.dirname(os.path.abspath(__file__))
            result = subprocess.run(
                ['node', script_filename],
                capture_output=True,
                text=True,
                timeout=35,
                cwd=project_dir  # Ejecutar desde el directorio del proyecto
            )

            if result.returncode == 0:
                # Obtener ruta del archivo temporal de la salida
                output_lines = result.stdout.strip().split('\n')
                temp_file = output_lines[-1]  # Última línea contiene la ruta del archivo

                if os.path.exists(temp_file):
                    # Leer imagen
                    with open(temp_file, 'rb') as f:
                        image_bytes = f.read()

                    # Leer content type
                    content_type = 'image/jpeg'
                    if os.path.exists(temp_file + '.type'):
                        with open(temp_file + '.type', 'r') as f:
                            content_type = f.read().strip()

                    # Limpiar archivos temporales
                    os.unlink(temp_file)
                    if os.path.exists(temp_file + '.type'):
                        os.unlink(temp_file + '.type')

                    print(f"✅ Imagen descargada con Puppeteer ({len(image_bytes)} bytes)")
                    return image_bytes, content_type
                else:
                    print(f"❌ Puppeteer no generó archivo temporal")
                    return None, None
            else:
                print(f"❌ Error ejecutando Puppeteer:")
                print(f"   stdout: {result.stdout}")
                print(f"   stderr: {result.stderr}")
                return None, None

        finally:
            # Limpiar script temporal
            if os.path.exists(script_filename):
                os.unlink(script_filename)

    except Exception as e:
        print(f"❌ Error en descarga con Puppeteer: {e}")
        traceback.print_exc()
        return None, None


def descargar_imagen_wix_a_do_spaces(wix_url):
    """
    Descarga una imagen de Wix CDN y la sube a Digital Ocean Spaces

    Estrategia:
    1. Primero intenta descargar con requests usando headers de navegador
    2. Si falla (403), intenta con Puppeteer (puede cargar imágenes con contexto de navegador)
    3. Si funciona, sube a DO Spaces y retorna la URL pública

    Args:
        wix_url: URL de la imagen en Wix CDN (ej: https://static.wixstatic.com/media/...)

    Returns:
        str: URL pública de la imagen en DO Spaces
        None: Si falla la descarga o la subida (usará fallback a Wix URL)
    """
    image_bytes = None
    content_type = 'image/jpeg'

    try:
        print(f"📥 Intentando descargar imagen de Wix: {wix_url}")

        # Headers que emulan un navegador Chrome real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.bsl.com.co/',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'image',
            'sec-fetch-mode': 'no-cors',
            'sec-fetch-site': 'cross-site'
        }

        response = requests.get(wix_url, headers=headers, timeout=10)
        response.raise_for_status()

        image_bytes = response.content
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        print(f"✅ Imagen descargada con requests ({len(image_bytes)} bytes)")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"⚠️  Wix CDN bloqueó requests (403 Forbidden)")
            print(f"   Intentando con Puppeteer...")

            # Intentar con Puppeteer como fallback
            image_bytes, content_type = descargar_imagen_wix_con_puppeteer(wix_url)

            if not image_bytes:
                print(f"❌ Puppeteer también falló. No se puede cachear la imagen.")
                return None
        else:
            print(f"❌ Error HTTP descargando imagen: {e}")
            return None

    except Exception as e:
        print(f"❌ Error descargando imagen de Wix: {e}")
        print(f"   URL: {wix_url}")
        traceback.print_exc()
        return None

    # Si llegamos aquí, tenemos image_bytes (ya sea de requests o Puppeteer)
    if not image_bytes:
        return None

    try:
        # Determinar extensión
        if 'jpeg' in content_type or 'jpg' in content_type:
            ext = 'jpg'
        elif 'png' in content_type:
            ext = 'png'
        elif 'webp' in content_type:
            ext = 'webp'
        else:
            ext = 'jpg'  # Default

        # Generar nombre único para el archivo
        image_id = uuid.uuid4().hex[:12]
        filename = f"wix-img-{image_id}.{ext}"

        # Subir a DO Spaces
        print(f"☁️  Subiendo imagen a DO Spaces...")
        do_spaces_url = subir_imagen_a_do_spaces(image_bytes, filename, content_type)

        if do_spaces_url:
            print(f"✅ Imagen subida a DO Spaces: {do_spaces_url}")
            return do_spaces_url
        else:
            print(f"❌ Error subiendo imagen a DO Spaces")
            return None

    except Exception as e:
        print(f"❌ Error subiendo a DO Spaces: {e}")
        traceback.print_exc()
        return None


def descargar_imagen_wix_localmente(wix_url):
    """
    DEPRECATED: Función antigua que descargaba a static/
    Ahora redirige a descargar_imagen_wix_a_do_spaces()

    Args:
        wix_url: URL de la imagen en Wix CDN

    Returns:
        str: URL pública de la imagen (DO Spaces o Wix directa como fallback)
        None: Si falla completamente
    """
    # Intentar primero con DO Spaces
    do_spaces_url = descargar_imagen_wix_a_do_spaces(wix_url)
    if do_spaces_url:
        return do_spaces_url

    # Fallback: usar URL de Wix directamente (Puppeteer puede cargarla)
    print(f"⚠️  Usando URL de Wix directamente (fallback): {wix_url}")
    return wix_url

# ================================================
# FUNCIONES DE ILOVEPDF PARA PDF (DESCARGAS ALEGRA)
# ================================================

def ilovepdf_get_token():
    """
    Obtiene un token de autenticación de iLovePDF

    Returns:
        str: Token JWT de autenticación

    Raises:
        Exception: Si falla la autenticación
    """
    try:
        response = requests.post(
            'https://api.ilovepdf.com/v1/auth',
            json={'public_key': ILOVEPDF_PUBLIC_KEY}
        )
        response.raise_for_status()
        token = response.json()['token']
        print(f"✅ [iLovePDF] Token de autenticación obtenido")
        return token
    except Exception as e:
        print(f"❌ [iLovePDF] Error obteniendo token: {e}")
        raise


def ilovepdf_html_to_pdf_from_url(html_url, output_filename="certificado"):
    """
    Convierte HTML a PDF usando iLovePDF API desde una URL pública

    Workflow completo de 5 pasos:
    1. Autenticación (obtener token JWT)
    2. Iniciar tarea (start task)
    3. Descargar HTML y subirlo como archivo (no cloud_file para evitar UrlError)
    4. Procesar conversión (process)
    5. Descargar PDF generado (download)

    Args:
        html_url: URL pública del HTML a convertir
        output_filename: Nombre del archivo de salida (sin extensión)

    Returns:
        bytes: Contenido del PDF generado

    Raises:
        Exception: Si falla cualquier paso del proceso
    """
    try:
        # Paso 1: Obtener token
        token = ilovepdf_get_token()
        headers = {'Authorization': f'Bearer {token}'}

        # Paso 2: Iniciar tarea
        print("📄 [iLovePDF] Iniciando tarea HTML→PDF...")
        start_response = requests.get(
            'https://api.ilovepdf.com/v1/start/htmlpdf/eu',
            headers=headers
        )
        start_response.raise_for_status()
        task_data = start_response.json()
        server = task_data['server']
        task_id = task_data['task']
        print(f"✅ [iLovePDF] Tarea iniciada: {task_id} en servidor {server}")

        # Paso 3: Subir HTML usando cloud_file (URL pública)
        print(f"📤 [iLovePDF] Subiendo HTML desde URL: {html_url}")
        upload_response = requests.post(
            f'https://{server}/v1/upload',
            data={
                'task': task_id,
                'cloud_file': html_url
            },
            headers=headers
        )
        upload_response.raise_for_status()
        server_filename = upload_response.json()['server_filename']
        print(f"✅ [iLovePDF] HTML subido: {server_filename}")

        # Paso 4: Procesar
        print("⚙️ [iLovePDF] Procesando HTML→PDF...")
        process_payload = {
            'task': task_id,
            'tool': 'htmlpdf',
            'files': [{
                'server_filename': server_filename,
                'filename': 'document.html'
            }],
            'output_filename': output_filename,
            'single_page': False,  # Permite PDFs de múltiples páginas
            'page_size': 'Letter',  # Tamaño de página estándar
            'page_margin': 20,  # Márgenes en píxeles
            'view_width': 850,  # Ancho del viewport
            'page_orientation': 'portrait'  # Orientación vertical
        }
        process_response = requests.post(
            f'https://{server}/v1/process',
            json=process_payload,
            headers=headers
        )
        process_response.raise_for_status()
        result = process_response.json()
        print(f"✅ [iLovePDF] PDF generado: {result.get('download_filename')} ({result.get('filesize')} bytes)")

        # Paso 5: Descargar
        print("📥 [iLovePDF] Descargando PDF...")
        download_response = requests.get(
            f'https://{server}/v1/download/{task_id}',
            headers=headers
        )
        download_response.raise_for_status()
        pdf_content = download_response.content
        print(f"✅ [iLovePDF] PDF descargado exitosamente ({len(pdf_content)} bytes)")

        return pdf_content

    except Exception as e:
        print(f"❌ [iLovePDF] Error en conversión HTML→PDF: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"❌ [iLovePDF] Respuesta del servidor: {e.response.text}")
        raise

# ================================================
# FUNCIONES DE PUPPETEER PARA PDF
# ================================================

def check_node_available():
    """
    Verifica si Node.js está disponible en el sistema

    Returns:
        bool: True si Node.js está disponible, False si no
    """
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def puppeteer_html_to_pdf_from_url(html_url, output_filename="certificado"):
    """
    Convierte HTML a PDF usando Puppeteer (Node.js) desde una URL pública
    Deja que Puppeteer cargue la URL directamente para que el navegador maneje las imágenes

    Args:
        html_url: URL pública del HTML a convertir
        output_filename: Nombre del archivo de salida (sin extensión)

    Returns:
        bytes: Contenido del PDF generado
    """
    try:
        print("🎭 Iniciando conversión HTML→PDF con Puppeteer...")
        print(f"🔗 URL a convertir: {html_url}")

        # Crear archivo temporal para el PDF de salida
        temp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        temp_pdf_path = temp_pdf.name
        temp_pdf.close()

        print(f"📄 PDF de salida: {temp_pdf_path}")

        # Script de Node.js para ejecutar Puppeteer
        # Carga la URL directamente para que el navegador maneje todas las imágenes
        puppeteer_script = f"""
const puppeteer = require('puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process'
        ]
    }});

    const page = await browser.newPage();

    // Configurar User-Agent real para evitar bloqueos de Wix CDN
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

    // Configurar headers para evitar problemas de CORS
    await page.setExtraHTTPHeaders({{
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': '{html_url}'
    }});

    console.log('🌐 Cargando URL: {html_url}');

    // Cargar la URL directamente - el navegador manejará las imágenes de Wix
    await page.goto('{html_url}', {{
        waitUntil: ['load', 'networkidle0'],
        timeout: 45000
    }});

    console.log('✅ Página cargada, esperando renderizado completo...');

    // 🔍 LOGGING EXPLÍCITO: Mostrar TODAS las URLs de imágenes en la página
    await page.evaluate(() => {{
        const images = Array.from(document.images);
        console.log('');
        console.log('🔍 ========== IMÁGENES ENCONTRADAS EN LA PÁGINA ==========');
        console.log(`🔍 Total de imágenes: ${{images.length}}`);
        images.forEach((img, index) => {{
            console.log(`🔍 Imagen ${{index}}: ${{img.src}}`);
            console.log(`   → Alt: "${{img.alt}}"`);
            console.log(`   → Complete: ${{img.complete}}, Width: ${{img.naturalWidth}}, Height: ${{img.naturalHeight}}`);
        }});
        console.log('🔍 =====================================================');
        console.log('');
    }});

    // Esperar a que todas las imágenes se carguen con timeout más largo
    const imageLoadResult = await page.evaluate(() => {{
        return Promise.all(
            Array.from(document.images).map((img, index) => {{
                return new Promise((resolve) => {{
                    // Si ya está cargada, verificar dimensiones
                    if (img.complete && img.naturalHeight !== 0) {{
                        console.log(`Imagen ${{index}} ya cargada: ${{img.src.substring(0, 60)}}... (${{img.naturalWidth}}x${{img.naturalHeight}})`);
                        resolve({{ loaded: true, src: img.src }});
                        return;
                    }}

                    // Si no está cargada, esperar eventos
                    let resolved = false;

                    const onLoad = () => {{
                        if (!resolved) {{
                            resolved = true;
                            console.log(`Imagen ${{index}} cargada: ${{img.src.substring(0, 60)}}... (${{img.naturalWidth}}x${{img.naturalHeight}})`);
                            resolve({{ loaded: true, src: img.src }});
                        }}
                    }};

                    const onError = () => {{
                        if (!resolved) {{
                            resolved = true;
                            console.log(`⚠️ Error cargando imagen ${{index}}: ${{img.src}}`);
                            resolve({{ loaded: false, src: img.src }});
                        }}
                    }};

                    img.addEventListener('load', onLoad);
                    img.addEventListener('error', onError);

                    // Timeout más largo para imágenes de Wix
                    setTimeout(() => {{
                        if (!resolved) {{
                            resolved = true;
                            if (img.complete && img.naturalHeight !== 0) {{
                                console.log(`Imagen ${{index}} cargada por timeout: ${{img.src.substring(0, 60)}}... (${{img.naturalWidth}}x${{img.naturalHeight}})`);
                                resolve({{ loaded: true, src: img.src }});
                            }} else {{
                                console.log(`⚠️ Timeout imagen ${{index}}: ${{img.src.substring(0, 60)}}...`);
                                resolve({{ loaded: false, src: img.src }});
                            }}
                        }}
                    }}, 10000);  // 10 segundos por imagen
                }});
            }})
        );
    }});

    console.log('🖼️  Imágenes procesadas:', JSON.stringify(imageLoadResult));

    // Forzar repaint del navegador para asegurar que las imágenes se rendericen
    await page.evaluate(() => {{
        // Forzar reflow/repaint
        document.body.style.display = 'none';
        document.body.offsetHeight;  // Trigger reflow
        document.body.style.display = '';

        // Forzar que las imágenes se pinten (convertir HTMLCollection a Array)
        Array.from(document.images).forEach(img => {{
            img.style.visibility = 'hidden';
            img.offsetHeight;  // Trigger reflow
            img.style.visibility = 'visible';
        }});
    }});

    console.log('✅ Repaint forzado completado');

    // Esperar aún más tiempo para asegurar renderizado completo (aumentado a 5 segundos)
    await new Promise(resolve => setTimeout(resolve, 5000));

    // Generar PDF
    console.log('📄 Generando PDF...');
    await page.pdf({{
        path: '{temp_pdf_path}',
        format: 'Letter',
        printBackground: true,
        margin: {{
            top: '0.5cm',
            right: '0.5cm',
            bottom: '0.5cm',
            left: '0.5cm'
        }}
    }});

    await browser.close();
    console.log('✅ PDF generado exitosamente');
}})();
"""

        # Guardar script temporal
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as temp_script:
            temp_script.write(puppeteer_script)
            temp_script_path = temp_script.name

        print(f"🚀 Ejecutando Puppeteer...")

        # Obtener directorio actual del proyecto
        project_dir = os.path.dirname(os.path.abspath(__file__))
        node_modules_path = os.path.join(project_dir, 'node_modules')

        # Configurar variables de entorno para que Node encuentre los módulos
        env = os.environ.copy()
        env['NODE_PATH'] = node_modules_path

        # Ejecutar Node.js con el script (timeout aumentado para espera de imágenes)
        result = subprocess.run(
            ['node', temp_script_path],
            capture_output=True,
            text=True,
            timeout=180,  # 180 segundos para certificados complejos con audiogramas y visiometría
            env=env
        )

        if result.returncode != 0:
            print(f"❌ Error en Puppeteer: {result.stderr}")
            raise Exception(f"Puppeteer falló: {result.stderr}")

        print(f"✅ Puppeteer stdout: {result.stdout}")

        # Leer el PDF generado
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_content = pdf_file.read()

        print(f"✅ PDF generado exitosamente ({len(pdf_content)} bytes)")

        # Limpiar archivos temporales
        try:
            os.unlink(temp_pdf_path)
            os.unlink(temp_script_path)
        except Exception as cleanup_error:
            print(f"⚠️ Error limpiando archivos temporales: {cleanup_error}")

        return pdf_content

    except subprocess.TimeoutExpired:
        print("❌ Timeout ejecutando Puppeteer")
        raise Exception("Timeout en la conversión con Puppeteer")
    except Exception as e:
        print(f"❌ Error en puppeteer_html_to_pdf_from_url: {e}")
        raise

# ================================================
# FUNCIONES DE VALIDACIÓN DE SOPORTE DE PAGO
# ================================================

def debe_colapsar_soporte(datos_wix):
    """
    Determina si se debe ocultar el aviso de soporte (siempre mostrar concepto)

    Returns:
        True si NO se debe mostrar aviso (casos especiales)
    """
    tipo_examen = datos_wix.get('tipoExamen', '')
    cod_empresa = datos_wix.get('codEmpresa', '')

    # Casos donde NUNCA se muestra el aviso (siempre mostrar concepto)
    if tipo_examen in TIPOS_EXAMEN_SIN_AVISO:
        return True

    # Empresas especiales o códigos numéricos de 6+ dígitos
    if es_empresa_especial(cod_empresa):
        return True

    return False

def debe_expandir_soporte(datos_wix):
    """
    Determina si se debe mostrar el aviso de "sin soporte de pago"

    Returns:
        True si se debe mostrar el aviso en lugar del concepto
    """
    pv_estado = datos_wix.get('pvEstado', '')

    # Si NO está pagado, mostrar aviso
    return pv_estado != "Pagado"

def es_empresa_especial(cod_empresa):
    """
    Verifica si es una empresa que no requiere pago
    o si es un código numérico de 6+ dígitos
    """
    if not cod_empresa:
        return False

    # Verificar si está en la lista de empresas especiales
    if cod_empresa in EMPRESAS_SIN_SOPORTE:
        return True

    # Verificar si es código numérico de 6+ dígitos
    import re
    if re.match(r'^\d{6,}$', str(cod_empresa)):
        return True

    return False

def determinar_mostrar_sin_soporte(datos_wix):
    """
    Función principal que determina si mostrar el aviso de sin soporte.
    Verifica TANTO Wix como PostgreSQL para determinar el estado de pago.

    Returns:
        tuple: (mostrar_aviso: bool, texto_aviso: str)
    """
    pv_estado_wix = datos_wix.get('pvEstado', '')
    cod_empresa = datos_wix.get('codEmpresa', '')
    wix_id = datos_wix.get('_id', '')

    print(f"🔍 DEBUG determinar_mostrar_sin_soporte:")
    print(f"   wix_id: '{wix_id}'")
    print(f"   pvEstado (Wix): '{pv_estado_wix}' (tipo: {type(pv_estado_wix).__name__})")
    print(f"   codEmpresa: '{cod_empresa}'")

    # PRIORIDAD 1: Verificar si es empresa especial (siempre mostrar certificado completo)
    es_especial = es_empresa_especial(cod_empresa)
    if es_especial:
        print(f"   ✅ NO mostrar aviso (empresa especial: {cod_empresa})")
        return False, ""

    # PRIORIDAD 2: Verificar estado de pago en Wix
    pagado_wix = pv_estado_wix == "Pagado"
    print(f"   pagado_wix (pvEstado == 'Pagado'): {pagado_wix}")

    # PRIORIDAD 3: Verificar estado de pago en PostgreSQL
    pagado_postgres = False
    if wix_id:
        estado_postgres = obtener_estado_pago_postgres(wix_id)
        if estado_postgres:
            # Considerar pagado si el campo booleano 'pagado' es True
            # O si pvEstado en PostgreSQL es "Pagado"
            pagado_postgres = estado_postgres.get('pagado', False) or estado_postgres.get('pvEstado', '') == "Pagado"
            print(f"   pagado_postgres: {pagado_postgres}")
            print(f"      - campo 'pagado': {estado_postgres.get('pagado', False)}")
            print(f"      - campo 'pvEstado': '{estado_postgres.get('pvEstado', '')}'")
        else:
            print(f"   ⚠️ No se encontró registro en PostgreSQL para wix_id: {wix_id}")

    # Si está pagado en CUALQUIERA de las dos fuentes, no mostrar aviso
    if pagado_wix or pagado_postgres:
        fuente = "Wix" if pagado_wix else "PostgreSQL"
        print(f"   ✅ NO mostrar aviso (pagado en {fuente})")
        return False, ""

    # No está pagado en ninguna fuente, mostrar aviso
    print(f"   ⚠️ MOSTRAR AVISO ROJO (no pagado en Wix ni PostgreSQL)")
    texto = "ESTE CERTIFICADO AÚN NO REGISTRA PAGO. PARA LIBERARLO REMITE EL SOPORTE DE CONSIGNACIÓN"
    return True, texto

# ================================================

def buscar_pdf_en_drive(documento, folder_id):
    """Busca un PDF en Google Drive por nombre de documento"""
    try:
        print(f"🔍 Buscando archivo: {documento}.pdf en folder: {folder_id}")
        
        # Usar las mismas credenciales que para subir
        if DEST == "drive":
            from drive_uploader import service_account, build
            import tempfile
            import base64
            
            # Recrear el servicio usando las mismas credenciales
            base64_str = os.getenv("GOOGLE_CREDENTIALS_BASE64")
            if not base64_str:
                raise Exception("❌ Falta GOOGLE_CREDENTIALS_BASE64 en .env")

            decoded_bytes = base64.b64decode(base64_str)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
            temp_file.write(decoded_bytes)
            temp_file.close()
            
            creds = service_account.Credentials.from_service_account_file(
                temp_file.name,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            service = build('drive', 'v3', credentials=creds)
            
        elif DEST == "drive-oauth":
            from upload_to_drive_oauth import get_authenticated_service
            service = get_authenticated_service()
        else:
            raise Exception("Búsqueda en Drive solo soportada para DEST=drive o drive-oauth")
        
        # Buscar archivos en la carpeta específica
        query = f"parents in '{folder_id}' and name = '{documento}.pdf' and trashed = false"
        
        results = service.files().list(
            q=query,
            fields="files(id, name, webViewLink, webContentLink)"
        ).execute()
        
        files = results.get('files', [])
        
        if files:
            file = files[0]  # Tomar el primer resultado
            print(f"✅ Archivo encontrado: {file['name']}")
            print(f"📎 WebViewLink: {file.get('webViewLink')}")
            print(f"📎 WebContentLink: {file.get('webContentLink')}")
            
            # Retornar el link de descarga directa
            return file.get('webContentLink') or file.get('webViewLink')
        else:
            print(f"❌ No se encontró el archivo {documento}.pdf en el folder {folder_id}")
            return None
            
        # Limpiar archivo temporal si se creó
        if DEST == "drive":
            os.unlink(temp_file.name)
            
    except Exception as e:
        print(f"❌ Error buscando en Drive: {e}")
        return None

def get_allowed_origins():
    """Retorna la lista de orígenes permitidos para CORS"""
    origins = list(EMPRESA_DOMAINS.values())
    # Agregar dominios de plataformas
    origins.extend(PLATAFORMA_DOMAINS.values())
    return origins

# --- Endpoint: GENERAR PDF Y SUBIR A STORAGE ---
@app.route("/generar-pdf", methods=["OPTIONS"])
def options_pdf():
    allowed_origins = get_allowed_origins()
    origin = request.headers.get('Origin')
    
    response_headers = {
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    
    if origin in allowed_origins:
        response_headers["Access-Control-Allow-Origin"] = origin
    
    return ("", 204, response_headers)

@app.route("/generar-pdf", methods=["POST"])
def generar_pdf():
    try:
        print("🔍 Iniciando generar_pdf...")
        
        # Determinar empresa
        empresa = determinar_empresa(request)
        print(f"🏢 Empresa determinada: {empresa}")
        
        folder_id = EMPRESA_FOLDERS.get(empresa)
        print(f"📁 Folder ID inicial: {folder_id}")
        
        if not folder_id:
            raise Exception(f"No se encontró configuración para la empresa {empresa}")
        
        data = request.get_json()
        documento = data.get("documento")
        nombre_archivo = data.get("nombreArchivo")  # Nuevo parámetro para el nombre del archivo
        cod_empresa = data.get("codEmpresa", "").upper()
        tipo_examen = data.get("tipoExamen", "")
        
        print(f"📄 Documento solicitado: {documento}")
        print(f"📝 Nombre archivo: {nombre_archivo}")
        print(f"🏢 Código empresa: {cod_empresa}")
        print(f"🔬 Tipo examen: {tipo_examen}")
        
        # Manejo especial para RIPPLING
        if cod_empresa == "RIPPLING":
            tipo = tipo_examen.strip().lower()
            print(f"🔍 Procesando RIPPLING con tipo: {tipo}")
            
            if tipo == "ingreso":
                folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID_RIPPLING_INGRESO")
                print(f"📁 Usando folder RIPPLING INGRESO: {folder_id}")
            elif tipo == "periódico" or tipo == "periodico":
                folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID_RIPPLING_PERIODICO")
                print(f"📁 Usando folder RIPPLING PERIODICO: {folder_id}")
            else:
                print(f"⚠️ tipoExamen no reconocido para RIPPLING: {tipo_examen}, usando default")
                
        # Manejo especial para TTEC 
        elif cod_empresa == "TTEC":
            print(f"🔍 Procesando TTEC, usando folder específico")
            # Usar el folder específico de TTEC configurado en EMPRESA_FOLDERS
            folder_id = EMPRESA_FOLDERS.get("TTEC")
            if folder_id:
                print(f"📁 Usando folder TTEC: {folder_id}")
            else:
                print(f"⚠️ No se encontró folder para TTEC, usando default de empresa: {empresa}")

        if not documento:
            raise Exception("No se recibió el nombre del documento.")

        # Construir URL usando la nueva función
        print("🔗 Construyendo URL...")
        url_obj = construir_url_documento(empresa, documento)
        print(f"🔗 URL construida: {url_obj}")
        
        # Determinar el nombre final del archivo (usar nombreArchivo si está disponible, sino documento)
        nombre_final = nombre_archivo if nombre_archivo else documento
        print(f"📋 Nombre final del archivo: {nombre_final}")
        
        # Construir payload específico para la empresa
        print("📋 Construyendo payload para API2PDF...")
        api_payload = construir_payload_api2pdf(empresa, url_obj, documento)
        print(f"📋 Payload construido: {api_payload}")
        
        # Llamada a API2PDF
        print("📡 Llamando a API2PDF...")
        api2 = "https://v2018.api2pdf.com/chrome/url"
        res = requests.post(api2, headers={
            "Authorization": API2PDF_KEY,
            "Content-Type": "application/json"
        }, json=api_payload)
        
        print(f"📡 Respuesta API2PDF status: {res.status_code}")
        data = res.json()
        print(f"📡 Respuesta API2PDF data: {data}")
        
        if not data.get("success"):
            raise Exception(data.get("error", "Error API2PDF"))
        pdf_url = data["pdf"]

        # Descargar PDF localmente
        print("💾 Descargando PDF localmente...")
        # Sanitizar el nombre del archivo local para evitar problemas con espacios y caracteres especiales
        nombre_sanitized = nombre_final.replace(" ", "_").replace("/", "_").replace("\\", "_")
        local = f"{empresa}_{nombre_sanitized}.pdf"
        print(f"💾 Archivo local: {local}")
        print(f"💾 Nombre en Drive: {nombre_final}.pdf")
        
        r2 = requests.get(pdf_url)
        with open(local, "wb") as f:
            f.write(r2.content)
        print("💾 PDF descargado correctamente")

        # Subir a almacenamiento según el destino configurado
        print(f"☁️ Subiendo a almacenamiento: {DEST}")
        
        if DEST == "drive":
            print("☁️ Usando drive_uploader...")
            enlace = subir_pdf_a_drive(local, f"{nombre_final}.pdf", folder_id)
        elif DEST == "drive-oauth":
            print("☁️ Usando drive_uploader OAuth...")
            enlace = subir_pdf_a_drive_oauth(local, f"{nombre_final}.pdf", folder_id)
        elif DEST == "gcs":
            print("☁️ Usando GCS...")
            enlace = subir_pdf_a_gcs(local, f"{empresa}/{nombre_final}.pdf")
        else:
            raise Exception(f"Destino {DEST} no soportado")

        print(f"☁️ Archivo subido correctamente: {enlace}")
        
        print("🧹 Limpiando archivo local...")
        os.remove(local)

        # Respuesta con CORS
        response = jsonify({"message": "✅ OK", "url": enlace, "empresa": empresa})
        origin = request.headers.get('Origin')
        if origin in get_allowed_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
        
        print("✅ Proceso completado exitosamente")
        return response

    except Exception as e:
        print(f"❌ Error en generar_pdf: {e}")
        print(f"❌ Tipo de error: {type(e).__name__}")
        print(f"❌ Stack trace completo:")
        traceback.print_exc()
        
        response = jsonify({"error": str(e)})
        origin = request.headers.get('Origin')
        if origin in get_allowed_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
        return response, 500

# --- Endpoint: SUBIR PDF DESDE URL DIRECTO A DRIVE ---
@app.route("/subir-pdf-directo", methods=["OPTIONS"])
def options_subir_pdf_directo():
    allowed_origins = get_allowed_origins()
    origin = request.headers.get('Origin')
    
    response_headers = {
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    
    if origin in allowed_origins:
        response_headers["Access-Control-Allow-Origin"] = origin
    
    return ("", 204, response_headers)

@app.route("/subir-pdf-directo", methods=["POST"])
def subir_pdf_directo():
    try:
        print("🔄 Iniciando subida de PDF desde URL...")
        
        # Obtener datos del request
        data = request.get_json()
        pdf_url = data.get("pdfUrl")
        documento = data.get("documento")
        empresa = data.get("empresa", "LGS").upper()
        
        print(f"📄 PDF URL recibida: {pdf_url}")
        print(f"📋 Documento: {documento}")
        print(f"🏢 Empresa: {empresa}")
        
        if not pdf_url or not documento:
            raise Exception("Faltan parámetros: pdfUrl y documento son requeridos")
        
        # Obtener folder_id para la empresa
        folder_id = EMPRESA_FOLDERS.get(empresa)
        if not folder_id:
            raise Exception(f"No se encontró configuración para la empresa {empresa}")
        
        print(f"📁 Folder ID: {folder_id}")
        
        # Descargar PDF desde la URL
        print("💾 Descargando PDF desde URL...")
        # Sanitizar el nombre del archivo local para evitar problemas con espacios y caracteres especiales
        documento_sanitized = documento.replace(" ", "_").replace("/", "_").replace("\\", "_")
        local = f"{empresa}_{documento_sanitized}_directo.pdf"
        
        pdf_response = requests.get(pdf_url)
        if pdf_response.status_code != 200:
            raise Exception(f"Error descargando PDF: {pdf_response.status_code}")
        
        with open(local, "wb") as f:
            f.write(pdf_response.content)
        print(f"💾 PDF descargado como: {local}")

        # Subir a almacenamiento según el destino configurado
        print(f"☁️ Subiendo a almacenamiento: {DEST}")
        
        if DEST == "drive":
            print("☁️ Usando drive_uploader...")
            enlace = subir_pdf_a_drive(local, f"{documento}.pdf", folder_id)
        elif DEST == "drive-oauth":
            print("☁️ Usando drive_uploader OAuth...")
            enlace = subir_pdf_a_drive_oauth(local, f"{documento}.pdf", folder_id)
        elif DEST == "gcs":
            print("☁️ Usando GCS...")
            enlace = subir_pdf_a_gcs(local, f"{empresa}/{documento}.pdf")
        else:
            raise Exception(f"Destino {DEST} no soportado")

        print(f"☁️ Archivo subido correctamente: {enlace}")
        
        # Limpiar archivo local
        print("🧹 Limpiando archivo local...")
        os.remove(local)

        # Respuesta con CORS
        response = jsonify({"message": "✅ PDF subido exitosamente", "url": enlace, "empresa": empresa})
        origin = request.headers.get('Origin')
        if origin in get_allowed_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
        
        print("✅ Proceso de subida directa completado exitosamente")
        return response

    except Exception as e:
        print(f"❌ Error en subir_pdf_directo: {e}")
        print(f"❌ Stack trace completo:")
        traceback.print_exc()
        
        response = jsonify({"error": str(e)})
        origin = request.headers.get('Origin')
        if origin in get_allowed_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
        return response, 500

# --- Endpoint: GENERAR Y DESCARGAR PDF DIRECTO ---
@app.route("/descargar-pdf-empresas", methods=["OPTIONS"])
def options_descargar_pdf_empresas():
    allowed_origins = get_allowed_origins()
    origin = request.headers.get('Origin')
    
    response_headers = {
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    
    if origin in allowed_origins:
        response_headers["Access-Control-Allow-Origin"] = origin
    
    return ("", 204, response_headers)

@app.route("/descargar-pdf-empresas", methods=["GET", "POST"])
def descargar_pdf_empresas():
    try:
        # Manejar tanto GET como POST
        if request.method == "GET":
            documento = request.args.get("documento")
            empresa = request.args.get("empresa", "BSL").upper()
        else:  # POST
            documento = request.json.get("documento")
            empresa = determinar_empresa(request)
        
        if not documento:
            error_msg = "No se recibió el nombre del documento."
            if request.method == "GET":
                return jsonify({"error": error_msg}), 400
            else:
                raise Exception(error_msg)

        # Construir URL usando la nueva función
        print("🔗 Construyendo URL para descarga...")
        url_obj = construir_url_documento(empresa, documento)
        print(f"🔗 URL construida para descarga: {url_obj}")
        
        # Construir payload específico para la empresa
        print("📋 Construyendo payload para descarga...")
        api_payload = construir_payload_api2pdf(empresa, url_obj, documento)
        print(f"📋 Payload para descarga: {api_payload}")
        
        # Llamada a API2PDF
        print("📡 Llamando a API2PDF para descarga...")
        api2 = "https://v2018.api2pdf.com/chrome/url"
        res = requests.post(api2, headers={
            "Authorization": API2PDF_KEY,
            "Content-Type": "application/json"
        }, json=api_payload)
        
        print(f"📡 Respuesta API2PDF para descarga - status: {res.status_code}")
        data = res.json()
        
        if not data.get("success"):
            error_msg = data.get("error", "Error API2PDF")
            if request.method == "GET":
                return jsonify({"error": error_msg}), 500
            else:
                raise Exception(error_msg)
        
        pdf_url = data["pdf"]

        # Descargar PDF localmente
        print("💾 Descargando PDF para envío directo...")
        # Sanitizar el nombre del archivo local para evitar problemas con espacios y caracteres especiales
        documento_sanitized = documento.replace(" ", "_").replace("/", "_").replace("\\", "_")
        local = f"{empresa}_{documento_sanitized}.pdf"
        r2 = requests.get(pdf_url)
        with open(local, "wb") as f:
            f.write(r2.content)

        response = send_file(
            local,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{documento}.pdf"
        )
        
        # Configurar CORS
        origin = request.headers.get('Origin')
        if origin in get_allowed_origins():
            response.headers["Access-Control-Allow-Origin"] = origin

        @response.call_on_close
        def cleanup():
            try:
                os.remove(local)
            except Exception:
                pass

        return response

    except Exception as e:
        print("❌", e)
        resp = jsonify({"error": str(e)})
        origin = request.headers.get('Origin')
        if origin in get_allowed_origins():
            resp.headers["Access-Control-Allow-Origin"] = origin
        return resp, 500

# --- Endpoint: DESCARGAR PDF DESDE GOOGLE DRIVE ---
@app.route("/descargar-pdf-drive/<documento>", methods=["GET", "OPTIONS"])
def descargar_pdf_drive(documento):
    if request.method == "OPTIONS":
        allowed_origins = get_allowed_origins()
        origin = request.headers.get('Origin')
        
        response_headers = {
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        
        if origin in allowed_origins:
            response_headers["Access-Control-Allow-Origin"] = origin
        
        return ("", 204, response_headers)
    
    try:
        # Determinar empresa desde parámetros o headers
        empresa = request.args.get("empresa", "LGS").upper()
        print(f"🔍 Buscando PDF para documento: {documento}, empresa: {empresa}")
        
        # Obtener folder_id para la empresa
        folder_id = EMPRESA_FOLDERS.get(empresa)
        if not folder_id:
            return jsonify({"error": f"No se encontró configuración para la empresa {empresa}"}), 400
        
        print(f"📁 Buscando en folder: {folder_id}")
        
        # Buscar el archivo en Google Drive
        pdf_url = buscar_pdf_en_drive(documento, folder_id)
        
        if pdf_url:
            print(f"✅ PDF encontrado, redirigiendo a: {pdf_url}")
            # Redirigir directamente al PDF en Google Drive
            response = redirect(pdf_url)
            
            # Configurar CORS si es necesario
            origin = request.headers.get('Origin')
            if origin in get_allowed_origins():
                response.headers["Access-Control-Allow-Origin"] = origin
            
            return response
        else:
            print(f"❌ PDF no encontrado para documento: {documento}")
            return jsonify({"error": f"PDF no encontrado para el documento {documento}"}), 404
            
    except Exception as e:
        print(f"❌ Error buscando PDF: {e}")
        return jsonify({"error": str(e)}), 500

# --- Servir el FRONTEND estático ---
@app.route("/", methods=["OPTIONS"])
def options_root():
    allowed_origins = get_allowed_origins()
    origin = request.headers.get('Origin')
    
    response_headers = {
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    
    if origin in allowed_origins:
        response_headers["Access-Control-Allow-Origin"] = origin
    
    return ("", 204, response_headers)

@app.route("/")
def serve_frontend():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/menu")
def serve_menu():
    """Ruta para el menú principal de utilidades"""
    return send_from_directory(app.static_folder, "menu.html")

@app.route("/estadisticas-bsl")
def estadisticas_bsl():
    """Ruta para el calendario de estadísticas de consultas BSL"""
    return send_from_directory(app.static_folder, "estadisticas-bsl.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# --- Endpoint: GENERAR CERTIFICADO MÉDICO DESDE WIX ---
@app.route("/generar-certificado-medico", methods=["OPTIONS"])
def options_certificado():
    response_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization"
    }
    return ("", 204, response_headers)

@app.route("/generar-certificado-medico", methods=["POST"])
def generar_certificado_medico():
    try:
        print("📋 Iniciando generación de certificado médico...")

        # Obtener datos del request
        data = request.get_json()
        print(f"📝 Datos recibidos: {data}")

        # Generar código de seguridad único
        codigo_seguridad = str(uuid.uuid4())

        # Preparar datos con valores por defecto
        fecha_actual = datetime.now()

        # Logo BSL embebido como base64 (recreado basado en el logo real)
        logo_bsl_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAASwAAABkCAYAAAA8AQ3AAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAKKUlEQVR4nO2dW6hdRRiAf21ttbW2trZaW1tb29ra2tra2traaq2trdbaWluttba2ttbWWmtrrbW1tdbW2lqttbXW1lpra62ttbXWWmtrrbVaX2f/M2tmzzl7n5kzc2bWzNrfB4czOXuvNbP+b2b+mfnPrFkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwDDYXFJXSf1a0vWS7pT0qqT3JX0l6TtJP0r6VdKfkv6W9I+kfyX9J+k/Sf9L+k/Sf5L+l/SfpP8k/Sfpf0n/SfpX0r+S/pH0t6S/JP0p6Q9Jv0v6TdKvkn6R9LOknyR9L+k7Sd9K+kbS15K+kvSlpC8kfS7pM0mfSvpE0seSPpL0oaQPJL0v6T1J70p6R9Lbkt6S9KakNyS9Luk1Sa9KekXSy5JekvSipBckPS/pOUnPSnpG0tOSnpL0pKQnJD0u6TFJj0p6RNJDCF3mQkmXSFoh6UpJV0u6TtINkm6UdJOkmy0ctLkq2f8ISbdZODjbwsGJkm6UdKOkayVdIWmFpCZcJOmirDfP7GaSrpW0UtI1kq6XdIOkGyXdJOlmSbdIulXSbZJul3SHpDsl3SXp7qB6+iOoj1xEDRXfTtJOknaWtIukXSXtJmk3STW8H3Ofuus+7+D58Kh89vfrvXse4nV9fOI6hxN5W1xLt5L0PEk/STpb0l6S7pN0p6Rn0+uH7SWdIekHSa9L2jHrTRsC60k6TdJvkj6XdGDWm2c8I+lhSe+l12YfSXtIOknSMZKOlnSUpCMlHS7pMEmHSjpE0sGSDrLw7u8gW1U4wML7RwdZOHh4WFnZOCpxP/w+73hAWXBdkj7rW0mXStqOPlJrW0naWdJekvaVdICkgyQdbOHd+UMsHKwjLbz7Y4dPlHSCpOMlHSvpGElHS7oq6zdbA7tIOl3SHyTDatDHkq6RdLikmyV9J+l5SVtmvYFmgHda7ZX1PbwJW7YtJZ0s6SczKLtJulfSi5LelbSCAmMcI+lJM9C/kvSKpHslfZO+vtZzJF0o6XZJ76cH5z1J90m6RNLN6ftrTnr9sJOkUxn6aM6Fkj6U9Jqk7bPetJGwlYUpoXSSZH2k13aWdI6k9y0c7L+YnpakLz35Hx1vXvKsma6VdKSku8w8vZqeEz1RP5rB/YiAuZukkyW9LeluSedKOi6dnzVE+/w9SRdJ+iCdU3aVhSNwPT14/5rp+9PySZz/+8nC0YzXz3ruZH2uqPzJNf9fY3+dKOl7M+E3Stwo6TZJd1k4WN+1cGDfJumPgPdIONgkbWfhoJHXLh8b24OZM+9YF1JJn7V/JV0l6WpJ11o4yNdZONDXWzhIrps4n/0sqJ/6tC6uI18zJT7l/ydJR0q6WdIzkl6x8HzZO3a+5Jy4WNKD6bXBW5JOknRoer7sOJy8fti+fKTpBwtHnDaS9Lykv8xt0m8t7PdyUelrh4V1s1Z8kfOFrUEaKu9LukLSLhQgyzaRtIOk0yX9buHI0CsWvt/XJoW0sMryZTtnfr3u9XAfWtgn3rNwTL1m4aB+bfoOcBulzy85nyd9N3lNUHo+5x2hfW/vt3Dgl/dT0y3cV78tvWAyj1ctvJNdn56fNyZ+1pUd3HnfC3zfwndq/7Z/RlJJ+bRX+ixy29z3PgrdA08s+e59wfmjr/wy7pzWJE6ksNWsj8wsFTNF8mdJz5n5+j19vfADC98vfNvCwf2OhXfH37L/P8v8xsI3k79L+2x6bdD3+vJ3KdNrmrc9PBdovoWDH+kl6Xk1v1Nbn3ktNb8Vvmvh2P2HPXz9YKakH9Nfw+9YOIY+Sn+evSa9Pjh/4nu4P6THrJ8tHIN+snDM/srCMf2L9FjxS3rs+dXCsepX8/tv02Pdb9Zj2+8WjnW/W49df6Tnt3PwD+sxNaS/rMfaP7PHi79a3y+jZ5h5K9dJOl3SHhQm63aRdKqkn82MvGbhx/CydGPh77aF92v/tHBELzyn5xeb7y8cs7+ZJXnfBHfOPm8Wru72OLR9kO5P03l/7VDfBx8F+P0k7/9Z+l7uR+kx6xsLx8jv7HgP/h5JN1GcbNtR0iWS/rJwPLxt4X7/yMJx9Qe7l8n2s/XYl/a79fiX9riX9niY9hiZ9niZ9riZ9viZFvnalvZ4m/Z4nPZ4nfZ4nvZ4n/Z4oLayx3/nLX3cdLONIz8Bby9J95sB+Ts9QO63cPD/0sKR/W0LB/F3LBzY/5l8J/ejhYP5Xem3ND6wcFD/ysKR/R8LB/0/7XmT93TftHBEf8fCUf5dU/cHO2/+tHDQ/8XCwf+vhXtB3Nf31p95jHznMLX39cLCwf+/hYN/OuN5+p7+eJ8v/xF/14gHcgOaJmkzSVeaEdqXgqzKppKOlnSftY8OPmHh3e/v0yGu762HCjGww0P2hfSFv/y8fOdNLz5zzA87aJMZ5A9t3uIQScea6XrT/r4jfJd9b/PdJwXaX9Illr+D/YGFd6c/sr5fb79zC2dY+I7OQ+k1wpFmyt7x9Pq1Xek75q+YGXvZwqmXfWzep9w9XTH7Pbq8fqfRd9LtfC6fIUnfN+5t97Zyr3O/Iz7J5n2m+1jyd8p9w8L3fj1n9AcL9zH/buGuAb8a+9f6bdN9vOyn6Xvyf03+P+y/hYV/9dqsfd9v5XM3Hj2r9a7YAEinPrz3xUch35r8gJJ9cF76Xvlj8+3dI7I+uyb4OLJz9kfzjhavXrxbeY+t4gvZJkm60MLFEf+0h3U8Zb+j9BdJ35qZ+tIMxsf2M/DfzBD8biblH/vdY/j17ff0vQe2vvDf9vv7E3/XdP+O7z2iP3u/2K9e/bqyfMC/+P57+7v5ddJz9vdMO1/+/c6kHbxT6zGRkxaVLDxP8ooGN0uWrU2Xm3nxHyFfNdNyfPrC4Yb0tYJvC+wg6aqsNwvAhttO0vGSPlX9j5H6J5u3zNg8YmZkq6w3C8CG2w7pTUmTRsZPkD9v4S6pky0cvN+xh5jWYRdJ51j4YcA67JWxHy0cN3/M+1v7Vb75h1vktzfmF39v9rO8v2WlhfM2k9+L2knSORauO6rDnhb+HmT9tJ/13XTff6d9P+OOlrxfxpeV1R8fzP5bvQP7vuUOCz+I8OMNOWGRtV0lnSrpc6v/zqF/UvCHtcdY+KM1+8WCr/M8XL7GwjUH9fnRwon1YRfWD1tYvg7vbQt/VHi+d+5N05/L2U7Sadm5Cc+a6M6z+u/g+RJe3wPojzqwPu6wQNOv3xfT//rKfvfqfwZ9CXDfrS1zLtMLOjPaflKWZT6zdaOF+9JutvCn2b5Tir7Tqg4bSjpS0r2WU4Kh7e6S7rLwe15+LstbZa8XfBvMryPwP5z1H8TuYuHEss8jfWjhFJ4v6vGn5Xz7C1+hZhJCvX8j29w62q4avZnA++zLtTfJeuNA8w2xJpz8fEO6N7iPCX5r/t1uEvpIFvP9n9a0/zHdjxa+Y2gHvkc5JfVRANPz8Tb9LKGPaGLJ46wNS4H5pxnKtPl/c8u9Bha+qqoNfwfnf5OL6w0AcNR7/wOi4MUFHQL9GgAAAABJRU5ErkJggg=="

        # Datos básicos del certificado
        datos_certificado = {
            "codigo_seguridad": codigo_seguridad,
            "logo_bsl_url": logo_bsl_base64,
            "fecha_atencion": data.get("fecha_atencion", formatear_fecha_espanol(fecha_actual)),
            "ciudad": "BOGOTÁ" if data.get("codEmpresa") == "GODRONE" else data.get("ciudad", "Bogotá"),
            "vigencia": data.get("vigencia", "1 año"),
            "ips_sede": data.get("ips_sede", "Sede norte DHSS0244914"),

            # Datos personales
            "nombres_apellidos": data.get("nombres_apellidos", ""),
            "documento_identidad": data.get("documento_identidad", ""),
            "empresa": data.get("empresa", "PARTICULAR"),
            "cargo": data.get("cargo", ""),
            "genero": data.get("genero", ""),
            "edad": data.get("edad", ""),
            "fecha_nacimiento": data.get("fecha_nacimiento", ""),
            "estado_civil": data.get("estado_civil", ""),
            "hijos": data.get("hijos", "0"),
            "profesion": data.get("profesion", ""),
            "email": data.get("email", ""),
            "celular": data.get("celular", ""),
            "tipo_examen": data.get("tipo_examen", "Ingreso"),
            "foto_paciente": obtener_foto_desde_postgres(data.get("wix_id")) if data.get("wix_id") else data.get("foto_paciente", None),

            # Exámenes realizados
            "examenes_realizados": data.get("examenes_realizados", [
                {"nombre": "Examen Médico Osteomuscular", "fecha": formatear_fecha_espanol(fecha_actual)},
                {"nombre": "Audiometría", "fecha": formatear_fecha_espanol(fecha_actual)},
                {"nombre": "Optometría", "fecha": formatear_fecha_espanol(fecha_actual)}
            ]),

            # Concepto médico (solo SANITHELP-JJ tiene valor por defecto)
            "concepto_medico": data.get("concepto_medico", "") or ('ELEGIBLE PARA EL CARGO' if data.get('codEmpresa') == 'SANITHELP-JJ' else ''),

            # Resultados generales
            "resultados_generales": data.get("resultados_generales", [
                {
                    "examen": "Examen Médico Osteomuscular",
                    "descripcion": "Basándonos en los resultados obtenidos de la evaluación osteomuscular, certificamos que el paciente presenta un sistema osteomuscular en condiciones óptimas de salud. Esta condición le permite llevar a cabo una variedad de actividades físicas y cotidianas sin restricciones notables y con un riesgo mínimo de lesiones osteomusculares."
                },
                {
                    "examen": "Audiometría",
                    "descripcion": "No presenta signos de pérdida auditiva o alteraciones en la audición. Los resultados se encuentran dentro de los rangos normales establecidos para la población general y no se observan indicios de daño auditivo relacionado con la exposición laboral a ruido u otros factores."
                },
                {
                    "examen": "Optometría",
                    "descripcion": "Presión intraocular (PIO): 15 mmHg en ambos ojos. Reflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos. Campo visual: Normal en ambos ojos. Visión de colores: Normal. Fondo de ojo: Normal."
                }
            ]),

            # Recomendaciones médicas adicionales
            "recomendaciones_medicas": data.get("recomendaciones_medicas", ""),

            # Firmas
            "medico_nombre": data.get("medico_nombre", ""),
            "medico_registro": data.get("medico_registro", ""),
            "medico_licencia": data.get("medico_licencia", ""),
            "firma_medico_url": data.get("firma_medico_url"),
            "firma_paciente_url": data.get("firma_paciente_url"),

            "optometra_nombre": data.get("optometra_nombre", "Dr. Miguel Garzón Rincón"),
            "optometra_registro": data.get("optometra_registro", "C.C.: 79.569.881 - Optómetra Ocupacional Res. 6473 04/07/2017"),
            "firma_optometra_url": data.get("firma_optometra_url"),

            # Exámenes detallados (página 2, opcional)
            "examenes_detallados": data.get("examenes_detallados", []),

            # Datos visuales (Optometría/Visiometría)
            "datos_visual": data.get("datos_visual"),

            # Datos de audiometría
            "datos_audiometria": data.get("datos_audiometria"),

            # Lista de exámenes para verificar tipo
            "examenes": data.get("examenes", []),

            # Logo URL
            "logo_url": "https://bsl-utilidades-yp78a.ondigitalocean.app/static/logo-bsl.png"
        }

        # Asegurar que existan los campos aunque estén vacíos (PRIMERO)
        datos_certificado.setdefault("eps", "")
        datos_certificado.setdefault("arl", "")
        datos_certificado.setdefault("pensiones", "")
        datos_certificado.setdefault("nivel_educativo", "")

        # Si hay wix_id, obtener datos adicionales de PostgreSQL (EPS, ARL, Pensiones, Nivel Educativo, Ciudad)
        # Esto sobrescribirá los valores vacíos con los datos reales de la BD
        if data.get("wix_id"):
            print(f"🔍 Buscando datos adicionales para wix_id: {data.get('wix_id')}")
            datos_postgres = obtener_datos_formulario_postgres(data.get("wix_id"))
            if datos_postgres:
                print(f"📦 Datos obtenidos de PostgreSQL: {list(datos_postgres.keys())}")
                # Merge datos de PostgreSQL con datos del certificado
                for key in ['eps', 'arl', 'pensiones', 'nivelEducativo', 'ciudadDeResidencia', 'celular']:
                    if key in datos_postgres and datos_postgres[key]:
                        # Mapear campos con nombres diferentes en la plantilla
                        if key == 'nivelEducativo':
                            template_key = 'nivel_educativo'
                        elif key == 'ciudadDeResidencia':
                            template_key = 'ciudad'
                        else:
                            template_key = key

                        # Para ciudad: solo usar PostgreSQL si NO viene en el request de Wix
                        if template_key == 'ciudad':
                            # Solo sobrescribir si no viene del request o es el valor por defecto
                            if not data.get('ciudad') or data.get('ciudad') == 'Bogotá':
                                datos_certificado[template_key] = datos_postgres[key]
                                print(f"✅ Ciudad desde PostgreSQL: {datos_postgres[key]}")
                            else:
                                print(f"ℹ️  Ciudad ya viene del request de Wix: {data.get('ciudad')}")
                        else:
                            # Para otros campos, sobrescribir siempre
                            datos_certificado[template_key] = datos_postgres[key]
                            print(f"✅ Datos adicionales de PostgreSQL: {template_key} = {datos_postgres[key]}")
                    else:
                        print(f"⚠️  Campo {key} no encontrado o vacío en PostgreSQL")

                # También agregar ciudadDeResidencia como dirección para el certificado
                if 'ciudadDeResidencia' in datos_postgres and datos_postgres['ciudadDeResidencia']:
                    datos_certificado['direccion'] = datos_postgres['ciudadDeResidencia']
                    print(f"✅ Dirección desde PostgreSQL: {datos_postgres['ciudadDeResidencia']}")
            else:
                print(f"❌ No se pudieron obtener datos de PostgreSQL para wix_id: {data.get('wix_id')}")

        # Determinar si mostrar aviso de sin soporte
        mostrar_aviso, texto_aviso = determinar_mostrar_sin_soporte(data)
        datos_certificado["mostrar_sin_soporte"] = mostrar_aviso
        datos_certificado["texto_sin_soporte"] = texto_aviso

        if mostrar_aviso:
            print(f"⚠️ Mostrando aviso de pago pendiente")

        # Renderizar template HTML
        print("🎨 Renderizando plantilla HTML...")
        html_content = render_template("certificado_medico.html", **datos_certificado)

        # Guardar HTML en archivo temporal para Puppeteer
        print("💾 Guardando HTML temporal...")
        temp_html = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode='w', encoding='utf-8')
        temp_html.write(html_content)
        temp_html.close()
        temp_filename = os.path.basename(temp_html.name)

        # Guardar referencia al archivo temporal para el endpoint /temp-html/
        if not hasattr(app, 'temp_html_files'):
            app.temp_html_files = {}
        app.temp_html_files[temp_filename] = temp_html.name

        # Construir URL para Puppeteer
        base_url = os.getenv("BASE_URL", "https://bsl-utilidades-yp78a.ondigitalocean.app")
        html_url = f"{base_url}/temp-html/{temp_filename}"

        # Generar PDF con Puppeteer
        print("🎭 Generando PDF con Puppeteer...")
        pdf_content = puppeteer_html_to_pdf_from_url(
            html_url=html_url,
            output_filename=f"certificado_{datos_certificado['documento_identidad']}"
        )

        # Limpiar archivo HTML temporal
        try:
            os.unlink(temp_html.name)
            if temp_filename in app.temp_html_files:
                del app.temp_html_files[temp_filename]
        except Exception as cleanup_error:
            print(f"⚠️ Error limpiando archivo HTML temporal: {cleanup_error}")

        # Guardar PDF temporalmente
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_pdf.write(pdf_content)
        temp_pdf.close()
        pdf_url = f"file://{temp_pdf.name}"
        print(f"✅ PDF generado y guardado en: {temp_pdf.name}")

        # Crear objeto de resultado compatible con el código existente
        result = {
            "success": True,
            "pdf": pdf_url,
            "fileSize": len(pdf_content)
        }

        print(f"✅ PDF generado exitosamente: {pdf_url}")

        # Si se especifica guardar en Drive
        if data.get("guardar_drive", False):
            print("💾 Guardando en Google Drive...")

            # Determinar carpeta de destino
            folder_id = data.get("folder_id") or EMPRESA_FOLDERS.get("BSL")

            # Descargar el PDF temporalmente
            pdf_response = requests.get(pdf_url)
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.write(pdf_response.content)
            temp_file.close()

            # Nombre del archivo
            documento_identidad = datos_certificado.get("documento_identidad", "sin_doc")
            nombre_archivo = data.get("nombre_archivo") or f"certificado_{documento_identidad}_{fecha_actual.strftime('%Y%m%d')}.pdf"

            # Subir a Google Drive según el destino configurado
            if DEST == "drive":
                resultado = subir_pdf_a_drive(temp_file.name, nombre_archivo, folder_id)
            elif DEST == "drive-oauth":
                resultado = subir_pdf_a_drive_oauth(temp_file.name, nombre_archivo, folder_id)
            elif DEST == "gcs":
                resultado = subir_pdf_a_gcs(temp_file.name, nombre_archivo, folder_id)
            else:
                resultado = {"success": False, "error": f"Destino {DEST} no soportado"}

            # Limpiar archivo temporal
            os.unlink(temp_file.name)

            if not resultado.get("success"):
                print(f"⚠️ Error subiendo a Drive: {resultado.get('error')}")

        # Preparar respuesta
        respuesta = {
            "success": True,
            "pdf_url": pdf_url,
            "codigo_seguridad": codigo_seguridad,
            "message": "Certificado médico generado exitosamente"
        }

        # Si se guardó en Drive, agregar información
        if data.get("guardar_drive", False) and resultado.get("success"):
            respuesta["drive_file_id"] = resultado.get("fileId")
            respuesta["drive_web_link"] = resultado.get("webViewLink")

        # Configurar headers CORS
        response = jsonify(respuesta)
        response.headers["Access-Control-Allow-Origin"] = "*"

        return response

    except Exception as e:
        print(f"❌ Error generando certificado: {str(e)}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "error": str(e)
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"

        return error_response, 500

@app.route("/generar-certificado-medico-puppeteer", methods=["OPTIONS"])
def options_certificado_puppeteer():
    response_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization"
    }
    return ("", 204, response_headers)

@app.route("/generar-certificado-medico-puppeteer", methods=["POST"])
def generar_certificado_medico_puppeteer():
    try:
        print("📋 Iniciando generación de certificado médico con Puppeteer...")

        # Obtener datos del request
        data = request.get_json()
        print(f"📝 Datos recibidos: {data}")

        # Generar código de seguridad único
        codigo_seguridad = str(uuid.uuid4())

        # Preparar datos con valores por defecto
        fecha_actual = datetime.now()

        # Logo BSL embebido como base64 (recreado basado en el logo real)
        logo_bsl_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAASwAAABkCAYAAAA8AQ3AAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAKKUlEQVR4nO2dW6hdRRiAf21ttbW2trZaW1tb29ra2tra2traaq2trdbaWluttba2ttbWWmtrrbW1tdbW2lqttbXW1lpra62ttbXWWmtrrbVaX2f/M2tmzzl7n5kzc2bWzNrfB4czOXuvNbP+b2b+mfnPrFkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwDDYXFJXSf1a0vWS7pT0qqT3JX0l6TtJP0r6VdKfkv6W9I+kfyX9J+k/Sf9L+k/Sf5L+l/SfpP8k/Sfpf0n/SfpX0r+S/pH0t6S/JP0p6Q9Jv0v6TdKvkn6R9LOknyR9L+k7Sd9K+kbS15K+kvSlpC8kfS7pM0mfSvpE0seSPpL0oaQPJL0v6T1J70p6R9Lbkt6S9KakNyS9Luk1Sa9KekXSy5JekvSipBckPS/pOUnPSnpG0tOSnpL0pKQnJD0u6TFJj0p6RNJDCF3mQkmXSFoh6UpJV0u6TtINkm6UdJOkmy0ctLkq2f8ISbdZODjbwsGJkm6UdKOkayVdIWmFpCZcJOmirDfP7GaSrpW0UtI1kq6XdIOkGyXdJOlmSbdIulXSbZJul3SHpDsl3SXp7qB6+iOoj1xEDRXfTtJOknaWtIukXSXtJmk3STW8H3Ofuus+7+D58Kh89vfrvXse4nV9fOI6hxN5W1xLt5L0PEk/STpb0l6S7pN0p6Rn0+uH7SWdIekHSa9L2jHrTRsC60k6TdJvkj6XdGDWm2c8I+lhSe+l12YfSXtIOknSMZKOlnSUpCMlHS7pMEmHSjpE0sGSDrLw7u8gW1U4wML7RwdZOHh4WFnZOCpxP/w+73hAWXBdkj7rW0mXStqOPlJrW0naWdJekvaVdICkgyQdbOHd+UMsHKwjLbz7Y4dPlHSCpOMlHSvpGElHS7oq6zdbA7tIOl3SHyTDatDHkq6RdLikmyV9J+l5SVtmvYFmgHda7ZX1PbwJW7YtJZ0s6SczKLtJulfSi5LelbSCAmMcI+lJM9C/kvSKpHslfZO+vtZzJF0o6XZJ76cH5z1J90m6RNLN6ftrTnr9sJOkUxn6aM6Fkj6U9Jqk7bPetJGwlYUpoXSSZH2k13aWdI6k9y0c7L+YnpakLz35Hx1vXvKsma6VdKSku8w8vZqeEz1RP5rB/YiAuZukkyW9LeluSedKOi6dnzVE+/w9SRdJ+iCdU3aVhSNwPT14/5rp+9PySZz/+8nC0YzXz3ruZH2uqPzJNf9fY3+dKOl7M+E3Stwo6TZJd1k4WN+1cGDfJumPgPdIONgkbWfhoJHXLh8b24OZM+9YF1JJn7V/JV0l6WpJ11o4yNdZONDXWzhIrps4n/0sqJ/6tC6uI18zJT7l/ydJR0q6WdIzkl6x8HzZO3a+5Jy4WNKD6bXBW5JOknRoer7sOJy8fti+fKTpBwtHnDaS9Lykv8xt0m8t7PdyUelrh4V1s1Z8kfOFrUEaKu9LukLSLhQgyzaRtIOk0yX9buHI0CsWvt/XJoW0sMryZTtnfr3u9XAfWtgn3rNwTL1m4aB+bfoOcBulzy85nyd9N3lNUHo+5x2hfW/vt3Dgl/dT0y3cV78tvWAyj1ctvJNdn56fNyZ+1pUd3HnfC3zfwndq/7Z/RlJJ+bRX+ixy29z3PgrdA08s+e59wfmjr/wy7pzWJE6ksNWsj8wsFTNF8mdJz5n5+j19vfADC98vfNvCwf2OhXfH37L/P8v8xsI3k79L+2x6bdD3+vJ3KdNrmrc9PBdovoWDH+kl6Xk1v1Nbn3ktNb8Vvmvh2P2HPXz9YKakH9Nfw+9YOIY+Sn+evSa9Pjh/4nu4P6THrJ8tHIN+snDM/srCMf2L9FjxS3rs+dXCsepX8/tv02Pdb9Zj2+8WjnW/W49df6Tnt3PwD+sxNaS/rMfaP7PHi79a3y+jZ5h5K9dJOl3SHhQm63aRdKqkn82MvGbhx/CydGPh77aF92v/tHBELzyn5xeb7y8cs7+ZJXnfBHfOPm8Wru72OLR9kO5P03l/7VDfBx8F+P0k7/9Z+l7uR+kx6xsLx8jv7HgP/h5JN1GcbNtR0iWS/rJwPLxt4X7/yMJx9Qe7l8n2s/XYl/a79fiX9riX9niY9hiZ9niZ9riZ9viZFvnalvZ4m/Z4nPZ4nfZ4nvZ4n/Z4oLayx3/nLX3cdLONIz8Bby9J95sB+Ts9QO63cPD/0sKR/W0LB/F/JN/J/ejhYP5Xem3ND6wcFD/ysKR/0/7XmT93TftHBEf8fCwf+vhXtB3Nf31p95jHznMLX39cLCwf+/hYN/OuN5+p7+eJ8v/xF/14gHcgOaJmkzSVeaEdqXgqzKppKOlnSftY8OPmHh3e/v0yGu762HCjGww0P2hfSFv/y8fOdNLz5zzA87aJMZ5A9t3uIQScea6XrT/r4jfJd9b/PdJwXaX9Illr+D/YGFd6c/sr5fb79zC2dY+I7OQ+k1wpFmyt7x9Pq1Xek75q+YGXvZwqmXfWzep9w9XTH7Pbq8fqfRd9LtfC6fIUnfN+5t97Zyr3O/Iz7J5n2m+1jyd8p9w8L3fj1n9AcL9zH/buGuAb8a+9f6bdN9vOyn6Xvyf03+P+y/hYV/9dqsfd9v5XM3Hj2r9a7YAEinPrz3xUch35r8gJJ9cF76Xvlj8+3dI7I+uyb4OLJz9kfzjhavXrxbeY+t4gvZJkm60MLFEf+0h3U8Zb+j9BdJ35qZ+tIMxsf2M/DfzBD8afflH/vdY/j17ff0vQe2vvDf9vv7E3/XdP+O7z2iP3u/2K9e/bqyfMC/+P57+7v5ddJz9vdMO1/+/c6kHbxT6zGRkxaVLDxP8ooGN0uWrU2Xm3nxHyFfNdNyfPrC4Yb0tYJvC+wg6aqsNwvAhttO0vGSPlX9j5H6J5u3zNg8YmZkq6w3C8CG2w7pTUmTRsZPkD9v4S6pky0cvN+xh5jWYRdJ51j4YcA67JWxHy0cN3/M+1v7Vb75h1vktzfmF39v9rO8v2WlhfM2k9+L2knSORauO6rDnhb+HmT9tJ/13XTff6d9P+OOlrxfxpeV1R8fzP5bvQP7vuUOCz+I8OMNOWGRtV0lnSrpc6v/zqF/UvCHtcdY+KM1+8WCr/M8XL7GwjUH9fnRwon1YRfWD1tYvg7vbQt/VHi+d+5N05/L2U7Sadm5Cc+a6M6z+u/g+RJe3wPojzqwPu6wQNOv3xfT//rKfvfqfwZ9CXDfrS1zLtMLOjPaflKWZT6zdaOF+9JutvCn2b5Tir7Tqg4bSjpS0r2WU4Kh7e6S7rLwe15+LstbZa8XfBvMryPwP5z1H8TuYuHEss8jfWjhFJ4v6vGn5Xz7C1+hZhJCvX8j29w62q4avZnA++zLtTfJeuNA8w2xJpz8fEO6N7iPCX5r/t1uEvpIFvP9n9a0/zHdjxa+Y2gHvkc5JfVRANPz8Tb9LKGPaGLJ46wNS4H5pxnKtPl/c8u9Bha+qqoNfwfnf5OL6w0AcNR7/wOi4MUFHQL9GgAAAABJRU5ErkJggg=="

        # Datos básicos del certificado
        datos_certificado = {
            "codigo_seguridad": codigo_seguridad,
            "logo_bsl_url": logo_bsl_base64,
            "fecha_atencion": data.get("fecha_atencion", formatear_fecha_espanol(fecha_actual)),
            "ciudad": "BOGOTÁ" if data.get("codEmpresa") == "GODRONE" else data.get("ciudad", "Bogotá"),
            "vigencia": data.get("vigencia", "1 año"),
            "ips_sede": data.get("ips_sede", "Sede norte DHSS0244914"),

            # Datos personales
            "nombres_apellidos": data.get("nombres_apellidos", ""),
            "documento_identidad": data.get("documento_identidad", ""),
            "empresa": data.get("empresa", "PARTICULAR"),
            "cargo": data.get("cargo", ""),
            "genero": data.get("genero", ""),
            "edad": data.get("edad", ""),
            "fecha_nacimiento": data.get("fecha_nacimiento", ""),
            "estado_civil": data.get("estado_civil", ""),
            "hijos": data.get("hijos", "0"),
            "profesion": data.get("profesion", ""),
            "email": data.get("email", ""),
            "celular": data.get("celular", ""),
            "tipo_examen": data.get("tipo_examen", "Ingreso"),
            "foto_paciente": obtener_foto_desde_postgres(data.get("wix_id")) if data.get("wix_id") else data.get("foto_paciente", None),

            # Exámenes realizados
            "examenes_realizados": data.get("examenes_realizados", [
                {"nombre": "Examen Médico Osteomuscular", "fecha": formatear_fecha_espanol(fecha_actual)},
                {"nombre": "Audiometría", "fecha": formatear_fecha_espanol(fecha_actual)},
                {"nombre": "Optometría", "fecha": formatear_fecha_espanol(fecha_actual)}
            ]),

            # Concepto médico (solo SANITHELP-JJ tiene valor por defecto)
            "concepto_medico": data.get("concepto_medico", "") or ('ELEGIBLE PARA EL CARGO' if data.get('codEmpresa') == 'SANITHELP-JJ' else ''),

            # Resultados generales
            "resultados_generales": data.get("resultados_generales", [
                {
                    "examen": "Examen Médico Osteomuscular",
                    "descripcion": "Basándonos en los resultados obtenidos de la evaluación osteomuscular, certificamos que el paciente presenta un sistema osteomuscular en condiciones óptimas de salud. Esta condición le permite llevar a cabo una variedad de actividades físicas y cotidianas sin restricciones notables y con un riesgo mínimo de lesiones osteomusculares."
                },
                {
                    "examen": "Audiometría",
                    "descripcion": "No presenta signos de pérdida auditiva o alteraciones en la audición. Los resultados se encuentran dentro de los rangos normales establecidos para la población general y no se observan indicios de daño auditivo relacionado con la exposición laboral a ruido u otros factores."
                },
                {
                    "examen": "Optometría",
                    "descripcion": "Presión intraocular (PIO): 15 mmHg en ambos ojos. Reflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos. Campo visual: Normal en ambos ojos. Visión de colores: Normal. Fondo de ojo: Normal."
                }
            ]),

            # Recomendaciones médicas adicionales
            "recomendaciones_medicas": data.get("recomendaciones_medicas", ""),

            # Firmas
            "medico_nombre": data.get("medico_nombre", ""),
            "medico_registro": data.get("medico_registro", ""),
            "medico_licencia": data.get("medico_licencia", ""),
            "firma_medico_url": data.get("firma_medico_url"),
            "firma_paciente_url": data.get("firma_paciente_url"),

            "optometra_nombre": data.get("optometra_nombre", "Dr. Miguel Garzón Rincón"),
            "optometra_registro": data.get("optometra_registro", "C.C.: 79.569.881 - Optómetra Ocupacional Res. 6473 04/07/2017"),
            "firma_optometra_url": data.get("firma_optometra_url"),

            # Exámenes detallados (página 2, opcional)
            "examenes_detallados": data.get("examenes_detallados", []),

            # Datos visuales (Optometría/Visiometría)
            "datos_visual": data.get("datos_visual"),

            # Datos de audiometría
            "datos_audiometria": data.get("datos_audiometria"),

            # Lista de exámenes para verificar tipo
            "examenes": data.get("examenes", []),

            # Logo URL
            "logo_url": "https://bsl-utilidades-yp78a.ondigitalocean.app/static/logo-bsl.png"
        }

        # Asegurar que existan los campos aunque estén vacíos (PRIMERO)
        datos_certificado.setdefault("eps", "")
        datos_certificado.setdefault("arl", "")
        datos_certificado.setdefault("pensiones", "")
        datos_certificado.setdefault("nivel_educativo", "")

        # Si hay wix_id, obtener datos adicionales de PostgreSQL (EPS, ARL, Pensiones, Nivel Educativo, Ciudad)
        # Esto sobrescribirá los valores vacíos con los datos reales de la BD
        if data.get("wix_id"):
            print(f"🔍 Buscando datos adicionales para wix_id: {data.get('wix_id')}")
            datos_postgres = obtener_datos_formulario_postgres(data.get("wix_id"))
            if datos_postgres:
                print(f"📦 Datos obtenidos de PostgreSQL: {list(datos_postgres.keys())}")
                # Merge datos de PostgreSQL con datos del certificado
                for key in ['eps', 'arl', 'pensiones', 'nivelEducativo', 'ciudadDeResidencia', 'celular']:
                    if key in datos_postgres and datos_postgres[key]:
                        # Mapear campos con nombres diferentes en la plantilla
                        if key == 'nivelEducativo':
                            template_key = 'nivel_educativo'
                        elif key == 'ciudadDeResidencia':
                            template_key = 'ciudad'
                        else:
                            template_key = key

                        # Para ciudad: solo usar PostgreSQL si NO viene en el request de Wix
                        if template_key == 'ciudad':
                            # Solo sobrescribir si no viene del request o es el valor por defecto
                            if not data.get('ciudad') or data.get('ciudad') == 'Bogotá':
                                datos_certificado[template_key] = datos_postgres[key]
                                print(f"✅ Ciudad desde PostgreSQL: {datos_postgres[key]}")
                            else:
                                print(f"ℹ️  Ciudad ya viene del request de Wix: {data.get('ciudad')}")
                        else:
                            # Para otros campos, sobrescribir siempre
                            datos_certificado[template_key] = datos_postgres[key]
                            print(f"✅ Datos adicionales de PostgreSQL: {template_key} = {datos_postgres[key]}")
                    else:
                        print(f"⚠️  Campo {key} no encontrado o vacío en PostgreSQL")

                # También agregar ciudadDeResidencia como dirección para el certificado
                if 'ciudadDeResidencia' in datos_postgres and datos_postgres['ciudadDeResidencia']:
                    datos_certificado['direccion'] = datos_postgres['ciudadDeResidencia']
                    print(f"✅ Dirección desde PostgreSQL: {datos_postgres['ciudadDeResidencia']}")
            else:
                print(f"❌ No se pudieron obtener datos de PostgreSQL para wix_id: {data.get('wix_id')}")

        # Determinar si mostrar aviso de sin soporte
        mostrar_aviso, texto_aviso = determinar_mostrar_sin_soporte(data)
        datos_certificado["mostrar_sin_soporte"] = mostrar_aviso
        datos_certificado["texto_sin_soporte"] = texto_aviso

        if mostrar_aviso:
            print(f"⚠️ Mostrando aviso de pago pendiente")

        # PRE-PROCESAR IMÁGENES: convertir URLs de Wix a DO Spaces ANTES de renderizar
        print("🖼️ Pre-procesando imágenes para usar DO Spaces...")

        # 1. Foto del paciente
        if datos_certificado.get("foto_paciente"):
            foto_url = datos_certificado["foto_paciente"]
            if 'wix' in foto_url.lower() or 'static.wixstatic.com' in foto_url:
                print(f"📸 Procesando foto de paciente desde Wix...")
                foto_local = descargar_imagen_wix_localmente(foto_url)
                if foto_local:
                    datos_certificado["foto_paciente"] = foto_local
                    print(f"✅ Foto paciente cacheada: {foto_local}")
                else:
                    print(f"⚠️ No se pudo cachear foto paciente, usando URL Wix")

        # 2. Firma del médico (si no viene, usar la por defecto)
        if not datos_certificado.get("firma_medico_url"):
            datos_certificado["firma_medico_url"] = "https://bsl-utilidades-yp78a.ondigitalocean.app/static/FIRMA-JUAN134.jpeg"

        # 3. Firma del optómetra (si no viene, usar la por defecto)
        if not datos_certificado.get("firma_optometra_url"):
            datos_certificado["firma_optometra_url"] = "https://bsl-utilidades-yp78a.ondigitalocean.app/static/FIRMA-OPTOMETRA.jpeg"

        # 4. Firma del paciente - Ya no se descarga (QR estático en template)
        # El QR de validación está embebido en el template como qr-validacion.jpg
        print(f"ℹ️  Firma paciente: QR estático en template")

        # Renderizar template HTML (ahora con imágenes ya procesadas a DO Spaces)
        print("🎨 Renderizando plantilla HTML...")
        html_content = render_template("certificado_medico.html", **datos_certificado)

        # Generar PDF con Puppeteer usando file:// (método simple que funciona)
        print("📄 Generando PDF con Puppeteer (file://)...")
        pdf_content = generar_pdf_con_puppeteer_local(
            html_content=html_content,
            output_filename=f"certificado_{datos_certificado['documento_identidad']}"
        )

        # Guardar PDF temporalmente
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_pdf.write(pdf_content)
        temp_pdf.close()
        pdf_url = f"file://{temp_pdf.name}"
        print(f"✅ PDF generado y guardado en: {temp_pdf.name}")

        # Crear objeto de resultado compatible con el código existente
        result = {
            "success": True,
            "pdf": pdf_url,
            "fileSize": len(pdf_content)
        }

        print(f"✅ PDF generado exitosamente: {pdf_url}")

        # Si se especifica guardar en Drive
        if data.get("guardar_drive", False):
            print("💾 Guardando en Google Drive...")

            # Determinar carpeta de destino
            folder_id = data.get("folder_id") or EMPRESA_FOLDERS.get("BSL")

            # Nombre del archivo
            documento_identidad = datos_certificado.get("documento_identidad", "sin_doc")
            nombre_archivo = data.get("nombre_archivo") or f"certificado_{documento_identidad}_{fecha_actual.strftime('%Y%m%d')}.pdf"

            # Subir a Google Drive según el destino configurado
            if DEST == "drive":
                resultado = subir_pdf_a_drive(temp_pdf.name, nombre_archivo, folder_id)
            elif DEST == "drive-oauth":
                resultado = subir_pdf_a_drive_oauth(temp_pdf.name, nombre_archivo, folder_id)
            elif DEST == "gcs":
                resultado = subir_pdf_a_gcs(temp_pdf.name, nombre_archivo, folder_id)
            else:
                resultado = {"success": False, "error": f"Destino {DEST} no soportado"}

            # Limpiar archivo temporal
            os.unlink(temp_pdf.name)

            if not resultado.get("success"):
                print(f"⚠️ Error subiendo a Drive: {resultado.get('error')}")

        # Preparar respuesta
        respuesta = {
            "success": True,
            "pdf_url": pdf_url,
            "codigo_seguridad": codigo_seguridad,
            "message": "Certificado médico generado exitosamente con Puppeteer"
        }

        # Si se guardó en Drive, agregar información
        if data.get("guardar_drive", False) and resultado.get("success"):
            respuesta["drive_file_id"] = resultado.get("fileId")
            respuesta["drive_web_link"] = resultado.get("webViewLink")

        # Configurar headers CORS
        response = jsonify(respuesta)
        response.headers["Access-Control-Allow-Origin"] = "*"

        return response

    except Exception as e:
        print(f"❌ Error generando certificado con Puppeteer: {str(e)}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "error": str(e)
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"

        return error_response, 500

@app.route("/images/<filename>")
def serve_image(filename):
    """Servir imágenes públicamente para API2PDF"""
    try:
        return send_from_directory("static", filename)
    except FileNotFoundError:
        return "Image not found", 404

@app.route("/temp-html/<filename>")
def serve_temp_html(filename):
    """Servir archivos HTML temporales para Puppeteer"""
    try:
        if not hasattr(app, 'temp_html_files'):
            return "Temporary file not found", 404

        file_path = app.temp_html_files.get(filename)
        if not file_path or not os.path.exists(file_path):
            return "Temporary file not found", 404

        return send_file(file_path, mimetype='text/html')
    except Exception as e:
        print(f"❌ Error sirviendo HTML temporal: {e}")
        return "Error serving temporary file", 500

# --- Función auxiliar para separar nombres completos ---
def separar_nombre_completo(nombre_completo):
    """
    Separa un nombre completo en sus componentes:
    primerNombre, segundoNombre, primerApellido, segundoApellido

    Args:
        nombre_completo (str): Nombre completo a separar

    Returns:
        dict: Diccionario con los componentes del nombre
    """
    print(f"🔍 Separando nombre: '{nombre_completo}' (tipo: {type(nombre_completo)})")

    if not nombre_completo or not isinstance(nombre_completo, str):
        print(f"⚠️ Nombre vacío o no es string")
        return {
            "primerNombre": "",
            "segundoNombre": "",
            "primerApellido": "",
            "segundoApellido": ""
        }

    # Limpiar y dividir el nombre
    partes = nombre_completo.strip().split()
    print(f"📋 Partes del nombre: {partes} (total: {len(partes)})")

    # Inicializar valores por defecto
    primer_nombre = ""
    segundo_nombre = ""
    primer_apellido = ""
    segundo_apellido = ""

    # Lógica de separación basada en la cantidad de palabras
    num_partes = len(partes)

    if num_partes == 1:
        # Solo un nombre
        primer_nombre = partes[0]
    elif num_partes == 2:
        # Nombre y apellido
        primer_nombre = partes[0]
        primer_apellido = partes[1]
    elif num_partes == 3:
        # Dos nombres y un apellido, o un nombre y dos apellidos
        # Asumimos: primer nombre, segundo nombre, primer apellido
        primer_nombre = partes[0]
        segundo_nombre = partes[1]
        primer_apellido = partes[2]
    elif num_partes >= 4:
        # Nombre completo: primer nombre, segundo nombre, primer apellido, segundo apellido
        primer_nombre = partes[0]
        segundo_nombre = partes[1]
        primer_apellido = partes[2]
        segundo_apellido = " ".join(partes[3:])  # En caso de apellidos compuestos

    resultado = {
        "primerNombre": primer_nombre,
        "segundoNombre": segundo_nombre,
        "primerApellido": primer_apellido,
        "segundoApellido": segundo_apellido
    }

    print(f"✅ Resultado: {resultado}")
    return resultado

# --- Endpoint: PROCESAR CSV ---
@app.route("/procesar-csv", methods=["OPTIONS"])
def options_procesar_csv():
    response_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    return ("", 204, response_headers)

@app.route("/procesar-csv", methods=["POST"])
def procesar_csv():
    """
    Endpoint para procesar archivos CSV con información de personas.
    Separa el nombre completo y extrae campos específicos.

    Campos esperados en el CSV:
    - NOMBRES APELLIDOS Y (o NOMBRES COMPLETOS, o NOMBRES Y APELLIDOS)
    - No IDENTIFICACION
    - CARGO
    - TELEFONOS
    - CIUDAD

    Returns:
        JSON con los datos procesados
    """
    try:
        print("📋 Iniciando procesamiento de CSV...")

        # Verificar que se envió un archivo
        if 'file' not in request.files:
            raise Exception("No se envió ningún archivo CSV")

        file = request.files['file']

        if file.filename == '':
            raise Exception("El archivo está vacío")

        if not file.filename.endswith('.csv'):
            raise Exception("El archivo debe ser un CSV")

        print(f"📄 Archivo recibido: {file.filename}")

        # Leer el contenido del archivo
        stream = io.StringIO(file.stream.read().decode("UTF-8"), newline=None)
        csv_reader = csv.DictReader(stream)

        # Procesar cada fila del CSV
        personas_procesadas = []

        # Hora inicial por defecto: 8:00 AM
        hora_base = datetime.strptime("08:00", "%H:%M")

        # Lista de médicos por defecto (se puede personalizar desde el frontend)
        medicos_disponibles = ["SIXTA", "JUAN 134", "CESAR", "MARY", "NUBIA", "PRESENCIAL", "PILAR"]

        # Contador para registros que NO son BOGOTA (para distribución equitativa)
        contador_no_bogota = 0

        for idx, row in enumerate(csv_reader, start=1):
            try:
                # Normalizar los nombres de las columnas (eliminar espacios al inicio/final)
                row_normalized = {key.strip(): value for key, value in row.items()}

                print(f"🔍 Columnas disponibles: {list(row_normalized.keys())}")

                # Detectar si el CSV ya viene con formato procesado (tiene primerNombre)
                es_formato_procesado = 'primerNombre' in row_normalized

                if es_formato_procesado:
                    # CSV ya procesado: usar los campos directamente
                    print(f"📋 Fila {idx} - Formato procesado detectado")

                    primer_nombre = row_normalized.get('primerNombre', '').strip()
                    segundo_nombre = row_normalized.get('segundoNombre', '').strip()
                    primer_apellido = row_normalized.get('primerApellido', '').strip()
                    segundo_apellido = row_normalized.get('segundoApellido', '').strip()
                    nombre_completo = f"{primer_nombre} {segundo_nombre} {primer_apellido} {segundo_apellido}".strip()
                    nombre_completo = ' '.join(nombre_completo.split())  # Eliminar espacios extras

                    numero_id = row_normalized.get('numeroId', '').strip()
                    cargo = row_normalized.get('cargo', '').strip()
                    celular = row_normalized.get('celular', '').strip()
                    ciudad = row_normalized.get('ciudad', '').strip()
                    tipo_examen = row_normalized.get('tipoExamen', '').strip()
                    empresa = row_normalized.get('empresa', '').strip()

                else:
                    # CSV formato original: procesar nombres
                    nombre_completo = (
                        row_normalized.get('NOMBRES APELLIDOS Y', '') or
                        row_normalized.get('NOMBRES COMPLETOS', '') or
                        row_normalized.get('NOMBRES Y APELLIDOS', '')
                    ).strip()

                    print(f"🔍 Fila {idx} - Nombre encontrado: '{nombre_completo}'")

                    nombres_separados = separar_nombre_completo(nombre_completo)
                    primer_nombre = nombres_separados["primerNombre"]
                    segundo_nombre = nombres_separados["segundoNombre"]
                    primer_apellido = nombres_separados["primerApellido"]
                    segundo_apellido = nombres_separados["segundoApellido"]

                    numero_id = row_normalized.get('No IDENTIFICACION', '').strip()
                    cargo = row_normalized.get('CARGO', '').strip()
                    celular = row_normalized.get('TELEFONOS', '').strip()
                    ciudad = row_normalized.get('CIUDAD', '').strip()
                    tipo_examen = row_normalized.get('TIPO DE EXAMEN OCUPACIONAL', '').strip()
                    empresa = row_normalized.get('Autorizado por:', '').strip()

                # Calcular fecha de atención (un día después de hoy por defecto)
                fecha_atencion = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

                # Normalizar Bogotá a BOGOTA (cualquier variación)
                es_bogota = 'BOGOT' in ciudad.upper()
                if es_bogota:
                    ciudad = 'BOGOTA'

                # Asignar médico y hora: PRESENCIAL y 07:00 si ciudad es Bogotá, sino round-robin
                if es_bogota:
                    medico_asignado = "PRESENCIAL"
                    hora_atencion = "07:00"
                else:
                    # Usar contador solo para registros que NO son BOGOTA
                    medico_asignado = medicos_disponibles[contador_no_bogota % len(medicos_disponibles)]
                    # Calcular hora de atención con incrementos de 10 minutos por registro no-BOGOTA
                    hora_atencion = (hora_base + timedelta(minutes=contador_no_bogota * 10)).strftime('%H:%M')
                    contador_no_bogota += 1

                # Construir objeto persona
                persona = {
                    "fila": idx,
                    "nombreCompleto": nombre_completo,
                    "primerNombre": primer_nombre,
                    "segundoNombre": segundo_nombre,
                    "primerApellido": primer_apellido,
                    "segundoApellido": segundo_apellido,
                    "numeroId": numero_id,
                    "cargo": cargo,
                    "celular": celular,
                    "ciudad": ciudad,
                    "tipoExamen": tipo_examen,
                    "fechaAtencion": fecha_atencion,
                    "horaAtencion": hora_atencion,
                    "medico": medico_asignado,
                    "empresa": empresa
                }

                personas_procesadas.append(persona)
                print(f"✅ Fila {idx} procesada: {nombre_completo}")

            except Exception as e:
                print(f"⚠️ Error procesando fila {idx}: {str(e)}")
                # Continuar con la siguiente fila
                personas_procesadas.append({
                    "fila": idx,
                    "error": str(e),
                    "datos_originales": dict(row)
                })

        print(f"✅ CSV procesado exitosamente. Total de registros: {len(personas_procesadas)}")

        # Ordenar registros: primero BOGOTA, luego por hora (de más temprano a más tarde)
        personas_procesadas.sort(key=lambda x: (x.get('ciudad', '') != 'BOGOTA', x.get('horaAtencion', '00:00')))

        print(f"✅ Registros ordenados: BOGOTA primero, luego por hora")

        # Preparar respuesta
        respuesta = {
            "success": True,
            "total_registros": len(personas_procesadas),
            "datos": personas_procesadas,
            "message": f"CSV procesado exitosamente. {len(personas_procesadas)} registros encontrados."
        }

        # Configurar headers CORS
        response = jsonify(respuesta)
        response.headers["Access-Control-Allow-Origin"] = "*"

        return response

    except Exception as e:
        print(f"❌ Error procesando CSV: {str(e)}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "error": str(e)
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"

        return error_response, 500

# --- Endpoint: MARCAR NÚMEROS CON STOPBOT ---
@app.route("/marcar-stopbot", methods=["POST", "OPTIONS"])
def marcar_stopbot():
    """
    Endpoint para marcar números de celular con stopBot = true en Wix CHATBOT.
    Recibe una lista de números con prefijo de país (sin el +) y los actualiza.

    Body JSON esperado:
    {
        "numeros": ["573001234567", "573109876543", ...]
    }

    Returns:
        JSON con el resultado de la operación
    """
    # Manejar preflight CORS
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print("📞 Iniciando marcado de stopBot para números de celular...")

        # Obtener datos del request
        data = request.get_json()
        numeros = data.get('numeros', [])

        if not numeros or not isinstance(numeros, list):
            raise Exception("Se requiere un array de números en el campo 'numeros'")

        print(f"📋 Total de números a procesar: {len(numeros)}")

        # Configuración de Wix
        wix_base_url = os.getenv('WIX_BASE_URL', 'https://www.bsl.com.co/_functions')

        resultados = {
            'exitosos': [],
            'fallidos': [],
            'total': len(numeros)
        }

        # Procesar cada número
        for numero in numeros:
            try:
                # Limpiar el número (remover espacios, caracteres especiales excepto números)
                numero_limpio = ''.join(filter(str.isdigit, str(numero)))

                if not numero_limpio:
                    print(f"⚠️ Número inválido (vacío): {numero}")
                    resultados['fallidos'].append({
                        'numero': numero,
                        'error': 'Número vacío o inválido'
                    })
                    continue

                # Asegurar que el número tenga prefijo de país (asumir Colombia 57 si no lo tiene)
                if len(numero_limpio) == 10:  # Número sin prefijo de país
                    numero_limpio = f"57{numero_limpio}"

                print(f"🔄 Procesando número: {numero_limpio}")

                # Llamar a la función de Wix para actualizar stopBot
                url = f"{wix_base_url}/marcarStopBot"
                payload = {
                    'userId': numero_limpio,
                    'stopBot': True
                }

                response = requests.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    print(f"✅ StopBot marcado exitosamente para: {numero_limpio}")
                    resultados['exitosos'].append(numero_limpio)
                else:
                    print(f"❌ Error al marcar stopBot para {numero_limpio}: {response.status_code}")
                    resultados['fallidos'].append({
                        'numero': numero_limpio,
                        'error': f'Error HTTP {response.status_code}'
                    })

            except Exception as e:
                print(f"❌ Error procesando número {numero}: {str(e)}")
                resultados['fallidos'].append({
                    'numero': numero,
                    'error': str(e)
                })

        print(f"✅ Proceso completado: {len(resultados['exitosos'])} exitosos, {len(resultados['fallidos'])} fallidos")

        # Preparar respuesta
        respuesta = {
            "success": True,
            "message": f"Proceso completado: {len(resultados['exitosos'])} números marcados exitosamente",
            "resultados": resultados
        }

        # Configurar headers CORS
        response = jsonify(respuesta)
        response.headers["Access-Control-Allow-Origin"] = "*"

        return response

    except Exception as e:
        print(f"❌ Error en marcar_stopbot: {str(e)}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "error": str(e)
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"

        return error_response, 500

# --- Endpoint: OBTENER IP DEL SERVIDOR ---
@app.route("/server-ip", methods=["GET"])
def server_ip():
    """Endpoint para obtener la IP pública del servidor"""
    try:
        ip = requests.get('https://api.ipify.org', timeout=5).text
        return jsonify({
            "server_public_ip": ip,
            "message": "Autoriza esta IP en Digital Ocean PostgreSQL"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Endpoint: EXPLORAR POSTGRESQL ---
@app.route("/test-certificado-postgres/<wix_id>", methods=["GET", "OPTIONS"])
def test_certificado_postgres(wix_id):
    """
    Endpoint de prueba para generar certificado usando foto de PostgreSQL
    en lugar de Wix CDN
    """
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()

    try:
        import psycopg2

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            return jsonify({
                "success": False,
                "error": "POSTGRES_PASSWORD no configurada"
            }), 500

        # Conectar a PostgreSQL
        print(f"🔌 Conectando a PostgreSQL para wix_id: {wix_id}")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor()

        # Buscar el registro por wix_id
        print(f"🔍 Buscando registro con wix_id: {wix_id}")
        cur.execute("""
            SELECT
                id, primer_nombre, segundo_nombre, primer_apellido, segundo_apellido,
                numero_id, cargo, empresa, cod_empresa, foto, wix_id
            FROM formularios
            WHERE wix_id = %s
            LIMIT 1;
        """, (wix_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            return jsonify({
                "success": False,
                "error": f"No se encontró registro con wix_id: {wix_id}"
            }), 404

        # Extraer datos
        (
            db_id, primer_nombre, segundo_nombre, primer_apellido, segundo_apellido,
            numero_id, cargo, empresa, cod_empresa, foto, db_wix_id
        ) = row

        print(f"✅ Registro encontrado: {primer_nombre} {primer_apellido}")
        print(f"📸 Foto length: {len(foto) if foto else 0} caracteres")

        # Preparar datos del certificado (ejemplo simple)
        from datetime import datetime
        fecha_actual = datetime.now()

        datos_certificado = {
            "nombres_apellidos": f"{primer_nombre or ''} {segundo_nombre or ''} {primer_apellido or ''} {segundo_apellido or ''}".strip(),
            "documento_identidad": numero_id or "Sin documento",
            "cargo": cargo or "No especificado",
            "empresa": empresa or "No especificada",
            "cod_empresa": cod_empresa or "",
            "foto_paciente": foto,  # Data URI base64 desde PostgreSQL

            # Datos mínimos requeridos para el template
            "fecha_nacimiento": "",
            "edad": "N/A",
            "genero": "N/A",
            "direccion": "",
            "ciudad": "",
            "telefono": "",
            "celular": "",
            "estado_civil": "",
            "hijos": "0",
            "profesion": "",
            "email": "",
            "tipo_examen": "Prueba PostgreSQL",

            "examenes_realizados": [
                {"nombre": "Examen Médico Osteomuscular", "fecha": formatear_fecha_espanol(fecha_actual)}
            ],

            "resultados_generales": [{
                "categoria": "Prueba",
                "resultado": "Normal",
                "observaciones": "Certificado de prueba usando foto de PostgreSQL"
            }],

            "concepto_medico": "APTO para desempeñar el cargo (PRUEBA PostgreSQL)",
            "recomendaciones": "Ninguna (certificado de prueba)",

            "medico_nombre": "Dr. Juan Pérez",
            "medico_firma": "/static/images/firma_medico.png",
            "medico_registro": "RM 12345",

            "codigo_seguridad": f"TEST-PG-{wix_id[:8]}",
            "fecha_emision": formatear_fecha_espanol(fecha_actual),
            "mostrar_sin_soporte": False,

            "qr_code_base64": None  # Por ahora sin QR
        }

        # Renderizar template
        print("🎨 Renderizando template...")
        html_content = render_template("certificado_medico.html", **datos_certificado)

        # Guardar HTML en archivo temporal para Puppeteer
        print("💾 Guardando HTML temporal...")
        temp_html = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode='w', encoding='utf-8')
        temp_html.write(html_content)
        temp_html.close()
        temp_filename = os.path.basename(temp_html.name)

        # Guardar referencia al archivo temporal para el endpoint /temp-html/
        if not hasattr(app, 'temp_html_files'):
            app.temp_html_files = {}
        app.temp_html_files[temp_filename] = temp_html.name

        # Construir URL para Puppeteer
        base_url = os.getenv("BASE_URL", "https://bsl-utilidades-yp78a.ondigitalocean.app")
        html_url = f"{base_url}/temp-html/{temp_filename}"

        # Generar PDF con Puppeteer
        print("🎭 Generando PDF con Puppeteer...")
        pdf_content = puppeteer_html_to_pdf_from_url(
            html_url=html_url,
            output_filename=f"test_certificado_postgres_{wix_id}"
        )

        # Limpiar archivo HTML temporal
        try:
            os.unlink(temp_html.name)
            if temp_filename in app.temp_html_files:
                del app.temp_html_files[temp_filename]
        except Exception as cleanup_error:
            print(f"⚠️ Error limpiando archivo HTML temporal: {cleanup_error}")

        # Guardar PDF temporalmente
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_pdf.write(pdf_content)
        temp_pdf.close()

        print(f"✅ PDF generado: {temp_pdf.name} ({len(pdf_content)} bytes)")

        return jsonify({
            "success": True,
            "message": "PDF generado exitosamente usando foto de PostgreSQL",
            "pdf_path": temp_pdf.name,
            "pdf_size_bytes": len(pdf_content),
            "foto_size_chars": len(foto) if foto else 0,
            "foto_preview": foto[:100] if foto else None,
            "paciente": {
                "nombre": datos_certificado["nombres_apellidos"],
                "documento": numero_id,
                "cargo": cargo,
                "empresa": empresa
            }
        })

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/explore-postgres", methods=["GET"])
def explore_postgres():
    """Endpoint para explorar la estructura de PostgreSQL"""
    try:
        import psycopg2

        # Conectar a PostgreSQL usando variables de entorno
        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            return jsonify({"success": False, "error": "POSTGRES_PASSWORD no configurado"}), 500

        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require",
            connect_timeout=10
        )

        cur = conn.cursor()

        resultado = {
            "success": True,
            "tablas": [],
            "detalles": {}
        }

        # Listar todas las tablas
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cur.fetchall()

        for table in tables:
            table_name = table[0]
            resultado["tablas"].append(table_name)

            # Obtener estructura de cada tabla
            cur.execute(f"""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            columns = cur.fetchall()

            # Contar registros
            cur.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cur.fetchone()[0]

            resultado["detalles"][table_name] = {
                "columnas": [
                    {
                        "nombre": col[0],
                        "tipo": col[1],
                        "max_length": col[2]
                    }
                    for col in columns
                ],
                "total_registros": count
            }

        cur.close()
        conn.close()

        return jsonify(resultado)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

# --- Endpoint: TEST PUPPETEER DESCARGA SIMPLE ---
@app.route("/test-puppeteer-imagen/<wix_id>", methods=["GET", "OPTIONS"])
def test_puppeteer_imagen(wix_id):
    """
    Endpoint de prueba SOLO para verificar que Puppeteer descarga correctamente la imagen

    Args:
        wix_id: ID del registro en Wix

    Returns:
        JSON con información detallada del proceso de descarga con Puppeteer
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print(f"\n{'='*60}")
        print(f"🎭 TEST PUPPETEER: Descarga de imagen Wix")
        print(f"📋 Wix ID: {wix_id}")
        print(f"{'='*60}\n")

        resultado = {
            "success": False,
            "wix_id": wix_id,
            "pasos": [],
            "foto_url_wix": None,
            "bytes_descargados": 0,
            "content_type": None,
            "errores": []
        }

        # PASO 1: Obtener URL de foto
        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")

        print("📡 PASO 1: Obteniendo URL de foto desde Wix...")
        resultado["pasos"].append("1. Obteniendo URL de foto desde Wix...")

        try:
            # Consultar historia clínica
            response = requests.get(f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}", timeout=10)
            if response.status_code != 200:
                raise Exception(f"Error consultando historia clínica: {response.status_code}")

            datos_wix = response.json().get("data", {})
            wix_id_historia = datos_wix.get('_id')

            # Consultar formulario desde PostgreSQL
            datos_formulario = obtener_datos_formulario_postgres(wix_id_historia)

            if not datos_formulario:
                raise Exception("No se encontraron datos del formulario en PostgreSQL")

            foto_url_original = datos_formulario.get('foto')

            if not foto_url_original:
                raise Exception("No se encontró foto en PostgreSQL")

            # Convertir URL
            if foto_url_original.startswith('wix:image://v1/'):
                parts = foto_url_original.replace('wix:image://v1/', '').split('/')
                if len(parts) > 0:
                    image_id = parts[0]
                    foto_url_wix_cdn = f"https://static.wixstatic.com/media/{image_id}"
            else:
                foto_url_wix_cdn = foto_url_original

            resultado["foto_url_wix"] = foto_url_wix_cdn
            resultado["pasos"].append(f"   ✅ URL obtenida: {foto_url_wix_cdn[:80]}...")
            print(f"   ✅ URL: {foto_url_wix_cdn}")

        except Exception as e:
            error_msg = f"Error obteniendo URL: {str(e)}"
            resultado["errores"].append(error_msg)
            resultado["pasos"].append(f"   ❌ {error_msg}")
            print(f"   ❌ {error_msg}")
            return jsonify(resultado), 500

        # PASO 2: Descargar con Puppeteer
        print("\n🎭 PASO 2: Descargando imagen con Puppeteer...")
        resultado["pasos"].append("2. Descargando con Puppeteer (nueva estrategia HTML)...")

        try:
            image_bytes, content_type = descargar_imagen_wix_con_puppeteer(foto_url_wix_cdn)

            if image_bytes and len(image_bytes) > 1000:
                resultado["success"] = True
                resultado["bytes_descargados"] = len(image_bytes)
                resultado["content_type"] = content_type
                resultado["pasos"].append(f"   ✅ Imagen descargada: {len(image_bytes):,} bytes")
                resultado["pasos"].append(f"   ✅ Tipo: {content_type}")
                print(f"   ✅ Descargado: {len(image_bytes):,} bytes ({content_type})")

                # Info adicional
                kb_size = len(image_bytes) / 1024
                mb_size = kb_size / 1024
                if mb_size >= 1:
                    resultado["pasos"].append(f"   📊 Tamaño: {mb_size:.2f} MB")
                else:
                    resultado["pasos"].append(f"   📊 Tamaño: {kb_size:.2f} KB")
            else:
                bytes_count = len(image_bytes) if image_bytes else 0
                error_msg = f"Imagen inválida o muy pequeña ({bytes_count} bytes)"
                resultado["errores"].append(error_msg)
                resultado["pasos"].append(f"   ❌ {error_msg}")
                resultado["bytes_descargados"] = bytes_count
                print(f"   ❌ {error_msg}")

        except Exception as e:
            error_msg = f"Error en Puppeteer: {str(e)}"
            resultado["errores"].append(error_msg)
            resultado["pasos"].append(f"   ❌ {error_msg}")
            print(f"   ❌ {error_msg}")
            traceback.print_exc()

        # Resumen
        print(f"\n{'='*60}")
        if resultado["success"]:
            print(f"✅ TEST EXITOSO")
            print(f"📸 URL: {resultado['foto_url_wix'][:80]}...")
            print(f"📊 Bytes: {resultado['bytes_descargados']:,}")
            print(f"🏷️  Tipo: {resultado['content_type']}")
        else:
            print(f"❌ TEST FALLIDO")
            print(f"Errores: {resultado['errores']}")
        print(f"{'='*60}\n")

        response = jsonify(resultado)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response, 200 if resultado["success"] else 500

    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {str(e)}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "wix_id": wix_id,
            "error": f"Error crítico: {str(e)}",
            "pasos": ["Error crítico antes de completar el test"]
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"
        return error_response, 500


# --- Endpoint: GUARDAR FOTO DESDE WIX A DO SPACES (TEST) ---
@app.route("/guardar-foto-desde-wix-do/<wix_id>", methods=["GET", "OPTIONS"])
def guardar_foto_desde_wix_do(wix_id):
    """
    Endpoint de prueba para diagnosticar descarga de fotos de Wix a DO Spaces

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Returns:
        JSON con información detallada del proceso de descarga
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print(f"\n{'='*60}")
        print(f"🧪 TEST: Guardar foto desde Wix a DO Spaces")
        print(f"📋 Wix ID: {wix_id}")
        print(f"{'='*60}\n")

        resultado = {
            "success": False,
            "wix_id": wix_id,
            "pasos": [],
            "foto_url_wix": None,
            "foto_url_do_spaces": None,
            "errores": []
        }

        # PASO 1: Obtener datos desde Wix
        resultado["pasos"].append("1. Consultando datos desde Wix HTTP Function...")
        print("📡 PASO 1: Consultando Wix HTTP Function...")

        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")
        wix_url = f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}"

        print(f"   URL: {wix_url}")

        try:
            response = requests.get(wix_url, timeout=10)
            print(f"   Status: {response.status_code}")

            if response.status_code != 200:
                error_msg = f"Error HTTP {response.status_code} al consultar Wix"
                resultado["errores"].append(error_msg)
                resultado["pasos"].append(f"   ❌ {error_msg}")
                return jsonify(resultado), 500

            wix_response = response.json()
            datos_wix = wix_response.get("data", {})

            if not datos_wix:
                error_msg = "Wix retornó respuesta vacía"
                resultado["errores"].append(error_msg)
                resultado["pasos"].append(f"   ❌ {error_msg}")
                return jsonify(resultado), 404

            resultado["pasos"].append(f"   ✅ Datos obtenidos exitosamente")
            print(f"   ✅ Datos obtenidos: {datos_wix.get('primerNombre', '')} {datos_wix.get('primerApellido', '')}")

        except Exception as e:
            error_msg = f"Error de conexión con Wix: {str(e)}"
            resultado["errores"].append(error_msg)
            resultado["pasos"].append(f"   ❌ {error_msg}")
            return jsonify(resultado), 500

        # PASO 2: Buscar foto en múltiples lugares
        resultado["pasos"].append("2. Buscando foto del paciente...")
        print("\n📝 PASO 2: Buscando foto del paciente...")

        wix_id_historia = datos_wix.get('_id')
        foto_url_original = None
        foto_url_wix_cdn = None

        # INTENTO 2A: Buscar en datos principales de historia clínica
        print("\n   2A. Revisando datos principales de historia clínica...")
        resultado["pasos"].append("   2A. Revisando datos principales...")

        # Revisar campos posibles donde puede estar la foto
        campos_foto = ['foto', 'fotoPaciente', 'foto_paciente', 'imagen', 'photo']
        for campo in campos_foto:
            if datos_wix.get(campo):
                foto_url_original = datos_wix.get(campo)
                resultado["pasos"].append(f"      ✅ Foto encontrada en campo '{campo}'")
                print(f"      ✅ Foto encontrada en campo '{campo}': {foto_url_original[:100]}...")
                break

        # INTENTO 2B: Buscar en formulario (solo si no se encontró antes)
        if not foto_url_original:
            print("\n   2B. Consultando formulario por idGeneral...")
            resultado["pasos"].append("   2B. Consultando formulario por idGeneral...")

            try:
                print(f"      Consultando PostgreSQL para wix_id={wix_id_historia}")

                datos_formulario = obtener_datos_formulario_postgres(wix_id_historia)

                if datos_formulario:
                    print(f"      ✅ Datos del formulario encontrados en PostgreSQL")

                    if datos_formulario.get('foto'):
                        foto_url_original = datos_formulario.get('foto')
                        resultado["pasos"].append(f"      ✅ Foto encontrada en PostgreSQL")
                        print(f"      ✅ Foto en PostgreSQL: {foto_url_original[:100]}...")
                    else:
                        resultado["pasos"].append(f"      ℹ️  Formulario sin foto")
                        print(f"      ℹ️  Formulario existe pero no tiene foto")
                        print(f"      📋 Campos disponibles: {list(datos_formulario.keys())}")
                else:
                    resultado["pasos"].append(f"      ℹ️  Formulario no encontrado en PostgreSQL para wix_id={wix_id_historia}")
                    print(f"      ℹ️  Formulario no encontrado en PostgreSQL")

            except Exception as e:
                resultado["pasos"].append(f"      ⚠️  Error consultando PostgreSQL: {str(e)}")
                print(f"      ⚠️  Error consultando PostgreSQL: {e}")
                traceback.print_exc()

        # Validar si se encontró foto
        if not foto_url_original:
            error_msg = "No se encontró foto del paciente en ningún lugar"
            resultado["errores"].append(error_msg)
            resultado["pasos"].append(f"\n   ❌ {error_msg}")
            print(f"\n   ❌ {error_msg}")
            print(f"   📋 Campos disponibles en datos: {list(datos_wix.keys())[:20]}")
            return jsonify(resultado), 404

        # Convertir URL de Wix si es necesario
        print(f"\n   🔄 Procesando URL de foto...")
        resultado["pasos"].append("   🔄 Procesando URL...")

        if foto_url_original.startswith('wix:image://v1/'):
            parts = foto_url_original.replace('wix:image://v1/', '').split('/')
            if len(parts) > 0:
                image_id = parts[0]
                foto_url_wix_cdn = f"https://static.wixstatic.com/media/{image_id}"
                resultado["pasos"].append(f"      ✅ Convertida de wix:image:// a CDN URL")
                print(f"      ✅ URL CDN: {foto_url_wix_cdn}")
        elif 'static.wixstatic.com' in foto_url_original:
            foto_url_wix_cdn = foto_url_original
            resultado["pasos"].append(f"      ℹ️  Ya es una URL de Wix CDN")
            print(f"      ℹ️  Ya es URL CDN")
        else:
            foto_url_wix_cdn = foto_url_original
            resultado["pasos"].append(f"      ℹ️  URL no es de Wix CDN (tipo: {foto_url_original[:50]}...)")
            print(f"      ℹ️  URL no es de Wix CDN")

        resultado["foto_url_wix"] = foto_url_wix_cdn

        # PASO 3: Descargar y subir a DO Spaces (SIN PUPPETEER - SOLO REQUESTS)
        resultado["pasos"].append("3. Descargando imagen con requests simple...")
        print(f"\n📥 PASO 3: Descargando imagen con requests (sin Puppeteer)...")
        print(f"   URL a descargar: {foto_url_wix_cdn}")

        try:
            # Headers básicos de navegador
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': 'https://www.bsl.com.co/',
            }

            # Descargar imagen con requests
            resultado["pasos"].append("   🌐 Descargando con requests + headers navegador...")
            print(f"   🌐 Descargando con requests...")

            response = requests.get(foto_url_wix_cdn, headers=headers, timeout=15)
            print(f"   📊 Status: {response.status_code}")
            resultado["pasos"].append(f"      Status HTTP: {response.status_code}")

            if response.status_code == 200:
                image_bytes = response.content
                content_type = response.headers.get('Content-Type', 'image/jpeg')

                print(f"   ✅ Imagen descargada: {len(image_bytes)} bytes, tipo: {content_type}")
                resultado["pasos"].append(f"      ✅ Descargada: {len(image_bytes)} bytes ({content_type})")

                # Subir a DO Spaces
                resultado["pasos"].append("   ☁️  Subiendo a Digital Ocean Spaces...")
                print(f"   ☁️  Subiendo a DO Spaces...")

                # Generar nombre único
                image_id = uuid.uuid4().hex[:12]
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = 'jpg'
                elif 'png' in content_type:
                    ext = 'png'
                elif 'webp' in content_type:
                    ext = 'webp'
                else:
                    ext = 'jpg'

                filename = f"wix-img-{image_id}.{ext}"

                # Subir
                do_spaces_url = subir_imagen_a_do_spaces(image_bytes, filename, content_type)

                if do_spaces_url:
                    resultado["success"] = True
                    resultado["foto_url_do_spaces"] = do_spaces_url
                    resultado["pasos"].append(f"      ✅ Subida exitosa a DO Spaces")
                    print(f"   ✅ URL DO Spaces: {do_spaces_url}")
                else:
                    error_msg = "Error subiendo a DO Spaces (retornó None)"
                    resultado["errores"].append(error_msg)
                    resultado["pasos"].append(f"      ❌ {error_msg}")
                    print(f"   ❌ {error_msg}")

            elif response.status_code == 403:
                error_msg = f"Wix CDN bloqueó la descarga (403 Forbidden)"
                resultado["errores"].append(error_msg)
                resultado["pasos"].append(f"   ❌ {error_msg}")
                print(f"   ❌ {error_msg}")
                print(f"   💡 Nota: Este endpoint NO usa Puppeteer, solo requests")
            else:
                error_msg = f"Error HTTP {response.status_code} al descargar"
                resultado["errores"].append(error_msg)
                resultado["pasos"].append(f"   ❌ {error_msg}")
                print(f"   ❌ {error_msg}")

        except requests.exceptions.Timeout:
            error_msg = "Timeout descargando imagen (>15s)"
            resultado["errores"].append(error_msg)
            resultado["pasos"].append(f"   ❌ {error_msg}")
            print(f"   ❌ {error_msg}")
        except Exception as e:
            error_msg = f"Error en descarga/subida: {str(e)}"
            resultado["errores"].append(error_msg)
            resultado["pasos"].append(f"   ❌ {error_msg}")
            print(f"   ❌ {error_msg}")
            traceback.print_exc()

        # Resumen final
        print(f"\n{'='*60}")
        if resultado["success"]:
            print(f"✅ TEST EXITOSO")
            print(f"📸 Foto Wix: {resultado['foto_url_wix'][:80]}...")
            print(f"☁️  Foto DO Spaces: {resultado['foto_url_do_spaces']}")
        else:
            print(f"❌ TEST FALLIDO")
            print(f"Errores: {resultado['errores']}")
        print(f"{'='*60}\n")

        response = jsonify(resultado)
        response.headers["Access-Control-Allow-Origin"] = "*"

        return response, 200 if resultado["success"] else 500

    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO EN TEST: {str(e)}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "wix_id": wix_id,
            "error": f"Error crítico: {str(e)}",
            "pasos": ["Error crítico antes de completar el test"]
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"

        return error_response, 500


# --- Endpoint: GENERAR CERTIFICADO DESDE ID DE WIX ---
@app.route("/generar-certificado-desde-wix/<wix_id>", methods=["GET", "OPTIONS"])
def generar_certificado_desde_wix(wix_id):
    """
    Endpoint que muestra loader mientras se genera el certificado

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Query params opcionales:
        guardar_drive: true/false (default: false)
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    # Mostrar página de loader
    return render_template('certificado_loader.html', wix_id=wix_id)


@app.route("/generar-certificado-desde-wix-puppeteer/<wix_id>", methods=["GET", "OPTIONS"])
def generar_certificado_desde_wix_puppeteer(wix_id):
    """
    Endpoint que genera certificado con Puppeteer (alias conveniente)

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Query params opcionales:
        guardar_drive: true/false (default: false)
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    # Redirigir al endpoint principal (ahora solo usa Puppeteer)
    guardar_drive = request.args.get('guardar_drive', 'false')
    return redirect(f"/api/generar-certificado-pdf/{wix_id}?guardar_drive={guardar_drive}")


@app.route("/api/generar-certificado-pdf/<wix_id>", methods=["GET", "OPTIONS"])
def api_generar_certificado_pdf(wix_id):
    """
    Endpoint API que genera el PDF del certificado (usado por el loader en background)

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Query params opcionales:
        guardar_drive: true/false (default: false)
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print(f"📋 Generando certificado desde Wix ID: {wix_id}")

        # Obtener parámetros opcionales
        guardar_drive = request.args.get('guardar_drive', 'false').lower() == 'true'

        print(f"🔧 Motor de conversión: Puppeteer")

        # ===== PRIORIDAD 1: CONSULTAR DATOS DESDE POSTGRESQL =====
        print(f"🔍 [PRIORIDAD 1] Consultando PostgreSQL para wix_id: {wix_id}")
        datos_postgres = obtener_datos_formulario_postgres(wix_id)

        # ===== PRIORIDAD 2: CONSULTAR DATOS DESDE WIX (COMPLEMENTO) =====
        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")
        print(f"🔍 [PRIORIDAD 2] Consultando Wix HTTP Function: {wix_base_url}/historiaClinicaPorId?_id={wix_id}")

        datos_wix = {}
        try:
            # Llamar al endpoint de Wix
            wix_url = f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}"
            response = requests.get(wix_url, timeout=10)

            print(f"📡 Respuesta Wix: {response.status_code}")

            if response.status_code == 200:
                wix_response = response.json()
                datos_wix = wix_response.get("data", {})

                if not datos_wix:
                    print(f"⚠️ Wix retornó respuesta vacía, usando solo datos de PostgreSQL")
                else:
                    print(f"✅ Datos obtenidos de Wix para ID: {wix_id}")
                    print(f"📋 Paciente Wix: {datos_wix.get('primerNombre', '')} {datos_wix.get('primerApellido', '')}")
            else:
                print(f"⚠️ Error consultando Wix: {response.status_code}, usando solo PostgreSQL")

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Error de conexión con Wix: {e}, usando solo PostgreSQL")
            traceback.print_exc()

        # ===== MERGE DE DATOS: PostgreSQL SOBRESCRIBE A WIX =====
        print(f"🔄 Haciendo merge de datos: PostgreSQL (prioridad) → Wix (complemento)")

        if datos_postgres:
            print(f"✅ Datos de PostgreSQL disponibles, sobrescribiendo datos de Wix...")
            # PostgreSQL sobrescribe TODOS los campos que tenga
            if datos_postgres.get('eps'):
                datos_wix['eps'] = datos_postgres.get('eps')
                print(f"  ✓ EPS: {datos_postgres.get('eps')}")
            if datos_postgres.get('arl'):
                datos_wix['arl'] = datos_postgres.get('arl')
                print(f"  ✓ ARL: {datos_postgres.get('arl')}")
            if datos_postgres.get('pensiones'):
                datos_wix['pensiones'] = datos_postgres.get('pensiones')
                print(f"  ✓ Pensiones: {datos_postgres.get('pensiones')}")
            if datos_postgres.get('nivelEducativo'):
                datos_wix['nivel_educativo'] = datos_postgres.get('nivelEducativo')
                print(f"  ✓ Nivel Educativo: {datos_postgres.get('nivelEducativo')}")
            if datos_postgres.get('edad'):
                datos_wix['edad'] = datos_postgres.get('edad')
            if datos_postgres.get('genero'):
                datos_wix['genero'] = datos_postgres.get('genero')
            if datos_postgres.get('estadoCivil'):
                datos_wix['estadoCivil'] = datos_postgres.get('estadoCivil')
            if datos_postgres.get('hijos'):
                datos_wix['hijos'] = datos_postgres.get('hijos')
            if datos_postgres.get('email'):
                datos_wix['email'] = datos_postgres.get('email')
            if datos_postgres.get('celular'):
                datos_wix['celular'] = datos_postgres.get('celular')
                print(f"  ✓ Celular: {datos_postgres.get('celular')}")
            if datos_postgres.get('profesionUOficio'):
                datos_wix['profesionUOficio'] = datos_postgres.get('profesionUOficio')
            if datos_postgres.get('ciudadDeResidencia'):
                datos_wix['ciudadDeResidencia'] = datos_postgres.get('ciudadDeResidencia')
            if datos_postgres.get('fechaNacimiento'):
                datos_wix['fechaNacimiento'] = datos_postgres.get('fechaNacimiento')
            if datos_postgres.get('foto'):
                datos_wix['foto_paciente'] = datos_postgres.get('foto')
                print(f"  ✓ Foto: disponible desde PostgreSQL")
            if datos_postgres.get('firma'):
                datos_wix['firma_paciente'] = datos_postgres.get('firma')
                print(f"  ✓ Firma: disponible desde PostgreSQL")

            print(f"📊 Merge completado: edad={datos_wix.get('edad')}, genero={datos_wix.get('genero')}, eps={datos_wix.get('eps')}, arl={datos_wix.get('arl')}")
        else:
            print(f"⚠️ No hay datos de PostgreSQL (formularios), usando solo datos de Wix")

        # ===== PRIORIDAD 0: CONSULTAR HISTORIA CLÍNICA DESDE POSTGRESQL (EXÁMENES) =====
        print(f"🔍 [PRIORIDAD 0] Consultando HistoriaClinica en PostgreSQL para wix_id: {wix_id}")
        datos_historia_postgres = obtener_datos_historia_clinica_postgres(wix_id)

        if datos_historia_postgres:
            print(f"✅ Datos de HistoriaClinica PostgreSQL disponibles, sobrescribiendo...")
            # Sobrescribir campos de HistoriaClinica desde PostgreSQL
            if datos_historia_postgres.get('examenes'):
                datos_wix['examenes'] = datos_historia_postgres.get('examenes')
                print(f"  ✓ Exámenes (PostgreSQL): {datos_historia_postgres.get('examenes')}")
            if datos_historia_postgres.get('primerNombre'):
                datos_wix['primerNombre'] = datos_historia_postgres.get('primerNombre')
            if datos_historia_postgres.get('segundoNombre'):
                datos_wix['segundoNombre'] = datos_historia_postgres.get('segundoNombre')
            if datos_historia_postgres.get('primerApellido'):
                datos_wix['primerApellido'] = datos_historia_postgres.get('primerApellido')
            if datos_historia_postgres.get('segundoApellido'):
                datos_wix['segundoApellido'] = datos_historia_postgres.get('segundoApellido')
            if datos_historia_postgres.get('numeroId'):
                datos_wix['numeroId'] = datos_historia_postgres.get('numeroId')
            if datos_historia_postgres.get('codEmpresa'):
                datos_wix['codEmpresa'] = datos_historia_postgres.get('codEmpresa')
            if datos_historia_postgres.get('empresa'):
                datos_wix['empresa'] = datos_historia_postgres.get('empresa')
            if datos_historia_postgres.get('cargo'):
                datos_wix['cargo'] = datos_historia_postgres.get('cargo')
            if datos_historia_postgres.get('tipoExamen'):
                datos_wix['tipoExamen'] = datos_historia_postgres.get('tipoExamen')
            if datos_historia_postgres.get('mdConceptoFinal'):
                datos_wix['mdConceptoFinal'] = datos_historia_postgres.get('mdConceptoFinal')
            if datos_historia_postgres.get('mdObservacionesCertificado'):
                datos_wix['mdObservacionesCertificado'] = datos_historia_postgres.get('mdObservacionesCertificado')
            if datos_historia_postgres.get('mdRecomendacionesMedicasAdicionales'):
                datos_wix['mdRecomendacionesMedicasAdicionales'] = datos_historia_postgres.get('mdRecomendacionesMedicasAdicionales')
            if datos_historia_postgres.get('mdAntecedentes'):
                datos_wix['mdAntecedentes'] = datos_historia_postgres.get('mdAntecedentes')
            if datos_historia_postgres.get('fechaConsulta'):
                datos_wix['fechaConsulta'] = datos_historia_postgres.get('fechaConsulta')
            if datos_historia_postgres.get('pvEstado'):
                datos_wix['pvEstado'] = datos_historia_postgres.get('pvEstado')
            if datos_historia_postgres.get('pagado'):
                datos_wix['pagado'] = datos_historia_postgres.get('pagado')
            if datos_historia_postgres.get('medico'):
                datos_wix['medico'] = datos_historia_postgres.get('medico')
                print(f"  ✓ Médico (PostgreSQL HistoriaClinica): {datos_historia_postgres.get('medico')}")
            if datos_historia_postgres.get('ciudad'):
                datos_wix['ciudad'] = datos_historia_postgres.get('ciudad')
                print(f"  ✓ Ciudad (PostgreSQL HistoriaClinica): {datos_historia_postgres.get('ciudad')}")
        else:
            print(f"⚠️ No hay datos de HistoriaClinica en PostgreSQL para wix_id: {wix_id}")

        # Transformar datos de Wix al formato del endpoint de certificado
        nombre_completo = f"{datos_wix.get('primerNombre', '')} {datos_wix.get('segundoNombre', '')} {datos_wix.get('primerApellido', '')} {datos_wix.get('segundoApellido', '')}".strip()

        fecha_consulta = datos_wix.get('fechaConsulta')
        if isinstance(fecha_consulta, datetime):
            fecha_formateada = formatear_fecha_espanol(fecha_consulta)
        elif isinstance(fecha_consulta, str):
            # Parsear fecha ISO de Wix (ej: "2025-09-30T16:31:00.927Z")
            try:
                fecha_obj = datetime.fromisoformat(fecha_consulta.replace('Z', '+00:00'))
                fecha_formateada = formatear_fecha_espanol(fecha_obj)
            except (ValueError, AttributeError):
                fecha_formateada = formatear_fecha_espanol(datetime.now())
        else:
            fecha_formateada = formatear_fecha_espanol(datetime.now())

        # Construir exámenes realizados
        # Normalizar lista de exámenes (convierte string a array si viene de PostgreSQL)
        examenes = normalizar_lista_examenes(datos_wix.get('examenes', []))
        print(f"📋 Exámenes antes de normalizar: {examenes}")
        examenes_normalizados = [normalizar_examen(e) for e in examenes]
        print(f"📋 Exámenes normalizados: {examenes_normalizados}")

        examenes_realizados = []
        for examen in examenes_normalizados:
            examenes_realizados.append({
                "nombre": examen,
                "fecha": fecha_formateada
            })

        # ===== CONSULTAR DATOS VISUALES (Optometría/Visiometría) =====
        datos_visual = None
        # examenes y examenes_normalizados ya están definidos arriba (ahora en MAYÚSCULAS)
        tiene_examen_visual = any(e in ['OPTOMETRÍA', 'VISIOMETRÍA', 'Optometría', 'Visiometría'] for e in examenes_normalizados)

        if tiene_examen_visual:
            wix_id_historia = datos_wix.get('_id', '')

            # PRIORIDAD 1: Consultar PostgreSQL - visiometrias_virtual (examen virtual)
            print(f"🔍 [PRIORIDAD 1] Consultando visiometrias_virtual en PostgreSQL para: {wix_id_historia}")
            datos_visual = obtener_visiometria_postgres(wix_id_historia)

            # PRIORIDAD 2: Consultar PostgreSQL - visiometrias (optometría profesional)
            if not datos_visual:
                print(f"🔍 [PRIORIDAD 2] Consultando visiometrias (optometría) en PostgreSQL...")
                datos_visual = obtener_optometria_postgres(wix_id_historia)

            # PRIORIDAD 3: Fallback a Wix si PostgreSQL no tiene datos
            if not datos_visual:
                print(f"🔍 [PRIORIDAD 3 - Fallback] Consultando datos visuales en Wix...")
                try:
                    visual_url = f"https://www.bsl.com.co/_functions/visualPorIdGeneral?idGeneral={wix_id_historia}"

                    visual_response = requests.get(visual_url, timeout=10)

                    if visual_response.status_code == 200:
                        visual_data = visual_response.json()
                        if visual_data.get('success') and visual_data.get('data'):
                            datos_visual = visual_data['data'][0] if len(visual_data['data']) > 0 else None
                            print(f"✅ Datos visuales obtenidos desde Wix (fallback)")
                        else:
                            print(f"⚠️ No se encontraron datos visuales en Wix para {wix_id_historia}")
                    else:
                        print(f"⚠️ Error al consultar datos visuales en Wix: {visual_response.status_code}")
                except Exception as e:
                    print(f"❌ Error consultando datos visuales en Wix: {e}")

        # ===== CONSULTAR DATOS DE AUDIOMETRÍA =====
        datos_audiometria = None
        tiene_examen_audio = any(e in ['AUDIOMETRÍA', 'Audiometría'] for e in examenes_normalizados)

        if tiene_examen_audio:
            wix_id_historia = datos_wix.get('_id', '')

            # PRIORIDAD 1: Consultar PostgreSQL (audiometrias)
            print(f"🔍 [PRIORIDAD 1] Consultando audiometrias en PostgreSQL para: {wix_id_historia}")
            datos_audiometria = obtener_audiometria_postgres(wix_id_historia)

            # PRIORIDAD 2: Fallback a Wix si PostgreSQL no tiene datos
            if not datos_audiometria:
                print(f"🔍 [PRIORIDAD 2 - Fallback] Consultando datos de audiometría en Wix...")
                try:
                    audio_url = f"https://www.bsl.com.co/_functions/audiometriaPorIdGeneral?idGeneral={wix_id_historia}"

                    audio_response = requests.get(audio_url, timeout=10)

                    if audio_response.status_code == 200:
                        audio_data = audio_response.json()
                        if audio_data.get('success') and audio_data.get('data'):
                            datos_raw = audio_data['data'][0] if len(audio_data['data']) > 0 else None

                            if datos_raw:
                                # Transformar datos de Wix al formato esperado
                                frecuencias = [250, 500, 1000, 2000, 3000, 4000, 6000, 8000]
                                datosParaTabla = []

                                for freq in frecuencias:
                                    campo_der = f"auDer{freq}"
                                    campo_izq = f"auIzq{freq}"
                                    datosParaTabla.append({
                                        "frecuencia": freq,
                                        "oidoDerecho": datos_raw.get(campo_der, 0),
                                        "oidoIzquierdo": datos_raw.get(campo_izq, 0)
                                    })

                                # Calcular diagnóstico automático basado en umbrales auditivos
                                def calcular_diagnostico_audiometria(datos):
                                    # Detectar umbrales anormalmente bajos (por debajo de 0 dB)
                                    umbrales_bajos_der = [d for d in datos if d['oidoDerecho'] < 0]
                                    umbrales_bajos_izq = [d for d in datos if d['oidoIzquierdo'] < 0]
                                    tiene_umbrales_bajos = len(umbrales_bajos_der) > 0 or len(umbrales_bajos_izq) > 0

                                    # Promedios de frecuencias conversacionales (500, 1000, 2000 Hz)
                                    freq_conv_indices = [1, 2, 3]  # índices para 500, 1000, 2000 Hz
                                    valores_der = [datos[i]['oidoDerecho'] for i in freq_conv_indices]
                                    valores_izq = [datos[i]['oidoIzquierdo'] for i in freq_conv_indices]

                                    prom_der = sum(valores_der) / len(valores_der)
                                    prom_izq = sum(valores_izq) / len(valores_izq)

                                    def clasificar_umbral(umbral):
                                        if umbral <= 25:
                                            return "Normal"
                                        elif umbral <= 40:
                                            return "Leve"
                                        elif umbral <= 55:
                                            return "Moderada"
                                        elif umbral <= 70:
                                            return "Moderadamente Severa"
                                        elif umbral <= 90:
                                            return "Severa"
                                        else:
                                            return "Profunda"

                                    clasif_der = clasificar_umbral(prom_der)
                                    clasif_izq = clasificar_umbral(prom_izq)

                                    # Verificar pérdida en frecuencias graves (250 Hz)
                                    grave_250_der = datos[0]['oidoDerecho']  # 250 Hz es índice 0
                                    grave_250_izq = datos[0]['oidoIzquierdo']

                                    # Verificar pérdida en frecuencias agudas (6000, 8000 Hz)
                                    agudas_der = [datos[6]['oidoDerecho'], datos[7]['oidoDerecho']]
                                    agudas_izq = [datos[6]['oidoIzquierdo'], datos[7]['oidoIzquierdo']]
                                    tiene_perdida_agudas = any(v > 25 for v in agudas_der + agudas_izq)

                                    # Construir diagnóstico base
                                    diagnostico_base = ""
                                    notas_adicionales = []

                                    if clasif_der == "Normal" and clasif_izq == "Normal":
                                        if tiene_perdida_agudas:
                                            diagnostico_base = "Audición dentro de parámetros normales en frecuencias conversacionales. Se observa leve disminución en frecuencias agudas."
                                        else:
                                            diagnostico_base = "Audición dentro de parámetros normales bilateralmente. Los umbrales auditivos se encuentran en rangos de normalidad en todas las frecuencias evaluadas."
                                    elif clasif_der == "Normal":
                                        diagnostico_base = f"Oído derecho con audición normal. Oído izquierdo presenta pérdida auditiva {clasif_izq.lower()} (promedio {prom_izq:.1f} dB HL)."
                                    elif clasif_izq == "Normal":
                                        diagnostico_base = f"Oído izquierdo con audición normal. Oído derecho presenta pérdida auditiva {clasif_der.lower()} (promedio {prom_der:.1f} dB HL)."
                                    else:
                                        diagnostico_base = f"Pérdida auditiva bilateral: Oído derecho {clasif_der.lower()} (promedio {prom_der:.1f} dB HL), Oído izquierdo {clasif_izq.lower()} (promedio {prom_izq:.1f} dB HL)."

                                    # Agregar nota sobre pérdida en 250 Hz si es significativa
                                    if grave_250_der > 25 or grave_250_izq > 25:
                                        if grave_250_der > 25 and grave_250_izq > 25:
                                            notas_adicionales.append(f"Se observa disminución en frecuencias graves (250 Hz) bilateral.")
                                        elif grave_250_der > 25:
                                            notas_adicionales.append(f"Se observa disminución en frecuencias graves (250 Hz) en oído derecho ({grave_250_der} dB).")
                                        else:
                                            notas_adicionales.append(f"Se observa disminución en frecuencias graves (250 Hz) en oído izquierdo ({grave_250_izq} dB).")

                                    # Agregar nota sobre umbrales atípicamente bajos si existen
                                    if tiene_umbrales_bajos:
                                        frecuencias_afectadas = []
                                        if umbrales_bajos_der:
                                            frecuencias_afectadas.append("oído derecho")
                                        if umbrales_bajos_izq:
                                            frecuencias_afectadas.append("oído izquierdo")
                                        notas_adicionales.append(f"Se observan umbrales atípicamente bajos en {' y '.join(frecuencias_afectadas)}.")

                                    # Combinar diagnóstico base con notas adicionales
                                    if notas_adicionales:
                                        diagnostico_base += " " + " ".join(notas_adicionales)

                                    return diagnostico_base

                                # Usar diagnóstico de Wix si existe, sino calcular automáticamente
                                diagnostico_auto = calcular_diagnostico_audiometria(datosParaTabla)
                                diagnostico_final = datos_raw.get('diagnostico') or diagnostico_auto

                                datos_audiometria = {
                                    "datosParaTabla": datosParaTabla,
                                    "diagnostico": diagnostico_final
                                }
                                print(f"✅ Datos de audiometría obtenidos desde Wix (fallback)")
                                print(f"📊 Diagnóstico: {diagnostico_final}")
                            else:
                                datos_audiometria = None
                        else:
                            print(f"⚠️ No se encontraron datos de audiometría en Wix para {wix_id_historia}")
                    else:
                        print(f"⚠️ Error al consultar datos de audiometría en Wix: {audio_response.status_code}")
                except Exception as e:
                    print(f"❌ Error consultando datos de audiometría en Wix: {e}")

        # ===== LÓGICA DE TEXTOS DINÁMICOS SEGÚN EXÁMENES (como en Wix) =====
        # Nota: Las claves deben coincidir con los nombres normalizados (MAYÚSCULAS de tabla examenes PostgreSQL)
        textos_examenes = {
            # Nombres normalizados (MAYÚSCULAS - coinciden con tabla examenes de PostgreSQL)
            "EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR": "Basándonos en los resultados obtenidos de la evaluación osteomuscular, certificamos que el paciente presenta un sistema osteomuscular en condiciones óptimas de salud. Esta condición le permite llevar a cabo una variedad de actividades físicas y cotidianas sin restricciones notables y con un riesgo mínimo de lesiones osteomusculares.",
            "OSTEOMUSCULAR": "Basándonos en los resultados obtenidos de la evaluación osteomuscular, certificamos que el paciente presenta un sistema osteomuscular en condiciones óptimas de salud. Esta condición le permite llevar a cabo una variedad de actividades físicas y cotidianas sin restricciones notables y con un riesgo mínimo de lesiones osteomusculares.",
            "ÉNFASIS CARDIOVASCULAR": "Énfasis cardiovascular: El examen médico laboral de ingreso con énfasis cardiovascular revela que presenta un estado cardiovascular dentro de los parámetros normales. No se observan hallazgos que indiquen la presencia de enfermedades cardiovasculares significativas o limitaciones funcionales para el desempeño laboral.",
            "PERFIL LIPÍDICO": "Perfil Lipídico: Los resultados del perfil lipídico indican un buen control de los lípidos en sangre. Los niveles de colesterol total, LDL, HDL y triglicéridos se encuentran dentro de los rangos de referencia, lo cual sugiere un bajo riesgo cardiovascular en este momento.",
            "PERFIL LIPÍDICO COMPLETO": "Perfil Lipídico: Los resultados del perfil lipídico indican un buen control de los lípidos en sangre. Los niveles de colesterol total, LDL, HDL y triglicéridos se encuentran dentro de los rangos de referencia, lo cual sugiere un bajo riesgo cardiovascular en este momento.",
            "ÉNFASIS VASCULAR": "El examen vascular muestra resultados dentro de los límites normales, sin evidencia de enfermedad arterial periférica ni estenosis carotídea significativa. Se recomienda al paciente continuar evitando el tabaquismo y mantener un estilo de vida saludable. Dada la buena condición vascular, no se requieren restricciones laborales en este momento. Se sugiere realizar seguimiento periódico para monitorear la salud vascular y prevenir posibles complicaciones en el futuro.",
            "ESPIROMETRÍA": "Prueba Espirometría: Función pulmonar normal sin evidencia de obstrucción o restricción significativa. No se requieren medidas adicionales en relación con la función pulmonar para el paciente en este momento.",
            "ÉNFASIS DERMATOLÓGICO": "Énfasis Dermatológico: Descripción general de la piel: La piel presenta un aspecto saludable, con una textura suave y uniforme. No se observan áreas de enrojecimiento, descamación o inflamación evidentes. El color de la piel es uniforme en todas las áreas evaluadas.\n\nAusencia de lesiones cutáneas: No se detectaron lesiones cutáneas como abrasiones, quemaduras, cortes o irritaciones en ninguna parte del cuerpo del paciente. La piel está íntegra y sin signos de traumatismos recientes.\n\nExposición controlada a agentes ambientales: No se identificaron signos de exposición excesiva a sustancias químicas o agentes ambientales que puedan afectar la piel.",
            "AUDIOMETRÍA": "No presenta signos de pérdida auditiva o alteraciones en la audición. Los resultados se encuentran dentro de los rangos normales establecidos para la población general y no se observan indicios de daño auditivo relacionado con la exposición laboral a ruido u otros factores.",
            "OPTOMETRÍA": "Presión intraocular (PIO): 15 mmHg en ambos ojos\nReflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos\nCampo visual: Normal en ambos ojos\nVisión de colores: Normal\nFondo de ojo: Normal.",
            "VISIOMETRÍA": "Presión intraocular (PIO): 15 mmHg en ambos ojos\nReflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos\nCampo visual: Normal en ambos ojos\nVisión de colores: Normal\nFondo de ojo: Normal.",
            "ELECTROCARDIOGRAMA": "Electrocardiograma: Ritmo sinusal normal. No se observan alteraciones en la conducción cardíaca ni signos de isquemia o hipertrofia ventricular. Los intervalos y segmentos se encuentran dentro de los parámetros normales.",
            "CUADRO HEMÁTICO": "Cuadro Hemático: Los valores de hemoglobina, hematocrito, leucocitos y plaquetas se encuentran dentro de los rangos normales. No se observan alteraciones que sugieran anemia, infección activa o trastornos de coagulación.",
            "HEMOGRAMA": "Hemograma: Los valores de hemoglobina, hematocrito, leucocitos y plaquetas se encuentran dentro de los rangos normales. No se observan alteraciones que sugieran anemia, infección activa o trastornos de coagulación.",
            "GLICEMIA": "Glicemia: Los niveles de glucosa en sangre se encuentran dentro de los parámetros normales, lo que indica un adecuado metabolismo de los carbohidratos.",
            "GLUCOSA EN SANGRE": "Glucosa en Sangre: Los niveles de glucosa en sangre se encuentran dentro de los parámetros normales, lo que indica un adecuado metabolismo de los carbohidratos.",
            "PARCIAL DE ORINA": "Parcial de Orina: El examen de orina no muestra alteraciones significativas. No se observan signos de infección urinaria, proteinuria ni glucosuria.",
            "PANEL DE DROGAS": "Panel de Drogas: Los resultados del panel de detección de sustancias psicoactivas son negativos para todas las sustancias evaluadas.",
            "EXAMEN DE ALTURAS": "Examen de Alturas: El paciente presenta condiciones físicas y psicológicas adecuadas para realizar trabajo en alturas. No se identifican contraindicaciones médicas para esta actividad.",
            "MANIPULACIÓN DE ALIMENTOS": "Manipulación de Alimentos: El paciente cumple con los requisitos de salud establecidos para la manipulación de alimentos. No presenta enfermedades infectocontagiosas ni condiciones que representen riesgo para la inocuidad alimentaria.",
            "KOH / COPROLÓGICO / FROTIS FARÍNGEO": "KOH / Coprológico / Frotis Faríngeo: Los exámenes de laboratorio no evidencian presencia de hongos, parásitos intestinales ni infecciones faríngeas activas.",
            "SCL-90": "SCL-90: La evaluación psicológica mediante el cuestionario SCL-90 muestra resultados dentro de los rangos normales en todas las dimensiones evaluadas, sin indicadores de psicopatología significativa.",
            "PRUEBA PSICOSENSOMÉTRICA": "Prueba Psicosensométrica: El usuario comprende rápidamente las indicaciones, realiza las pruebas correctamente y en el tiempo estipulado. La atención, concentración, memoria, velocidad de respuesta y las habilidades psicomotrices no presentan ninguna alteración. Los resultados están dentro de los rangos normales.",
            "EXAMEN MÉDICO OCUPACIONAL / AUDIOMETRÍA / VISIOMETRÍA": "Examen médico ocupacional completo con audiometría y visiometría. Todos los resultados se encuentran dentro de los parámetros normales.",
            # Mantener compatibilidad con nombres en formato antiguo (por si acaso)
            "Examen Médico Osteomuscular": "Basándonos en los resultados obtenidos de la evaluación osteomuscular, certificamos que el paciente presenta un sistema osteomuscular en condiciones óptimas de salud. Esta condición le permite llevar a cabo una variedad de actividades físicas y cotidianas sin restricciones notables y con un riesgo mínimo de lesiones osteomusculares.",
            "Énfasis Cardiovascular": "Énfasis cardiovascular: El examen médico laboral de ingreso con énfasis cardiovascular revela que presenta un estado cardiovascular dentro de los parámetros normales. No se observan hallazgos que indiquen la presencia de enfermedades cardiovasculares significativas o limitaciones funcionales para el desempeño laboral.",
            "É. Cardiovascular": "Énfasis cardiovascular: El examen médico laboral de ingreso con énfasis cardiovascular revela que presenta un estado cardiovascular dentro de los parámetros normales. No se observan hallazgos que indiquen la presencia de enfermedades cardiovasculares significativas o limitaciones funcionales para el desempeño laboral.",
            "Perfil Lipídico": "Perfil Lipídico: Los resultados del perfil lipídico indican un buen control de los lípidos en sangre. Los niveles de colesterol total, LDL, HDL y triglicéridos se encuentran dentro de los rangos de referencia, lo cual sugiere un bajo riesgo cardiovascular en este momento.",
            "É. VASCULAR": "El examen vascular muestra resultados dentro de los límites normales, sin evidencia de enfermedad arterial periférica ni estenosis carotídea significativa. Se recomienda al paciente continuar evitando el tabaquismo y mantener un estilo de vida saludable. Dada la buena condición vascular, no se requieren restricciones laborales en este momento. Se sugiere realizar seguimiento periódico para monitorear la salud vascular y prevenir posibles complicaciones en el futuro.",
            "Test Vocal Voximetría": "Los resultados obtenidos del test de voximetría muestran que el paciente presenta una saturación de oxígeno adecuada tanto en reposo como durante la actividad laboral. La frecuencia respiratoria y la frecuencia cardíaca se encuentran dentro de los rangos normales, lo que sugiere que no hay signos de hipoxia o alteraciones significativas en la función respiratoria bajo condiciones laborales normales.",
            "Espirometría": "Prueba Espirometría: Función pulmonar normal sin evidencia de obstrucción o restricción significativa. No se requieren medidas adicionales en relación con la función pulmonar para el paciente en este momento.",
            "Énfasis Dermatológico": "Énfasis Dermatológico: Descripción general de la piel: La piel presenta un aspecto saludable, con una textura suave y uniforme. No se observan áreas de enrojecimiento, descamación o inflamación evidentes. El color de la piel es uniforme en todas las áreas evaluadas.\n\nAusencia de lesiones cutáneas: No se detectaron lesiones cutáneas como abrasiones, quemaduras, cortes o irritaciones en ninguna parte del cuerpo del paciente. La piel está íntegra y sin signos de traumatismos recientes.\n\nExposición controlada a agentes ambientales: No se identificaron signos de exposición excesiva a sustancias químicas o agentes ambientales que puedan afectar la piel.",
            "Test R. Psicosocial (Ansiedad,Depresión)": "Nivel de estrés percibido: Muestra un nivel de estrés bajo en su vida cotidiana, con preocupaciones manejables y una actitud tranquila frente a las demandas laborales.\n\nCapacidad de adaptación: Destaca una excepcional capacidad de adaptación a diferentes entornos y escenarios laborales, evidenciando flexibilidad y disposición para aprender ante nuevos desafíos.\n\nResiliencia emocional: Exhibe una resiliencia emocional notable, enfrentando las dificultades con calma y manteniendo una perspectiva optimista incluso en momentos de presión.\n\nHabilidades de afrontamiento: Se identifican habilidades de afrontamiento efectivas, como la búsqueda de soluciones creativas y la gestión proactiva de situaciones conflictivas, lo que sugiere una capacidad para resolver problemas de manera constructiva.\n\nRelaciones interpersonales: Demuestra habilidades interpersonales excepcionales, estableciendo relaciones sólidas y colaborativas con colegas y superiores, lo que favorece un ambiente laboral armonioso y productivo.\n\nAutoeficacia y autoestima: Se evidencia una autoeficacia alta y una autoestima saludable, reflejando confianza en las propias habilidades y una valoración positiva de sí mismo, aspectos que contribuyen a un desempeño laboral sólido y satisfactorio.",
            "Audiometría": "No presenta signos de pérdida auditiva o alteraciones en la audición. Los resultados se encuentran dentro de los rangos normales establecidos para la población general y no se observan indicios de daño auditivo relacionado con la exposición laboral a ruido u otros factores.",
            "Optometría": "Presión intraocular (PIO): 15 mmHg en ambos ojos\nReflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos\nCampo visual: Normal en ambos ojos\nVisión de colores: Normal\nFondo de ojo: Normal.",
            "Visiometría": "Presión intraocular (PIO): 15 mmHg en ambos ojos\nReflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos\nCampo visual: Normal en ambos ojos\nVisión de colores: Normal\nFondo de ojo: Normal."
        }

        # Construir resultados generales basados en los exámenes
        resultados_generales = []
        observaciones_certificado = datos_wix.get('mdObservacionesCertificado', '')

        # Detectar si hay análisis postural en las observaciones
        analisis_postural = []
        observaciones_sin_analisis = observaciones_certificado

        if observaciones_certificado and '=== ANÁLISIS POSTURAL ===' in observaciones_certificado:
            # Separar análisis postural de las observaciones regulares
            import re
            patron = r'=== ANÁLISIS POSTURAL ===\s*(.*?)\s*=== FIN ANÁLISIS POSTURAL ==='
            matches = re.findall(patron, observaciones_certificado, re.DOTALL)

            for match in matches:
                # Parsear cada ejercicio
                ejercicio_info = {}

                # Extraer fecha
                fecha_match = re.search(r'Fecha:\s*(\d{2}/\d{2}/\d{4})', match)
                if fecha_match:
                    ejercicio_info['fecha'] = fecha_match.group(1)

                # Extraer número de ejercicio y hora
                ejercicio_match = re.search(r'EJERCICIO\s+(\d+)\s*\(([^)]+)\)', match)
                if ejercicio_match:
                    ejercicio_info['numero'] = ejercicio_match.group(1)
                    ejercicio_info['hora'] = ejercicio_match.group(2)

                # Extraer ángulo del tronco
                tronco_match = re.search(r'Ángulo del tronco:\s*([\d.]+)°', match)
                if tronco_match:
                    ejercicio_info['angulo_tronco'] = tronco_match.group(1)

                # Extraer alineación
                alineacion_match = re.search(r'Alineación:\s*(\w+)', match)
                if alineacion_match:
                    ejercicio_info['alineacion'] = alineacion_match.group(1)

                # Extraer ángulos articulares
                codo_izq = re.search(r'Codo izquierdo:\s*([\d.]+)°', match)
                codo_der = re.search(r'Codo derecho:\s*([\d.]+)°', match)
                rodilla_izq = re.search(r'Rodilla izquierda:\s*([\d.]+)°', match)
                rodilla_der = re.search(r'Rodilla derecha:\s*([\d.]+)°', match)

                ejercicio_info['angulos'] = {
                    'codo_izq': codo_izq.group(1) if codo_izq else 'N/A',
                    'codo_der': codo_der.group(1) if codo_der else 'N/A',
                    'rodilla_izq': rodilla_izq.group(1) if rodilla_izq else 'N/A',
                    'rodilla_der': rodilla_der.group(1) if rodilla_der else 'N/A'
                }

                # Extraer simetría
                hombros_match = re.search(r'Hombros:\s*(\w+)\s*\(diferencia:\s*([\d.]+)%\)', match)
                caderas_match = re.search(r'Caderas:\s*(\w+)\s*\(diferencia:\s*([\d.]+)%\)', match)

                ejercicio_info['simetria'] = {
                    'hombros': hombros_match.group(1) if hombros_match else 'N/A',
                    'hombros_diff': hombros_match.group(2) if hombros_match else 'N/A',
                    'caderas': caderas_match.group(1) if caderas_match else 'N/A',
                    'caderas_diff': caderas_match.group(2) if caderas_match else 'N/A'
                }

                analisis_postural.append(ejercicio_info)

            # Remover análisis postural de las observaciones
            observaciones_sin_analisis = re.sub(r'=== ANÁLISIS POSTURAL ===.*?=== FIN ANÁLISIS POSTURAL ===\s*', '', observaciones_certificado, flags=re.DOTALL).strip()

        # Usar examenes_normalizados que ya fue definido arriba (con normalizar_lista_examenes)
        # Si hay observaciones del médico, usarlas en lugar del texto hardcodeado
        for i, examen in enumerate(examenes_normalizados):
            # Si hay observaciones y este es el examen osteomuscular, usar las observaciones
            if observaciones_sin_analisis and "OSTEOMUSCULAR" in examen.upper():
                descripcion = observaciones_sin_analisis
            # Si es audiometría y hay datos de audiometría, usar el diagnóstico del audiograma
            elif "AUDIOMETRÍA" in examen.upper() or "AUDIOMETRIA" in examen.upper():
                if datos_audiometria and datos_audiometria.get('diagnostico'):
                    descripcion = datos_audiometria['diagnostico']
                else:
                    descripcion = textos_examenes.get(examen, "Resultados dentro de parámetros normales.")
            else:
                descripcion = textos_examenes.get(examen, "Resultados dentro de parámetros normales.")
            resultados_generales.append({
                "examen": examen,
                "descripcion": descripcion
            })

        # Recomendaciones médicas
        recomendaciones = datos_wix.get('mdRecomendacionesMedicasAdicionales', '')
        if not recomendaciones:
            recomendaciones = "RECOMENDACIONES GENERALES:\n1. PAUSAS ACTIVAS\n2. HIGIENE POSTURAL\n3. MEDIDAS ERGONOMICAS\n4. TÉCNICAS DE MANEJO DE ESTRÉS\n5. ALIMENTACIÓN BALANCEADA"

        # Mapear médico a imagen de firma y datos
        medico = datos_wix.get('medico', 'JUAN 134')
        firma_medico_map = {
            "SIXTA": "FIRMA-SIXTA.png",
            "JUAN 134": "FIRMA-JUAN134.jpeg",
            "CESAR": "FIRMA-CESAR.jpeg",
            "MARY": "FIRMA-MARY.jpeg",
            "NUBIA": "FIRMA-JUAN134.jpeg",
            "PRESENCIAL": "FIRMA-PRESENCIAL.jpeg",
            "PILAR": "FIRMA_PILAR.png"
        }

        # Datos de cada médico
        medico_datos_map = {
            "SIXTA": {
                "nombre": "SIXTA VIVERO CARRASCAL",
                "registro": "REGISTRO MÉDICO NO 55300504",
                "licencia": "LICENCIA SALUD OCUPACIONAL 583",
                "fecha": "16 DE FEBRERO DE 2021"
            },
            "JUAN 134": {
                "nombre": "JUAN JOSE REATIGA",
                "registro": "C.C.: 7.472.676 - REGISTRO MEDICO NO 14791",
                "licencia": "LICENCIA SALUD OCUPACIONAL 460",
                "fecha": "6 DE JULIO DE 2020"
            },
            "CESAR": {
                "nombre": "CÉSAR ADOLFO ZAMBRANO MARTÍNEZ",
                "registro": "REGISTRO MEDICO NO 1192803570",
                "licencia": "LICENCIA SALUD OCUPACIONAL # 3241",
                "fecha": "13 DE JULIO DE 2021"
            },
            "MARY": {
                "nombre": "",
                "registro": "",
                "licencia": "",
                "fecha": ""
            },
            "NUBIA": {
                "nombre": "JUAN JOSE REATIGA",
                "registro": "C.C.: 7.472.676 - REGISTRO MEDICO NO 14791",
                "licencia": "LICENCIA SALUD OCUPACIONAL 460",
                "fecha": "6 DE JULIO DE 2020"
            },
            "PRESENCIAL": {
                "nombre": "",
                "registro": "",
                "licencia": "",
                "fecha": ""
            },
            "PILAR": {
                "nombre": "DRA. MARIA DEL PILAR PEROZO HERNANDEZ",
                "registro": "C.C.: 1.090.419.867 - MÉDICO OCUPACIONAL",
                "licencia": "Resolución No. 27293",
                "fecha": "05 DE AGOSTO DE 2025"
            }
        }

        # Obtener firma del médico desde archivos locales
        firma_medico_filename = firma_medico_map.get(medico)
        firma_medico_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/static/{firma_medico_filename}" if firma_medico_filename else ""

        # Obtener datos del médico
        datos_medico = medico_datos_map.get(medico, {"nombre": "", "registro": "", "licencia": "", "fecha": ""})
        print(f"✅ Firma médico: {firma_medico_filename}")
        print(f"👨‍⚕️ Médico: {datos_medico['nombre']}")

        # Firma del paciente desde PostgreSQL
        firma_paciente_url = datos_wix.get('firma_paciente')
        if firma_paciente_url:
            print(f"✅ Firma paciente: obtenida desde PostgreSQL (data URI base64)")
        else:
            print(f"ℹ️  Firma paciente: no disponible")

        # Firma del optómetra (siempre la misma)
        firma_optometra_url = "https://bsl-utilidades-yp78a.ondigitalocean.app/static/FIRMA-OPTOMETRA.jpeg"
        print(f"✅ Firma optómetra: FIRMA-OPTOMETRA.jpeg")

        # Preparar payload para el endpoint de generación
        payload_certificado = {
            # Datos personales
            "nombres_apellidos": nombre_completo,
            "documento_identidad": datos_wix.get('numeroId', ''),
            "cargo": datos_wix.get('cargo', ''),
            "empresa": datos_wix.get('empresa', ''),
            "genero": datos_wix.get('genero', ''),
            "edad": str(datos_wix.get('edad', '')),
            "fecha_nacimiento": datos_wix.get('fechaNacimiento', ''),
            "estado_civil": datos_wix.get('estadoCivil', ''),
            "hijos": str(datos_wix.get('hijos', '0')),
            "profesion": datos_wix.get('profesionUOficio', ''),
            "email": datos_wix.get('email', ''),
            "celular": datos_wix.get('celular', ''),
            "tipo_examen": datos_wix.get('tipoExamen', ''),
            "foto_paciente": datos_wix.get('foto_paciente', None),

            # Seguridad social y nivel educativo
            "eps": datos_wix.get('eps', ''),
            "arl": datos_wix.get('arl', ''),
            "pensiones": datos_wix.get('pensiones', ''),
            "nivel_educativo": datos_wix.get('nivel_educativo', ''),

            # Información de la consulta
            "fecha_atencion": fecha_formateada,
            "ciudad": "BOGOTÁ" if datos_wix.get('codEmpresa') == 'GODRONE' else datos_wix.get('ciudad', 'Bogotá'),
            "vigencia": "1 año",
            "ips_sede": "Sede norte DHSS0244914",

            # Exámenes
            "examenes_realizados": examenes_realizados,
            "examenes": examenes,  # Lista de exámenes para verificar tipo

            # Resultados generales (con textos dinámicos)
            "resultados_generales": resultados_generales,

            # Análisis postural (si existe)
            "analisis_postural": analisis_postural,

            # Concepto médico (solo SANITHELP-JJ tiene valor por defecto)
            "concepto_medico": datos_wix.get('mdConceptoFinal', '') or ('ELEGIBLE PARA EL CARGO' if datos_wix.get('codEmpresa') == 'SANITHELP-JJ' else ''),

            # Recomendaciones médicas
            "recomendaciones_medicas": recomendaciones,

            # Datos visuales (Optometría/Visiometría)
            "datos_visual": datos_visual,

            # Datos de audiometría
            "datos_audiometria": datos_audiometria,

            # Firmas
            "medico_nombre": datos_medico['nombre'],
            "medico_registro": datos_medico['registro'],
            "medico_licencia": datos_medico['licencia'],
            "medico_fecha": datos_medico['fecha'],
            "firma_medico_url": firma_medico_url,
            "firma_paciente_url": firma_paciente_url,
            "firma_optometra_url": firma_optometra_url,

            # Almacenamiento
            "guardar_drive": guardar_drive,
            "nombre_archivo": f"certificado_{datos_wix.get('numeroId', wix_id)}_{datetime.now().strftime('%Y%m%d')}.pdf"
        }

        print(f"📄 Datos preparados para generar certificado")
        print(f"👤 Paciente: {nombre_completo}")
        print(f"🆔 Documento: {datos_wix.get('numeroId', '')}")

        # ========== GENERAR PDF CON PUPPETEER ==========
        # Usar Puppeteer con la URL del preview

        print("🎭 Generando PDF con Puppeteer desde URL del preview...")

        # Construir URL del preview HTML con cache-busting
        import time
        cache_buster = int(time.time() * 1000)  # timestamp en milisegundos
        preview_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/preview-certificado-html/{wix_id}?v={cache_buster}"
        print(f"🔗 URL del preview: {preview_url}")

        # Generar PDF usando Puppeteer
        try:
            pdf_content = puppeteer_html_to_pdf_from_url(
                html_url=preview_url,
                output_filename=f"certificado_{datos_wix.get('numeroId', wix_id)}"
            )

            # Guardar PDF localmente para envío directo
            print("💾 Guardando PDF localmente...")
            documento_id = datos_wix.get('numeroId', wix_id)
            documento_sanitized = str(documento_id).replace(" ", "_").replace("/", "_").replace("\\", "_")
            local = f"certificado_medico_{documento_sanitized}.pdf"

            with open(local, "wb") as f:
                f.write(pdf_content)

            print(f"✅ PDF generado y guardado localmente: {local}")

            # Enviar archivo como descarga directa
            response = send_file(
                local,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"certificado_medico_{documento_sanitized}.pdf"
            )

            # Configurar CORS
            response.headers["Access-Control-Allow-Origin"] = "*"

            # Limpiar archivo temporal después del envío
            @response.call_on_close
            def cleanup():
                try:
                    os.remove(local)
                    print(f"🗑️  Archivo temporal eliminado: {local}")
                except Exception as e:
                    print(f"⚠️  Error al eliminar archivo temporal: {e}")

            return response

        except Exception as e:
            print(f"❌ Error generando PDF con Puppeteer: {e}")
            traceback.print_exc()
            error_response = jsonify({
                "success": False,
                "error": f"Error generando PDF: {str(e)}"
            })
            error_response.headers["Access-Control-Allow-Origin"] = "*"
            return error_response, 500

    except Exception as e:
        print(f"❌ Error generando certificado desde Wix: {str(e)}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "error": str(e),
            "wix_id": wix_id
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"

        return error_response, 500


# ================================================
# ENDPOINTS PARA DESCARGAS ALEGRA (iLovePDF)
# ================================================

@app.route("/generar-certificado-alegra/<wix_id>", methods=["GET", "OPTIONS"])
def generar_certificado_alegra(wix_id):
    """
    Endpoint que muestra loader mientras se genera el certificado con iLovePDF (Descargas Alegra)

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Query params opcionales:
        guardar_drive: true/false (default: false)
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    # Mostrar página de loader (reutiliza el mismo loader que Puppeteer)
    return render_template('certificado_loader.html', wix_id=wix_id)


@app.route("/api/generar-certificado-alegra/<wix_id>", methods=["GET", "OPTIONS"])
def api_generar_certificado_alegra(wix_id):
    """
    Endpoint API que genera el PDF del certificado usando iLovePDF (para Descargas Alegra)

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Query params opcionales:
        guardar_drive: true/false (default: false)
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print(f"📋 [ALEGRA/iLovePDF] Generando certificado para Wix ID: {wix_id}")

        # Obtener parámetros opcionales
        guardar_drive = request.args.get('guardar_drive', 'false').lower() == 'true'

        print(f"🔧 [ALEGRA] Motor de conversión: iLovePDF")

        # Construir URL del preview HTML ESPECIAL para Alegra (con datos de FORMULARIO)
        import time
        cache_buster = int(time.time() * 1000)
        preview_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/preview-certificado-alegra/{wix_id}?v={cache_buster}"
        print(f"🔗 [ALEGRA] URL del preview (con FORMULARIO): {preview_url}")

        # Generar PDF usando iLovePDF
        print(f"📄 [ALEGRA] Iniciando generación con iLovePDF...")
        pdf_content = ilovepdf_html_to_pdf_from_url(
            html_url=preview_url,
            output_filename=f"certificado_alegra_{wix_id}"
        )

        # Guardar PDF localmente
        print("💾 [ALEGRA] Guardando PDF localmente...")
        local = f"certificado_alegra_{wix_id}.pdf"

        with open(local, "wb") as f:
            f.write(pdf_content)

        print(f"✅ [ALEGRA] PDF generado con iLovePDF: {local} ({len(pdf_content)} bytes)")

        # Enviar archivo como descarga
        response = send_file(
            local,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"certificado_alegra_{wix_id}.pdf"
        )

        # Configurar CORS
        response.headers["Access-Control-Allow-Origin"] = "*"

        # Limpiar archivo temporal después del envío
        @response.call_on_close
        def cleanup():
            try:
                os.remove(local)
                print(f"🗑️  [ALEGRA] Archivo temporal eliminado: {local}")
            except Exception as e:
                print(f"⚠️  [ALEGRA] Error al eliminar archivo temporal: {e}")

        return response

    except Exception as e:
        print(f"❌ [ALEGRA] Error generando certificado con iLovePDF: {e}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "error": f"Error generando PDF con iLovePDF: {str(e)}",
            "wix_id": wix_id
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"

        return error_response, 500


# --- Endpoint: PREVIEW CERTIFICADO ALEGRA CON DATOS DE FORMULARIO ---
@app.route("/preview-certificado-alegra/<wix_id>", methods=["GET", "OPTIONS"])
def preview_certificado_alegra(wix_id):
    """
    Endpoint para previsualizar el certificado en HTML CON datos de FORMULARIO (para Alegra/iLovePDF)

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Returns:
        HTML renderizado del certificado con datos demográficos de FORMULARIO
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print(f"🔍 [ALEGRA] Previsualizando certificado HTML con FORMULARIO para Wix ID: {wix_id}")

        # Consultar datos desde Wix HTTP Functions
        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")

        # 1. Obtener datos de HistoriaClinica (primero Wix, luego PostgreSQL como fallback)
        datos_wix = {}
        try:
            wix_url = f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}"
            response = requests.get(wix_url, timeout=10)

            if response.status_code == 200:
                wix_response = response.json()
                datos_wix = wix_response.get("data", {})

                if datos_wix:
                    print(f"✅ [ALEGRA] Datos obtenidos de HistoriaClinica Wix para ID: {wix_id}")
                else:
                    print(f"⚠️ [ALEGRA] Wix retornó respuesta vacía, intentando PostgreSQL...")
            else:
                print(f"⚠️ [ALEGRA] Error consultando Wix: {response.status_code}, intentando PostgreSQL...")

        except Exception as e:
            print(f"⚠️ [ALEGRA] Error de conexión a Wix: {str(e)}, intentando PostgreSQL...")

        # Si Wix no tiene datos, consultar HistoriaClinica de PostgreSQL
        if not datos_wix:
            print(f"🔍 [ALEGRA] Consultando HistoriaClinica desde PostgreSQL...")
            datos_historia_postgres = obtener_datos_historia_clinica_postgres(wix_id)

            if datos_historia_postgres:
                print(f"✅ [ALEGRA] Datos obtenidos de HistoriaClinica PostgreSQL")
                datos_wix = datos_historia_postgres
            else:
                print(f"❌ [ALEGRA] No se encontraron datos ni en Wix ni en PostgreSQL")
                return f"<html><body><h1>Error</h1><p>No se encontraron datos del paciente en el sistema (ID: {wix_id})</p></body></html>", 404

        # 2. Consultar FORMULARIO desde PostgreSQL (fuente principal, igual que Puppeteer)
        print(f"📋 [ALEGRA] Consultando FORMULARIO desde PostgreSQL con wix_id={wix_id}")

        datos_formulario = obtener_datos_formulario_postgres(wix_id)

        if datos_formulario:
            print(f"✅ [ALEGRA] Datos del formulario obtenidos desde PostgreSQL")

            # Agregar datos demográficos a datos_wix
            if datos_formulario.get('edad'):
                datos_wix['edad'] = datos_formulario.get('edad')
            if datos_formulario.get('genero'):
                datos_wix['genero'] = datos_formulario.get('genero')
            if datos_formulario.get('estadoCivil'):
                datos_wix['estadoCivil'] = datos_formulario.get('estadoCivil')
            if datos_formulario.get('hijos'):
                datos_wix['hijos'] = datos_formulario.get('hijos')
            if datos_formulario.get('email'):
                datos_wix['email'] = datos_formulario.get('email')
            if datos_formulario.get('profesionUOficio'):
                datos_wix['profesionUOficio'] = datos_formulario.get('profesionUOficio')
            if datos_formulario.get('ciudadDeResidencia'):
                datos_wix['ciudadDeResidencia'] = datos_formulario.get('ciudadDeResidencia')
            if datos_formulario.get('fechaNacimiento'):
                datos_wix['fechaNacimiento'] = datos_formulario.get('fechaNacimiento')

            # Foto y firma del paciente
            if datos_formulario.get('foto'):
                datos_wix['foto_paciente'] = datos_formulario.get('foto')
                print(f"✅ [ALEGRA] Foto obtenida de PostgreSQL")
            else:
                datos_wix['foto_paciente'] = None

            if datos_formulario.get('firma'):
                datos_wix['firma_paciente'] = datos_formulario.get('firma')
                print(f"✅ [ALEGRA] Firma obtenida de PostgreSQL")
            else:
                datos_wix['firma_paciente'] = None

            # Campos de seguridad social
            if datos_formulario.get('eps'):
                datos_wix['eps'] = datos_formulario.get('eps')
            if datos_formulario.get('arl'):
                datos_wix['arl'] = datos_formulario.get('arl')
            if datos_formulario.get('pensiones'):
                datos_wix['pensiones'] = datos_formulario.get('pensiones')
            if datos_formulario.get('nivelEducativo'):
                datos_wix['nivel_educativo'] = datos_formulario.get('nivelEducativo')

            print(f"📊 [ALEGRA] Datos integrados desde PostgreSQL: edad={datos_wix.get('edad')}, genero={datos_wix.get('genero')}, eps={datos_wix.get('eps')}")
        else:
            print(f"⚠️ [ALEGRA] No se encontró formulario en PostgreSQL, intentando Wix como fallback...")

            # Fallback: Consultar FORMULARIO desde Wix
            try:
                formulario_url = f"{wix_base_url}/formularioPorIdGeneral?idGeneral={wix_id}"
                print(f"🔗 [ALEGRA] URL de consulta Wix: {formulario_url}")
                formulario_response = requests.get(formulario_url, timeout=10)

                if formulario_response.status_code == 200:
                    formulario_data = formulario_response.json()

                    if formulario_data.get('success') and formulario_data.get('item'):
                        formulario = formulario_data['item']
                        print(f"✅ [ALEGRA] Datos demográficos obtenidos de Wix FORMULARIO (fallback)")

                        # Agregar datos demográficos a datos_wix
                        datos_wix['edad'] = formulario.get('edad')
                        datos_wix['genero'] = formulario.get('genero')
                        datos_wix['estadoCivil'] = formulario.get('estadoCivil')
                        datos_wix['hijos'] = formulario.get('hijos')
                        datos_wix['email'] = formulario.get('email')
                        datos_wix['profesionUOficio'] = formulario.get('profesionUOficio')
                        datos_wix['ciudadDeResidencia'] = formulario.get('ciudadDeResidencia')
                        datos_wix['fechaNacimiento'] = formulario.get('fechaNacimiento')
                        datos_wix['foto_paciente'] = formulario.get('foto')
                        datos_wix['firma_paciente'] = formulario.get('firma')
                    else:
                        print(f"⚠️ [ALEGRA] No se encontró formulario en Wix para idGeneral: {wix_id}")
                        datos_wix['foto_paciente'] = None
                        datos_wix['firma_paciente'] = None
                else:
                    print(f"⚠️ [ALEGRA] Error al consultar FORMULARIO en Wix: {formulario_response.status_code}")
                    datos_wix['foto_paciente'] = None
                    datos_wix['firma_paciente'] = None
            except Exception as e:
                print(f"❌ [ALEGRA] Error consultando FORMULARIO en Wix: {e}")
                datos_wix['foto_paciente'] = None
                datos_wix['firma_paciente'] = None

        # 3. Ahora generar el preview HTML completo con los datos enriquecidos
        print(f"✅ [ALEGRA] Generando preview HTML completo con datos de FORMULARIO")

        # Guardar datos enriquecidos temporalmente en flask.g para que preview_certificado_html los use
        import flask
        flask.g.datos_wix_enriquecidos = datos_wix
        flask.g.usar_datos_formulario = True

        # Llamar internamente al preview normal que ya tiene toda la lógica de renderizado
        return preview_certificado_html(wix_id)

    except Exception as e:
        print(f"❌ [ALEGRA] Error general: {str(e)}")
        traceback.print_exc()
        return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>", 500


# --- Endpoint: PREVIEW CERTIFICADO EN HTML (sin generar PDF) ---
@app.route("/preview-certificado-html/<wix_id>", methods=["GET", "OPTIONS"])
def preview_certificado_html(wix_id):
    """
    Endpoint para previsualizar el certificado en HTML sin generar el PDF

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Returns:
        HTML renderizado del certificado
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print(f"🔍 Previsualizando certificado HTML para Wix ID: {wix_id}")

        # Consultar datos desde Wix HTTP Functions
        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")

        # Verificar si tenemos datos enriquecidos de Alegra (vienen de flask.g)
        import flask
        usar_datos_formulario = getattr(flask.g, 'usar_datos_formulario', False)

        if usar_datos_formulario and hasattr(flask.g, 'datos_wix_enriquecidos'):
            # Usar datos ya enriquecidos con FORMULARIO (vienen de preview_certificado_alegra)
            datos_wix = flask.g.datos_wix_enriquecidos
            print(f"✅ [ALEGRA] Usando datos enriquecidos con FORMULARIO para preview")
        else:
            # Consultar normalmente desde Wix (flujo original de Puppeteer)
            datos_wix = {}
            try:
                wix_url = f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}"
                response = requests.get(wix_url, timeout=10)

                if response.status_code == 200:
                    wix_response = response.json()
                    datos_wix = wix_response.get("data", {})

                    if datos_wix:
                        print(f"✅ Datos obtenidos de Wix para ID: {wix_id}")
                    else:
                        print(f"⚠️ Wix retornó respuesta vacía, intentando PostgreSQL...")
                else:
                    print(f"⚠️ Error consultando Wix: {response.status_code}, intentando PostgreSQL...")

            except Exception as e:
                print(f"⚠️ Error de conexión a Wix: {str(e)}, intentando PostgreSQL...")

            # SIEMPRE consultar PostgreSQL primero (tiene prioridad sobre Wix)
            print(f"🔍 Consultando HistoriaClinica desde PostgreSQL (prioridad)...")
            datos_historia_postgres = obtener_datos_historia_clinica_postgres(wix_id)

            if datos_historia_postgres:
                print(f"✅ Datos obtenidos de HistoriaClinica PostgreSQL")
                # PostgreSQL sobrescribe TODOS los datos de Wix
                for key, value in datos_historia_postgres.items():
                    if value is not None:
                        datos_wix[key] = value
                        print(f"  ✓ {key} sobrescrito desde PostgreSQL")
            elif not datos_wix:
                print(f"❌ No se encontraron datos ni en Wix ni en PostgreSQL")
                return f"<html><body><h1>Error</h1><p>No se encontraron datos del paciente en el sistema (ID: {wix_id})</p></body></html>", 404

        # Transformar datos de Wix al formato del certificado
        nombre_completo = f"{datos_wix.get('primerNombre', '')} {datos_wix.get('segundoNombre', '')} {datos_wix.get('primerApellido', '')} {datos_wix.get('segundoApellido', '')}".strip()

        fecha_consulta = datos_wix.get('fechaConsulta')
        if isinstance(fecha_consulta, datetime):
            fecha_formateada = formatear_fecha_espanol(fecha_consulta)
        elif isinstance(fecha_consulta, str):
            # Parsear fecha ISO de Wix (ej: "2025-09-30T16:31:00.927Z")
            try:
                fecha_obj = datetime.fromisoformat(fecha_consulta.replace('Z', '+00:00'))
                fecha_formateada = formatear_fecha_espanol(fecha_obj)
            except (ValueError, AttributeError):
                fecha_formateada = formatear_fecha_espanol(datetime.now())
        else:
            fecha_formateada = formatear_fecha_espanol(datetime.now())

        # Construir exámenes realizados
        # Normalizar lista de exámenes (convierte string a array si viene de PostgreSQL)
        examenes = normalizar_lista_examenes(datos_wix.get('examenes', []))
        examenes_normalizados = [normalizar_examen(e) for e in examenes]

        examenes_realizados = []
        for examen in examenes_normalizados:
            examenes_realizados.append({
                "nombre": examen,
                "fecha": fecha_formateada
            })

        # ===== CONSULTAR DATOS VISUALES (Optometría/Visiometría) =====
        datos_visual = None
        # examenes y examenes_normalizados ya están definidos arriba (ahora en MAYÚSCULAS)
        tiene_examen_visual = any(e in ['OPTOMETRÍA', 'VISIOMETRÍA', 'Optometría', 'Visiometría'] for e in examenes_normalizados)

        if tiene_examen_visual:
            wix_id_historia = datos_wix.get('_id', wix_id)  # Usar wix_id del parámetro si no viene en datos_wix

            # PRIORIDAD 1: Consultar PostgreSQL - visiometrias_virtual (examen virtual)
            print(f"🔍 [PRIORIDAD 1] Consultando visiometrias_virtual en PostgreSQL para: {wix_id_historia}", flush=True)
            datos_visual = obtener_visiometria_postgres(wix_id_historia)

            # PRIORIDAD 2: Consultar PostgreSQL - visiometrias (optometría profesional)
            if not datos_visual:
                print(f"🔍 [PRIORIDAD 2] Consultando visiometrias (optometría) en PostgreSQL...", flush=True)
                datos_visual = obtener_optometria_postgres(wix_id_historia)

            # PRIORIDAD 3: Fallback a Wix si PostgreSQL no tiene datos
            if not datos_visual:
                print(f"🔍 [PRIORIDAD 3 - Fallback] Consultando datos visuales en Wix...", flush=True)
                try:
                    visual_url = f"https://www.bsl.com.co/_functions/visualPorIdGeneral?idGeneral={wix_id_historia}"

                    visual_response = requests.get(visual_url, timeout=10)

                    if visual_response.status_code == 200:
                        visual_data = visual_response.json()
                        if visual_data.get('success') and visual_data.get('data'):
                            datos_visual = visual_data['data'][0] if len(visual_data['data']) > 0 else None
                            print(f"✅ Datos visuales obtenidos desde Wix (fallback)", flush=True)
                            print(f"📊 Datos: {datos_visual}", flush=True)
                        else:
                            print(f"⚠️ No se encontraron datos visuales en Wix para {wix_id_historia}", flush=True)
                            datos_visual = None
                    else:
                        print(f"⚠️ Error al consultar datos visuales en Wix: {visual_response.status_code}", flush=True)
                        datos_visual = None
                except Exception as e:
                    print(f"❌ Error consultando datos visuales en Wix: {e}", flush=True)
                    datos_visual = None

        # ===== CONSULTAR DATOS DE AUDIOMETRÍA =====
        datos_audiometria = None
        tiene_examen_audio = any(e in ['AUDIOMETRÍA', 'Audiometría'] for e in examenes_normalizados)

        if tiene_examen_audio:
            wix_id_historia = datos_wix.get('_id', wix_id)  # Usar wix_id del parámetro si no viene en datos_wix

            # PRIORIDAD 1: Consultar PostgreSQL (audiometrias)
            print(f"🔍 [PRIORIDAD 1] Consultando audiometrias en PostgreSQL para: {wix_id_historia}", flush=True)
            datos_audiometria = obtener_audiometria_postgres(wix_id_historia)

            # PRIORIDAD 2: Fallback a Wix si PostgreSQL no tiene datos
            if not datos_audiometria:
                print(f"🔍 [PRIORIDAD 2 - Fallback] Consultando datos de audiometría en Wix...", flush=True)
                try:
                    audio_url = f"https://www.bsl.com.co/_functions/audiometriaPorIdGeneral?idGeneral={wix_id_historia}"

                    audio_response = requests.get(audio_url, timeout=10)

                    if audio_response.status_code == 200:
                        audio_data = audio_response.json()
                        if audio_data.get('success') and audio_data.get('data'):
                            datos_raw = audio_data['data'][0] if len(audio_data['data']) > 0 else None

                            if datos_raw:
                                # Transformar datos de Wix al formato esperado
                                frecuencias = [250, 500, 1000, 2000, 3000, 4000, 6000, 8000]
                                datosParaTabla = []

                                for freq in frecuencias:
                                    campo_der = f"auDer{freq}"
                                    campo_izq = f"auIzq{freq}"
                                    datosParaTabla.append({
                                        "frecuencia": freq,
                                        "oidoDerecho": datos_raw.get(campo_der, 0),
                                        "oidoIzquierdo": datos_raw.get(campo_izq, 0)
                                    })

                                # Calcular diagnóstico automático basado en umbrales auditivos
                                def calcular_diagnostico_audiometria(datos):
                                    # Detectar umbrales anormalmente bajos (por debajo de 0 dB)
                                    umbrales_bajos_der = [d for d in datos if d['oidoDerecho'] < 0]
                                    umbrales_bajos_izq = [d for d in datos if d['oidoIzquierdo'] < 0]
                                    tiene_umbrales_bajos = len(umbrales_bajos_der) > 0 or len(umbrales_bajos_izq) > 0

                                    # Promedios de frecuencias conversacionales (500, 1000, 2000 Hz)
                                    freq_conv_indices = [1, 2, 3]  # índices para 500, 1000, 2000 Hz
                                    valores_der = [datos[i]['oidoDerecho'] for i in freq_conv_indices]
                                    valores_izq = [datos[i]['oidoIzquierdo'] for i in freq_conv_indices]

                                    prom_der = sum(valores_der) / len(valores_der)
                                    prom_izq = sum(valores_izq) / len(valores_izq)

                                    def clasificar_umbral(umbral):
                                        if umbral <= 25:
                                            return "Normal"
                                        elif umbral <= 40:
                                            return "Leve"
                                        elif umbral <= 55:
                                            return "Moderada"
                                        elif umbral <= 70:
                                            return "Moderadamente Severa"
                                        elif umbral <= 90:
                                            return "Severa"
                                        else:
                                            return "Profunda"

                                    clasif_der = clasificar_umbral(prom_der)
                                    clasif_izq = clasificar_umbral(prom_izq)

                                    # Verificar pérdida en frecuencias graves (250 Hz)
                                    grave_250_der = datos[0]['oidoDerecho']  # 250 Hz es índice 0
                                    grave_250_izq = datos[0]['oidoIzquierdo']

                                    # Verificar pérdida en frecuencias agudas (6000, 8000 Hz)
                                    agudas_der = [datos[6]['oidoDerecho'], datos[7]['oidoDerecho']]
                                    agudas_izq = [datos[6]['oidoIzquierdo'], datos[7]['oidoIzquierdo']]
                                    tiene_perdida_agudas = any(v > 25 for v in agudas_der + agudas_izq)

                                    # Construir diagnóstico base
                                    diagnostico_base = ""
                                    notas_adicionales = []

                                    if clasif_der == "Normal" and clasif_izq == "Normal":
                                        if tiene_perdida_agudas:
                                            diagnostico_base = "Audición dentro de parámetros normales en frecuencias conversacionales. Se observa leve disminución en frecuencias agudas."
                                        else:
                                            diagnostico_base = "Audición dentro de parámetros normales bilateralmente. Los umbrales auditivos se encuentran en rangos de normalidad en todas las frecuencias evaluadas."
                                    elif clasif_der == "Normal":
                                        diagnostico_base = f"Oído derecho con audición normal. Oído izquierdo presenta pérdida auditiva {clasif_izq.lower()} (promedio {prom_izq:.1f} dB HL)."
                                    elif clasif_izq == "Normal":
                                        diagnostico_base = f"Oído izquierdo con audición normal. Oído derecho presenta pérdida auditiva {clasif_der.lower()} (promedio {prom_der:.1f} dB HL)."
                                    else:
                                        diagnostico_base = f"Pérdida auditiva bilateral: Oído derecho {clasif_der.lower()} (promedio {prom_der:.1f} dB HL), Oído izquierdo {clasif_izq.lower()} (promedio {prom_izq:.1f} dB HL)."

                                    # Agregar nota sobre pérdida en 250 Hz si es significativa
                                    if grave_250_der > 25 or grave_250_izq > 25:
                                        if grave_250_der > 25 and grave_250_izq > 25:
                                            notas_adicionales.append(f"Se observa disminución en frecuencias graves (250 Hz) bilateral.")
                                        elif grave_250_der > 25:
                                            notas_adicionales.append(f"Se observa disminución en frecuencias graves (250 Hz) en oído derecho ({grave_250_der} dB).")
                                        else:
                                            notas_adicionales.append(f"Se observa disminución en frecuencias graves (250 Hz) en oído izquierdo ({grave_250_izq} dB).")

                                    # Agregar nota sobre umbrales atípicamente bajos si existen
                                    if tiene_umbrales_bajos:
                                        frecuencias_afectadas = []
                                        if umbrales_bajos_der:
                                            frecuencias_afectadas.append("oído derecho")
                                        if umbrales_bajos_izq:
                                            frecuencias_afectadas.append("oído izquierdo")
                                        notas_adicionales.append(f"Se observan umbrales atípicamente bajos en {' y '.join(frecuencias_afectadas)}.")

                                    # Combinar diagnóstico base con notas adicionales
                                    if notas_adicionales:
                                        diagnostico_base += " " + " ".join(notas_adicionales)

                                    return diagnostico_base

                                # Usar diagnóstico de Wix si existe, sino calcular automáticamente
                                diagnostico_auto = calcular_diagnostico_audiometria(datosParaTabla)
                                diagnostico_final = datos_raw.get('diagnostico') or diagnostico_auto

                                datos_audiometria = {
                                    "datosParaTabla": datosParaTabla,
                                    "diagnostico": diagnostico_final
                                }
                                print(f"✅ Datos de audiometría obtenidos desde Wix (fallback)", flush=True)
                                print(f"📊 Diagnóstico: {diagnostico_final}", flush=True)
                            else:
                                datos_audiometria = None
                        else:
                            print(f"⚠️ No se encontraron datos de audiometría en Wix para {wix_id_historia}", flush=True)
                            datos_audiometria = None
                    else:
                        print(f"⚠️ Error al consultar datos de audiometría en Wix: {audio_response.status_code}", flush=True)
                        datos_audiometria = None
                except Exception as e:
                    print(f"❌ Error consultando datos de audiometría en Wix: {e}", flush=True)
                    datos_audiometria = None

        # ===== CONSULTAR DATOS DEL FORMULARIO DESDE POSTGRESQL =====
        # Solo consultar PostgreSQL si NO venimos de Alegra con datos ya cargados
        if not usar_datos_formulario:
            wix_id_historia = datos_wix.get('_id', wix_id)
            print(f"🔍 Consultando datos del formulario desde PostgreSQL para wix_id: {wix_id_historia}", flush=True)

            datos_formulario = obtener_datos_formulario_postgres(wix_id_historia)

            if datos_formulario:
                print(f"✅ Datos del formulario obtenidos desde PostgreSQL", flush=True)

                # Sobrescribir los datos de HistoriaClinica con los de PostgreSQL si existen
                if datos_formulario.get('edad'):
                    datos_wix['edad'] = datos_formulario.get('edad')
                if datos_formulario.get('genero'):
                    datos_wix['genero'] = datos_formulario.get('genero')
                if datos_formulario.get('estadoCivil'):
                    datos_wix['estadoCivil'] = datos_formulario.get('estadoCivil')
                if datos_formulario.get('hijos'):
                    datos_wix['hijos'] = datos_formulario.get('hijos')
                if datos_formulario.get('email'):
                    datos_wix['email'] = datos_formulario.get('email')
                if datos_formulario.get('profesionUOficio'):
                    datos_wix['profesionUOficio'] = datos_formulario.get('profesionUOficio')
                if datos_formulario.get('ciudadDeResidencia'):
                    datos_wix['ciudadDeResidencia'] = datos_formulario.get('ciudadDeResidencia')
                if datos_formulario.get('fechaNacimiento'):
                    datos_wix['fechaNacimiento'] = datos_formulario.get('fechaNacimiento')

                # ===== MERGE DE NUEVOS CAMPOS: EPS, ARL, PENSIONES, NIVEL EDUCATIVO =====
                if datos_formulario.get('eps'):
                    datos_wix['eps'] = datos_formulario.get('eps')
                    print(f"  ✓ EPS: {datos_formulario.get('eps')}", flush=True)
                if datos_formulario.get('arl'):
                    datos_wix['arl'] = datos_formulario.get('arl')
                    print(f"  ✓ ARL: {datos_formulario.get('arl')}", flush=True)
                if datos_formulario.get('pensiones'):
                    datos_wix['pensiones'] = datos_formulario.get('pensiones')
                    print(f"  ✓ Pensiones: {datos_formulario.get('pensiones')}", flush=True)
                if datos_formulario.get('nivelEducativo'):
                    datos_wix['nivel_educativo'] = datos_formulario.get('nivelEducativo')
                    print(f"  ✓ Nivel Educativo: {datos_formulario.get('nivelEducativo')}", flush=True)

                # Foto del paciente
                if datos_formulario.get('foto'):
                    datos_wix['foto_paciente'] = datos_formulario.get('foto')
                    print(f"✅ Usando foto de PostgreSQL (data URI base64)", flush=True)
                else:
                    datos_wix['foto_paciente'] = None
                    print(f"ℹ️  No hay foto disponible en PostgreSQL", flush=True)

                # Firma del paciente
                if datos_formulario.get('firma'):
                    datos_wix['firma_paciente'] = datos_formulario.get('firma')
                    print(f"✅ Usando firma de PostgreSQL (data URI base64)", flush=True)
                else:
                    datos_wix['firma_paciente'] = None
                    print(f"ℹ️  No hay firma disponible en PostgreSQL", flush=True)

                print(f"📊 Merge completado (preview): edad={datos_wix.get('edad')}, genero={datos_wix.get('genero')}, eps={datos_wix.get('eps')}, arl={datos_wix.get('arl')}", flush=True)
            else:
                print(f"⚠️ No se encontraron datos del formulario en PostgreSQL para wix_id: {wix_id_historia}", flush=True)
                datos_wix['foto_paciente'] = None
                datos_wix['firma_paciente'] = None
        else:
            print(f"✅ [ALEGRA] Usando datos de formulario ya cargados (PostgreSQL o Wix fallback)", flush=True)

        # Textos dinámicos según exámenes (MAYÚSCULAS para coincidir con normalización)
        textos_examenes = {
            # Nombres normalizados (MAYÚSCULAS)
            "EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR": "Basándonos en los resultados obtenidos de la evaluación osteomuscular, certificamos que el paciente presenta un sistema osteomuscular en condiciones óptimas de salud. Esta condición le permite llevar a cabo una variedad de actividades físicas y cotidianas sin restricciones notables y con un riesgo mínimo de lesiones osteomusculares.",
            "OSTEOMUSCULAR": "Basándonos en los resultados obtenidos de la evaluación osteomuscular, certificamos que el paciente presenta un sistema osteomuscular en condiciones óptimas de salud. Esta condición le permite llevar a cabo una variedad de actividades físicas y cotidianas sin restricciones notables y con un riesgo mínimo de lesiones osteomusculares.",
            "ÉNFASIS CARDIOVASCULAR": "Énfasis cardiovascular: El examen médico laboral de ingreso con énfasis cardiovascular revela que presenta un estado cardiovascular dentro de los parámetros normales. No se observan hallazgos que indiquen la presencia de enfermedades cardiovasculares significativas o limitaciones funcionales para el desempeño laboral.",
            "PERFIL LIPÍDICO": "Perfil Lipídico: Los resultados del perfil lipídico indican un buen control de los lípidos en sangre. Los niveles de colesterol total, LDL, HDL y triglicéridos se encuentran dentro de los rangos de referencia, lo cual sugiere un bajo riesgo cardiovascular en este momento.",
            "PERFIL LIPÍDICO COMPLETO": "Perfil Lipídico: Los resultados del perfil lipídico indican un buen control de los lípidos en sangre. Los niveles de colesterol total, LDL, HDL y triglicéridos se encuentran dentro de los rangos de referencia, lo cual sugiere un bajo riesgo cardiovascular en este momento.",
            "ÉNFASIS VASCULAR": "El examen vascular muestra resultados dentro de los límites normales, sin evidencia de enfermedad arterial periférica ni estenosis carotídea significativa. Se recomienda al paciente continuar evitando el tabaquismo y mantener un estilo de vida saludable. Dada la buena condición vascular, no se requieren restricciones laborales en este momento. Se sugiere realizar seguimiento periódico para monitorear la salud vascular y prevenir posibles complicaciones en el futuro.",
            "ESPIROMETRÍA": "Prueba Espirometría: Función pulmonar normal sin evidencia de obstrucción o restricción significativa. No se requieren medidas adicionales en relación con la función pulmonar para el paciente en este momento.",
            "ÉNFASIS DERMATOLÓGICO": "Énfasis Dermatológico: Descripción general de la piel: La piel presenta un aspecto saludable, con una textura suave y uniforme. No se observan áreas de enrojecimiento, descamación o inflamación evidentes. El color de la piel es uniforme en todas las áreas evaluadas.\n\nAusencia de lesiones cutáneas: No se detectaron lesiones cutáneas como abrasiones, quemaduras, cortes o irritaciones en ninguna parte del cuerpo del paciente. La piel está íntegra y sin signos de traumatismos recientes.\n\nExposición controlada a agentes ambientales: No se identificaron signos de exposición excesiva a sustancias químicas o agentes ambientales que puedan afectar la piel.",
            "AUDIOMETRÍA": "No presenta signos de pérdida auditiva o alteraciones en la audición. Los resultados se encuentran dentro de los rangos normales establecidos para la población general y no se observan indicios de daño auditivo relacionado con la exposición laboral a ruido u otros factores.",
            "OPTOMETRÍA": "Presión intraocular (PIO): 15 mmHg en ambos ojos\nReflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos\nCampo visual: Normal en ambos ojos\nVisión de colores: Normal\nFondo de ojo: Normal.",
            "VISIOMETRÍA": "Presión intraocular (PIO): 15 mmHg en ambos ojos\nReflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos\nCampo visual: Normal en ambos ojos\nVisión de colores: Normal\nFondo de ojo: Normal.",
            "ELECTROCARDIOGRAMA": "Electrocardiograma: Ritmo sinusal normal. No se observan alteraciones en la conducción cardíaca ni signos de isquemia o hipertrofia ventricular. Los intervalos y segmentos se encuentran dentro de los parámetros normales.",
            "CUADRO HEMÁTICO": "Cuadro Hemático: Los valores de hemoglobina, hematocrito, leucocitos y plaquetas se encuentran dentro de los rangos normales. No se observan alteraciones que sugieran anemia, infección activa o trastornos de coagulación.",
            "HEMOGRAMA": "Hemograma: Los valores de hemoglobina, hematocrito, leucocitos y plaquetas se encuentran dentro de los rangos normales. No se observan alteraciones que sugieran anemia, infección activa o trastornos de coagulación.",
            "GLICEMIA": "Glicemia: Los niveles de glucosa en sangre se encuentran dentro de los parámetros normales, lo que indica un adecuado metabolismo de los carbohidratos.",
            "GLUCOSA EN SANGRE": "Glucosa en Sangre: Los niveles de glucosa en sangre se encuentran dentro de los parámetros normales, lo que indica un adecuado metabolismo de los carbohidratos.",
            "PARCIAL DE ORINA": "Parcial de Orina: El examen de orina no muestra alteraciones significativas. No se observan signos de infección urinaria, proteinuria ni glucosuria.",
            "PANEL DE DROGAS": "Panel de Drogas: Los resultados del panel de detección de sustancias psicoactivas son negativos para todas las sustancias evaluadas.",
            "EXAMEN DE ALTURAS": "Examen de Alturas: El paciente presenta condiciones físicas y psicológicas adecuadas para realizar trabajo en alturas. No se identifican contraindicaciones médicas para esta actividad.",
            "MANIPULACIÓN DE ALIMENTOS": "Manipulación de Alimentos: El paciente cumple con los requisitos de salud establecidos para la manipulación de alimentos. No presenta enfermedades infectocontagiosas ni condiciones que representen riesgo para la inocuidad alimentaria.",
            "KOH / COPROLÓGICO / FROTIS FARÍNGEO": "KOH / Coprológico / Frotis Faríngeo: Los exámenes de laboratorio no evidencian presencia de hongos, parásitos intestinales ni infecciones faríngeas activas.",
            "SCL-90": "SCL-90: La evaluación psicológica mediante el cuestionario SCL-90 muestra resultados dentro de los rangos normales en todas las dimensiones evaluadas, sin indicadores de psicopatología significativa.",
            "PRUEBA PSICOSENSOMÉTRICA": "Prueba Psicosensométrica: El usuario comprende rápidamente las indicaciones, realiza las pruebas correctamente y en el tiempo estipulado. La atención, concentración, memoria, velocidad de respuesta y las habilidades psicomotrices no presentan ninguna alteración. Los resultados están dentro de los rangos normales.",
            "PERFIL PSICOLÓGICO ADC": "Perfil Psicológico ADC: Nivel de estrés percibido: Muestra un nivel de estrés bajo en su vida cotidiana, con preocupaciones manejables y una actitud tranquila frente a las demandas laborales.\n\nCapacidad de adaptación: Destaca una excepcional capacidad de adaptación a diferentes entornos y escenarios laborales, evidenciando flexibilidad y disposición para aprender ante nuevos desafíos.\n\nResiliencia emocional: Exhibe una resiliencia emocional notable, enfrentando las dificultades con calma y manteniendo una perspectiva optimista incluso en momentos de presión.\n\nHabilidades de afrontamiento: Se identifican habilidades de afrontamiento efectivas, como la búsqueda de soluciones creativas y la gestión proactiva de situaciones conflictivas, lo que sugiere una capacidad para resolver problemas de manera constructiva.\n\nRelaciones interpersonales: Demuestra habilidades interpersonales excepcionales, estableciendo relaciones sólidas y colaborativas con colegas y superiores, lo que favorece un ambiente laboral armonioso y productivo.\n\nAutoeficacia y autoestima: Se evidencia una autoeficacia alta y una autoestima saludable, reflejando confianza en las propias habilidades y una valoración positiva de sí mismo, aspectos que contribuyen a un desempeño laboral sólido y satisfactorio.",
            "EXAMEN MÉDICO OCUPACIONAL / AUDIOMETRÍA / VISIOMETRÍA": "Examen médico ocupacional completo con audiometría y visiometría. Todos los resultados se encuentran dentro de los parámetros normales.",
            # Compatibilidad con nombres en formato antiguo (Title Case)
            "Examen Médico Osteomuscular": "Basándonos en los resultados obtenidos de la evaluación osteomuscular, certificamos que el paciente presenta un sistema osteomuscular en condiciones óptimas de salud. Esta condición le permite llevar a cabo una variedad de actividades físicas y cotidianas sin restricciones notables y con un riesgo mínimo de lesiones osteomusculares.",
            "Énfasis Cardiovascular": "Énfasis cardiovascular: El examen médico laboral de ingreso con énfasis cardiovascular revela que presenta un estado cardiovascular dentro de los parámetros normales. No se observan hallazgos que indiquen la presencia de enfermedades cardiovasculares significativas o limitaciones funcionales para el desempeño laboral.",
            "É. Cardiovascular": "Énfasis cardiovascular: El examen médico laboral de ingreso con énfasis cardiovascular revela que presenta un estado cardiovascular dentro de los parámetros normales. No se observan hallazgos que indiquen la presencia de enfermedades cardiovasculares significativas o limitaciones funcionales para el desempeño laboral.",
            "Perfil Lipídico": "Perfil Lipídico: Los resultados del perfil lipídico indican un buen control de los lípidos en sangre. Los niveles de colesterol total, LDL, HDL y triglicéridos se encuentran dentro de los rangos de referencia, lo cual sugiere un bajo riesgo cardiovascular en este momento.",
            "É. VASCULAR": "El examen vascular muestra resultados dentro de los límites normales, sin evidencia de enfermedad arterial periférica ni estenosis carotídea significativa. Se recomienda al paciente continuar evitando el tabaquismo y mantener un estilo de vida saludable. Dada la buena condición vascular, no se requieren restricciones laborales en este momento. Se sugiere realizar seguimiento periódico para monitorear la salud vascular y prevenir posibles complicaciones en el futuro.",
            "Test Vocal Voximetría": "Los resultados obtenidos del test de voximetría muestran que el paciente presenta una saturación de oxígeno adecuada tanto en reposo como durante la actividad laboral. La frecuencia respiratoria y la frecuencia cardíaca se encuentran dentro de los rangos normales, lo que sugiere que no hay signos de hipoxia o alteraciones significativas en la función respiratoria bajo condiciones laborales normales.",
            "Espirometría": "Prueba Espirometría: Función pulmonar normal sin evidencia de obstrucción o restricción significativa. No se requieren medidas adicionales en relación con la función pulmonar para el paciente en este momento.",
            "Énfasis Dermatológico": "Énfasis Dermatológico: Descripción general de la piel: La piel presenta un aspecto saludable, con una textura suave y uniforme. No se observan áreas de enrojecimiento, descamación o inflamación evidentes. El color de la piel es uniforme en todas las áreas evaluadas.\n\nAusencia de lesiones cutáneas: No se detectaron lesiones cutáneas como abrasiones, quemaduras, cortes o irritaciones en ninguna parte del cuerpo del paciente. La piel está íntegra y sin signos de traumatismos recientes.\n\nExposición controlada a agentes ambientales: No se identificaron signos de exposición excesiva a sustancias químicas o agentes ambientales que puedan afectar la piel.",
            "Test R. Psicosocial (Ansiedad,Depresión)": "Nivel de estrés percibido: Muestra un nivel de estrés bajo en su vida cotidiana, con preocupaciones manejables y una actitud tranquila frente a las demandas laborales.\n\nCapacidad de adaptación: Destaca una excepcional capacidad de adaptación a diferentes entornos y escenarios laborales, evidenciando flexibilidad y disposición para aprender ante nuevos desafíos.\n\nResiliencia emocional: Exhibe una resiliencia emocional notable, enfrentando las dificultades con calma y manteniendo una perspectiva optimista incluso en momentos de presión.\n\nHabilidades de afrontamiento: Se identifican habilidades de afrontamiento efectivas, como la búsqueda de soluciones creativas y la gestión proactiva de situaciones conflictivas, lo que sugiere una capacidad para resolver problemas de manera constructiva.\n\nRelaciones interpersonales: Demuestra habilidades interpersonales excepcionales, estableciendo relaciones sólidas y colaborativas con colegas y superiores, lo que favorece un ambiente laboral armonioso y productivo.\n\nAutoeficacia y autoestima: Se evidencia una autoeficacia alta y una autoestima saludable, reflejando confianza en las propias habilidades y una valoración positiva de sí mismo, aspectos que contribuyen a un desempeño laboral sólido y satisfactorio.",
            "Audiometría": "No presenta signos de pérdida auditiva o alteraciones en la audición. Los resultados se encuentran dentro de los rangos normales establecidos para la población general y no se observan indicios de daño auditivo relacionado con la exposición laboral a ruido u otros factores.",
            "Optometría": "Presión intraocular (PIO): 15 mmHg en ambos ojos\nReflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos\nCampo visual: Normal en ambos ojos\nVisión de colores: Normal\nFondo de ojo: Normal.",
            "Visiometría": "Presión intraocular (PIO): 15 mmHg en ambos ojos\nReflejos pupilares: Respuesta pupilar normal a la luz en ambos ojos\nCampo visual: Normal en ambos ojos\nVisión de colores: Normal\nFondo de ojo: Normal.",
            "Perfil Psicológico ADC": "Perfil Psicológico ADC: Nivel de estrés percibido: Muestra un nivel de estrés bajo en su vida cotidiana, con preocupaciones manejables y una actitud tranquila frente a las demandas laborales.\n\nCapacidad de adaptación: Destaca una excepcional capacidad de adaptación a diferentes entornos y escenarios laborales, evidenciando flexibilidad y disposición para aprender ante nuevos desafíos.\n\nResiliencia emocional: Exhibe una resiliencia emocional notable, enfrentando las dificultades con calma y manteniendo una perspectiva optimista incluso en momentos de presión."
        }

        # Construir resultados generales
        resultados_generales = []
        observaciones_certificado = datos_wix.get('mdObservacionesCertificado', '')

        # Detectar si hay análisis postural en las observaciones
        analisis_postural = []
        observaciones_sin_analisis = observaciones_certificado

        if observaciones_certificado and '=== ANÁLISIS POSTURAL ===' in observaciones_certificado:
            # Separar análisis postural de las observaciones regulares
            import re
            patron = r'=== ANÁLISIS POSTURAL ===\s*(.*?)\s*=== FIN ANÁLISIS POSTURAL ==='
            matches = re.findall(patron, observaciones_certificado, re.DOTALL)

            for match in matches:
                # Parsear cada ejercicio
                ejercicio_info = {}

                # Extraer fecha
                fecha_match = re.search(r'Fecha:\s*(\d{2}/\d{2}/\d{4})', match)
                if fecha_match:
                    ejercicio_info['fecha'] = fecha_match.group(1)

                # Extraer número de ejercicio y hora
                ejercicio_match = re.search(r'EJERCICIO\s+(\d+)\s*\(([^)]+)\)', match)
                if ejercicio_match:
                    ejercicio_info['numero'] = ejercicio_match.group(1)
                    ejercicio_info['hora'] = ejercicio_match.group(2)

                # Extraer ángulo del tronco
                tronco_match = re.search(r'Ángulo del tronco:\s*([\d.]+)°', match)
                if tronco_match:
                    ejercicio_info['angulo_tronco'] = tronco_match.group(1)

                # Extraer alineación
                alineacion_match = re.search(r'Alineación:\s*(\w+)', match)
                if alineacion_match:
                    ejercicio_info['alineacion'] = alineacion_match.group(1)

                # Extraer ángulos articulares
                codo_izq = re.search(r'Codo izquierdo:\s*([\d.]+)°', match)
                codo_der = re.search(r'Codo derecho:\s*([\d.]+)°', match)
                rodilla_izq = re.search(r'Rodilla izquierda:\s*([\d.]+)°', match)
                rodilla_der = re.search(r'Rodilla derecha:\s*([\d.]+)°', match)

                ejercicio_info['angulos'] = {
                    'codo_izq': codo_izq.group(1) if codo_izq else 'N/A',
                    'codo_der': codo_der.group(1) if codo_der else 'N/A',
                    'rodilla_izq': rodilla_izq.group(1) if rodilla_izq else 'N/A',
                    'rodilla_der': rodilla_der.group(1) if rodilla_der else 'N/A'
                }

                # Extraer simetría
                hombros_match = re.search(r'Hombros:\s*(\w+)\s*\(diferencia:\s*([\d.]+)%\)', match)
                caderas_match = re.search(r'Caderas:\s*(\w+)\s*\(diferencia:\s*([\d.]+)%\)', match)

                ejercicio_info['simetria'] = {
                    'hombros': hombros_match.group(1) if hombros_match else 'N/A',
                    'hombros_diff': hombros_match.group(2) if hombros_match else 'N/A',
                    'caderas': caderas_match.group(1) if caderas_match else 'N/A',
                    'caderas_diff': caderas_match.group(2) if caderas_match else 'N/A'
                }

                analisis_postural.append(ejercicio_info)

            # Remover análisis postural de las observaciones
            observaciones_sin_analisis = re.sub(r'=== ANÁLISIS POSTURAL ===.*?=== FIN ANÁLISIS POSTURAL ===\s*', '', observaciones_certificado, flags=re.DOTALL).strip()

        # Usar examenes_normalizados que ya fue definido arriba (con normalizar_lista_examenes)
        # Si hay observaciones del médico, usarlas en lugar del texto hardcodeado
        for i, examen in enumerate(examenes_normalizados):
            # Si hay observaciones y este es el examen osteomuscular, usar las observaciones
            if observaciones_sin_analisis and "OSTEOMUSCULAR" in examen.upper():
                descripcion = observaciones_sin_analisis
            # Si es audiometría y hay datos de audiometría, usar el diagnóstico del audiograma
            elif "AUDIOMETRÍA" in examen.upper() or "AUDIOMETRIA" in examen.upper():
                if datos_audiometria and datos_audiometria.get('diagnostico'):
                    descripcion = datos_audiometria['diagnostico']
                else:
                    descripcion = textos_examenes.get(examen, "Resultados dentro de parámetros normales.")
            else:
                descripcion = textos_examenes.get(examen, "Resultados dentro de parámetros normales.")
            resultados_generales.append({
                "examen": examen,
                "descripcion": descripcion
            })

        # Recomendaciones médicas
        recomendaciones = datos_wix.get('mdRecomendacionesMedicasAdicionales', '')
        if not recomendaciones:
            recomendaciones = "RECOMENDACIONES GENERALES:\n1. PAUSAS ACTIVAS\n2. HIGIENE POSTURAL\n3. MEDIDAS ERGONOMICAS\n4. TÉCNICAS DE MANEJO DE ESTRÉS\n5. ALIMENTACIÓN BALANCEADA"

        # Mapear médico a imagen de firma y datos
        medico = datos_wix.get('medico', 'JUAN 134')
        firma_medico_map = {
            "SIXTA": "FIRMA-SIXTA.png",
            "JUAN 134": "FIRMA-JUAN134.jpeg",
            "CESAR": "FIRMA-CESAR.jpeg",
            "MARY": "FIRMA-MARY.jpeg",
            "NUBIA": "FIRMA-JUAN134.jpeg",
            "PRESENCIAL": "FIRMA-PRESENCIAL.jpeg",
            "PILAR": "FIRMA_PILAR.png"
        }

        # Datos de cada médico
        medico_datos_map = {
            "SIXTA": {
                "nombre": "SIXTA VIVERO CARRASCAL",
                "registro": "REGISTRO MÉDICO NO 55300504",
                "licencia": "LICENCIA SALUD OCUPACIONAL 583",
                "fecha": "16 DE FEBRERO DE 2021"
            },
            "JUAN 134": {
                "nombre": "JUAN JOSE REATIGA",
                "registro": "C.C.: 7.472.676 - REGISTRO MEDICO NO 14791",
                "licencia": "LICENCIA SALUD OCUPACIONAL 460",
                "fecha": "6 DE JULIO DE 2020"
            },
            "CESAR": {
                "nombre": "CÉSAR ADOLFO ZAMBRANO MARTÍNEZ",
                "registro": "REGISTRO MEDICO NO 1192803570",
                "licencia": "LICENCIA SALUD OCUPACIONAL # 3241",
                "fecha": "13 DE JULIO DE 2021"
            },
            "MARY": {
                "nombre": "",
                "registro": "",
                "licencia": "",
                "fecha": ""
            },
            "NUBIA": {
                "nombre": "JUAN JOSE REATIGA",
                "registro": "C.C.: 7.472.676 - REGISTRO MEDICO NO 14791",
                "licencia": "LICENCIA SALUD OCUPACIONAL 460",
                "fecha": "6 DE JULIO DE 2020"
            },
            "PRESENCIAL": {
                "nombre": "",
                "registro": "",
                "licencia": "",
                "fecha": ""
            },
            "PILAR": {
                "nombre": "DRA. MARIA DEL PILAR PEROZO HERNANDEZ",
                "registro": "C.C.: 1.090.419.867 - MÉDICO OCUPACIONAL",
                "licencia": "Resolución No. 27293",
                "fecha": "05 DE AGOSTO DE 2025"
            }
        }

        # Obtener firma del médico desde archivos locales
        firma_medico_filename = firma_medico_map.get(medico)
        firma_medico_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/static/{firma_medico_filename}" if firma_medico_filename else ""

        # Obtener datos del médico
        datos_medico = medico_datos_map.get(medico, {"nombre": "", "registro": "", "licencia": "", "fecha": ""})
        print(f"✅ Firma médico: {firma_medico_filename}")
        print(f"👨‍⚕️ Médico: {datos_medico['nombre']}")

        # Firma del paciente desde PostgreSQL
        firma_paciente_url = datos_wix.get('firma_paciente')
        if firma_paciente_url:
            print(f"✅ Firma paciente: obtenida desde PostgreSQL (data URI base64)")
        else:
            print(f"ℹ️  Firma paciente: no disponible")

        # Firma del optómetra (siempre la misma)
        firma_optometra_url = "https://bsl-utilidades-yp78a.ondigitalocean.app/static/FIRMA-OPTOMETRA.jpeg"
        print(f"✅ Firma optómetra: FIRMA-OPTOMETRA.jpeg")

        # Generar código de seguridad
        codigo_seguridad = str(uuid.uuid4())

        # Preparar datos para el template
        datos_certificado = {
            "codigo_seguridad": codigo_seguridad,
            "nombres_apellidos": nombre_completo,
            "documento_identidad": datos_wix.get('numeroId', ''),
            "cargo": datos_wix.get('cargo', ''),
            "empresa": datos_wix.get('empresa', ''),
            "genero": datos_wix.get('genero', ''),
            "edad": str(datos_wix.get('edad', '')),
            "fecha_nacimiento": datos_wix.get('fechaNacimiento', ''),
            "estado_civil": datos_wix.get('estadoCivil', ''),
            "hijos": str(datos_wix.get('hijos', '0')),
            "profesion": datos_wix.get('profesionUOficio', ''),
            "email": datos_wix.get('email', ''),
            "celular": datos_wix.get('celular', ''),
            "tipo_examen": datos_wix.get('tipoExamen', ''),
            "foto_paciente": datos_wix.get('foto_paciente', None),
            "fecha_atencion": fecha_formateada,
            "ciudad": "BOGOTÁ" if datos_wix.get('codEmpresa') == 'GODRONE' else datos_wix.get('ciudad', 'Bogotá'),
            "vigencia": "1 año",
            "ips_sede": "Sede norte DHSS0244914",
            "examenes_realizados": examenes_realizados,
            "examenes": examenes,  # Lista de exámenes para verificar tipo
            "resultados_generales": resultados_generales,
            "analisis_postural": analisis_postural,
            "concepto_medico": datos_wix.get('mdConceptoFinal', '') or ('ELEGIBLE PARA EL CARGO' if datos_wix.get('codEmpresa') == 'SANITHELP-JJ' else ''),
            "recomendaciones_medicas": recomendaciones,
            "datos_visual": datos_visual,  # Datos visuales (Optometría/Visiometría)
            "datos_audiometria": datos_audiometria,  # Datos de audiometría
            "medico_nombre": datos_medico['nombre'],
            "medico_registro": datos_medico['registro'],
            "medico_licencia": datos_medico['licencia'],
            "medico_fecha": datos_medico['fecha'],
            "firma_medico_url": firma_medico_url,
            "firma_paciente_url": firma_paciente_url,
            "optometra_nombre": "Dr. Miguel Garzón Rincón",
            "optometra_registro": "C.C.: 79.569.881 - Optómetra Ocupacional Res. 6473 04/07/2017",
            "firma_optometra_url": firma_optometra_url,
            "examenes_detallados": [],
            "logo_url": "https://bsl-utilidades-yp78a.ondigitalocean.app/static/logo-bsl.png",
            # ===== NUEVOS CAMPOS DESDE POSTGRESQL =====
            "eps": datos_wix.get('eps', ''),
            "arl": datos_wix.get('arl', ''),
            "pensiones": datos_wix.get('pensiones', ''),
            "nivel_educativo": datos_wix.get('nivel_educativo', '')
        }

        # Determinar si mostrar aviso de sin soporte
        mostrar_aviso, texto_aviso = determinar_mostrar_sin_soporte(datos_wix)
        datos_certificado["mostrar_sin_soporte"] = mostrar_aviso
        datos_certificado["texto_sin_soporte"] = texto_aviso

        if mostrar_aviso:
            print(f"⚠️ Preview mostrará aviso de pago pendiente para {datos_wix.get('codEmpresa', 'N/A')}")

        # Renderizar template HTML
        print("🎨 Renderizando plantilla HTML para preview...")
        html_content = render_template("certificado_medico.html", **datos_certificado)

        print(f"✅ HTML generado exitosamente para preview")

        # Devolver el HTML directamente
        return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}

    except Exception as e:
        print(f"❌ Error generando preview HTML: {str(e)}")
        traceback.print_exc()

        return f"""
        <html>
            <head><title>Error</title></head>
            <body>
                <h1>Error generando preview del certificado</h1>
                <p><strong>Error:</strong> {str(e)}</p>
                <p><strong>Wix ID:</strong> {wix_id}</p>
            </body>
        </html>
        """, 500, {'Content-Type': 'text/html; charset=utf-8'}

# --- Endpoint: ENVIAR CERTIFICADO POR WHATSAPP ---
@app.route("/enviar-certificado-whatsapp", methods=["POST", "OPTIONS"])
def enviar_certificado_whatsapp():
    """
    Endpoint que busca un certificado por número de cédula o por _id de HistoriaClinica y lo envía por WhatsApp
    Parámetros aceptados:
    - numeroId: buscar por número de cédula
    - historiaId: buscar directamente por _id de HistoriaClinica
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        data = request.get_json()
        numero_id = data.get('numeroId')
        historia_id = data.get('historiaId')

        if not numero_id and not historia_id:
            return jsonify({
                "success": False,
                "message": "Falta el parámetro requerido: numeroId o historiaId"
            }), 400

        print(f"📱 Solicitud de certificado por WhatsApp")

        datos_wix = None
        wix_id = None

        # PRIORIDAD 1: Buscar en PostgreSQL primero
        print(f"🔍 [PRIORIDAD 1] Consultando PostgreSQL...")
        try:
            import psycopg2

            # Usar el mismo patrón de conexión que las funciones que funcionan
            postgres_password = os.getenv("POSTGRES_PASSWORD")
            if not postgres_password:
                print("⚠️ POSTGRES_PASSWORD no configurada")
                raise Exception("POSTGRES_PASSWORD not configured")

            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
                port=int(os.getenv("POSTGRES_PORT", "25060")),
                user=os.getenv("POSTGRES_USER", "doadmin"),
                password=postgres_password,
                database=os.getenv("POSTGRES_DB", "defaultdb"),
                sslmode="require"
            )
            cur = conn.cursor()

            if historia_id:
                print(f"   Buscando por Historia ID: {historia_id}")
                cur.execute('SELECT _id, "numeroId", celular FROM "HistoriaClinica" WHERE _id = %s LIMIT 1', (historia_id,))
            else:
                print(f"   Buscando por Cédula: {numero_id}")
                # Priorizar registros que tengan datos en formularios usando LEFT JOIN
                cur.execute('''
                    SELECT h._id, h."numeroId", h.celular
                    FROM "HistoriaClinica" h
                    LEFT JOIN formularios f ON h._id = f.wix_id
                    WHERE h."numeroId" = %s
                    ORDER BY
                        CASE WHEN f.wix_id IS NOT NULL THEN 0 ELSE 1 END,
                        h._createdDate DESC
                    LIMIT 1
                ''', (numero_id,))

            row = cur.fetchone()
            cur.close()
            conn.close()

            if row:
                wix_id = row[0]
                datos_wix = {
                    '_id': row[0],
                    'numeroId': row[1],
                    'celular': row[2]
                }
                print(f"✅ Encontrado en PostgreSQL: {wix_id}")
            else:
                print(f"⚠️ No se encontró registro en PostgreSQL")
        except Exception as e:
            import traceback
            print(f"⚠️ Error consultando PostgreSQL: {e}")
            print(f"   Traceback: {traceback.format_exc()}")

        # PRIORIDAD 2: Si no se encontró en PostgreSQL, buscar en Wix
        if not datos_wix or not wix_id:
            print(f"🔍 [PRIORIDAD 2 - Fallback] Consultando Wix...")
            wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")

            if historia_id:
                wix_url = f"{wix_base_url}/medidataPaciente?historiaId={historia_id}"
            else:
                wix_url = f"{wix_base_url}/historiaClinicaPorNumeroId?numeroId={numero_id}"

            print(f"   URL: {wix_url}")

            try:
                wix_response = requests.get(wix_url, timeout=10)

                if wix_response.status_code == 200:
                    wix_data = wix_response.json()
                    print(f"✅ Respuesta de Wix: {wix_data}")

                    # Si vino por historiaId, la respuesta es diferente
                    if historia_id:
                        datos_wix = wix_data.get('historiaClinica', {})
                        wix_id = historia_id
                    else:
                        datos_wix = wix_data.get('data')
                        wix_id = wix_data.get('_id')

                    if datos_wix and wix_id:
                        print(f"✅ Encontrado en Wix: {wix_id}")
                else:
                    print(f"⚠️ Wix respondió con código: {wix_response.status_code}")
            except Exception as e:
                print(f"⚠️ Error consultando Wix: {e}")

        # Si no se encontró en ninguna fuente, retornar error
        if not datos_wix or not wix_id:
            mensaje = "No se encontró certificado para este registro" if historia_id else f"No se encontró certificado para cédula: {numero_id}"
            print(f"❌ {mensaje}")
            return jsonify({
                "success": False,
                "message": mensaje + ". Verifica los datos ingresados."
            }), 404

        # Obtener celular del registro de HistoriaClinica
        celular_raw = datos_wix.get('celular', '')
        if not celular_raw:
            return jsonify({
                "success": False,
                "message": "No se encontró número de celular registrado para esta cédula"
            }), 400

        # Limpiar y formatear el celular (agregar prefijo 57 si no lo tiene)
        celular = str(celular_raw).strip().replace(' ', '').replace('-', '')
        if not celular.startswith('57'):
            celular = '57' + celular

        print(f"✅ Certificado encontrado: {wix_id}")
        print(f"📱 Celular de envío: {celular}")

        # Generar URL del certificado PDF
        pdf_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/generar-certificado-desde-wix/{wix_id}"

        print(f"📄 Generando certificado: {pdf_url}")

        # Cache-busting para evitar PDFs antiguos
        cache_buster = int(time.time() * 1000)  # timestamp en milisegundos

        # Generar el PDF (hacer request al endpoint) - Timeout aumentado a 180s por certificados complejos
        pdf_response = requests.get(f"https://bsl-utilidades-yp78a.ondigitalocean.app/api/generar-certificado-pdf/{wix_id}?v={cache_buster}", timeout=180)

        if pdf_response.status_code != 200:
            return jsonify({
                "success": False,
                "message": "Error al generar el certificado PDF"
            }), 500

        # Guardar PDF temporalmente y subirlo a un lugar accesible
        # Para simplificar, vamos a usar la URL del preview como link CON CACHE-BUSTING
        certificado_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/api/generar-certificado-pdf/{wix_id}?v={cache_buster}"

        # Enviar por WhatsApp usando Twilio
        print(f"📤 Enviando certificado por WhatsApp via Twilio a {celular}")

        # Obtener nombre del paciente y cédula
        nombre_completo = f"{datos_wix.get('primerNombre', '')} {datos_wix.get('segundoNombre', '')} {datos_wix.get('primerApellido', '')} {datos_wix.get('segundoApellido', '')}".strip()
        cedula = numero_id if numero_id else datos_wix.get('numeroId', 'N/A')

        # Mensaje con el certificado
        mensaje_whatsapp = f"🏥 *Certificado Médico Ocupacional*\n\n*Paciente:* {nombre_completo}\n*Cédula:* {cedula}\n\n✅ Tu certificado está listo.\n\n_Bienestar y Salud Laboral SAS_"

        try:
            # Importar y usar cliente Twilio
            from twilio.rest import Client as TwilioClient

            twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            twilio_whatsapp_from = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+573008021701')

            if not twilio_account_sid or not twilio_auth_token:
                print("❌ Credenciales de Twilio no configuradas")
                return jsonify({
                    "success": False,
                    "message": "Error de configuración del servicio de WhatsApp"
                }), 500

            twilio_client = TwilioClient(twilio_account_sid, twilio_auth_token)

            # Formatear número de destino
            formatted_number = celular
            if not formatted_number.startswith('whatsapp:'):
                if not formatted_number.startswith('+'):
                    formatted_number = f'+{formatted_number}' if formatted_number.startswith('57') else f'+57{formatted_number}'
                formatted_number = f'whatsapp:{formatted_number}'

            # Enviar mensaje con media (PDF del certificado)
            message = twilio_client.messages.create(
                from_=twilio_whatsapp_from,
                to=formatted_number,
                body=mensaje_whatsapp,
                media_url=[certificado_url]
            )

            print(f"✅ Certificado enviado exitosamente por WhatsApp via Twilio. SID: {message.sid}")

            # Guardar mensaje en base de datos para que aparezca en BSL-PLATAFORMA
            try:
                import psycopg2

                # Normalizar número
                numero_limpio = celular.replace('whatsapp:', '').replace('+', '').strip()
                if not numero_limpio.startswith('57') and len(numero_limpio) == 10:
                    numero_limpio = '57' + numero_limpio
                numero_normalizado = '+' + numero_limpio

                conn = psycopg2.connect(
                    host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
                    port=int(os.getenv("POSTGRES_PORT", "25060")),
                    user=os.getenv("POSTGRES_USER", "doadmin"),
                    password=os.getenv("POSTGRES_PASSWORD"),
                    database=os.getenv("POSTGRES_DB", "defaultdb"),
                    sslmode="require"
                )
                cur = conn.cursor()

                # Buscar o crear conversación
                cur.execute("SELECT id FROM conversaciones_whatsapp WHERE celular = %s", (numero_normalizado,))
                result = cur.fetchone()

                if result:
                    conversacion_id = result[0]
                    cur.execute("UPDATE conversaciones_whatsapp SET fecha_ultima_actividad = NOW() WHERE id = %s", (conversacion_id,))
                else:
                    cur.execute("""
                        INSERT INTO conversaciones_whatsapp (celular, nombre_paciente, estado_actual, fecha_inicio, fecha_ultima_actividad, bot_activo)
                        VALUES (%s, %s, 'activa', NOW(), NOW(), false) RETURNING id
                    """, (numero_normalizado, nombre_completo or 'Cliente WhatsApp'))
                    conversacion_id = cur.fetchone()[0]

                # Guardar mensaje saliente
                cur.execute("""
                    INSERT INTO mensajes_whatsapp (conversacion_id, contenido, direccion, sid_twilio, tipo_mensaje, media_url, timestamp)
                    VALUES (%s, %s, 'saliente', %s, 'document', %s, NOW())
                """, (conversacion_id, mensaje_whatsapp, message.sid, certificado_url))

                conn.commit()
                cur.close()
                conn.close()
                print(f"✅ Mensaje guardado en BD para conversación {conversacion_id}")

            except Exception as db_error:
                print(f"⚠️ Error guardando mensaje en BD (no crítico): {db_error}")

            return jsonify({
                "success": True,
                "message": "Certificado enviado exitosamente por WhatsApp"
            }), 200

        except ImportError:
            print("❌ Twilio no está instalado")
            return jsonify({
                "success": False,
                "message": "Error de configuración del servicio de WhatsApp"
            }), 500

        except Exception as twilio_error:
            print(f"❌ Error enviando por WhatsApp via Twilio: {str(twilio_error)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "success": False,
                "message": "Error al enviar el mensaje por WhatsApp. Verifica el número."
            }), 500

    except Exception as e:
        print(f"❌ Error en enviar_certificado_whatsapp: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Error interno: {str(e)}"
        }), 500


# --- Endpoint: MEDIDATA PANEL PRINCIPAL ---
@app.route("/medidata-principal")
def medidata_principal():
    """
    Servir la página HTML del panel MediData principal
    """
    return send_from_directory('static', 'medidata-principal.html')

# --- PROXY ENDPOINTS PARA MEDIDATA (SOLUCION CORS) ---
@app.route("/api/medidata/<endpoint>", methods=['GET', 'POST', 'OPTIONS'])
def proxy_medidata(endpoint):
    """
    Proxy para endpoints MediData de Wix que maneja CORS correctamente
    """
    if request.method == 'OPTIONS':
        # Manejar preflight CORS
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response, 200

    try:
        # Mapear endpoint a función de Wix (camelCase)
        wix_url = f"https://www.bsl.com.co/_functions/{endpoint}"

        # Preparar la petición
        if request.method == 'GET':
            # Pasar query params
            params = request.args.to_dict()
            response = requests.get(wix_url, params=params, timeout=30)
        else:  # POST
            # Pasar JSON body
            data = request.get_json() if request.is_json else {}
            response = requests.post(wix_url, json=data, timeout=30)

        # Retornar respuesta de Wix con headers CORS
        result = jsonify(response.json())
        result.headers.add('Access-Control-Allow-Origin', '*')
        return result, response.status_code

    except Exception as e:
        logger.error(f"Error en proxy MediData: {str(e)}")
        response = jsonify({'success': False, 'error': str(e)})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500



# Función para generar PDF con Puppeteer desde HTML local (file://)
def generar_pdf_con_puppeteer_local(html_content, output_filename="certificado"):
    """
    Genera un PDF usando Puppeteer desde HTML guardado localmente.
    Estrategia simple que funciona (basada en /test-pdf-do-spaces):
    - Guarda HTML en archivo temporal
    - Usa file:// protocol (sin dependencia de red)
    - Script de Puppeteer simple sin User-Agent ni headers especiales
    - Solo networkidle0 (funciona bien con imágenes de DO Spaces)

    Args:
        html_content: String con el HTML renderizado (imágenes deben ser URLs públicas de DO Spaces)
        output_filename: Nombre base del archivo PDF (sin extensión)

    Returns:
        bytes: Contenido del PDF generado

    Raises:
        Exception: Si falla la generación del PDF
    """
    try:
        print(f"🎭 Generando PDF con Puppeteer (file://)...")
        print(f"📄 Archivo: {output_filename}.pdf")

        # Guardar HTML en archivo temporal
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as html_file:
            html_file.write(html_content)
            html_path = html_file.name

        # Archivo PDF de salida
        pdf_path = html_path.replace('.html', '.pdf')

        # Script de Puppeteer (simple y efectivo)
        project_dir = os.path.dirname(os.path.abspath(__file__))
        puppeteer_script = f"""
const puppeteer = require('{project_dir}/node_modules/puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ]
    }});

    const page = await browser.newPage();

    // Cargar HTML desde archivo local (file://)
    await page.goto('file://{html_path}', {{
        waitUntil: 'networkidle0',
        timeout: 30000
    }});

    // Generar PDF
    await page.pdf({{
        path: '{pdf_path}',
        format: 'Letter',
        printBackground: true,
        margin: {{
            top: '0.5cm',
            right: '0.5cm',
            bottom: '0.5cm',
            left: '0.5cm'
        }}
    }});

    await browser.close();
    console.log('✅ PDF generado exitosamente');
}})();
"""

        # Guardar script de Puppeteer
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as js_file:
            js_file.write(puppeteer_script)
            js_path = js_file.name

        # Ejecutar Puppeteer
        print(f"🚀 Ejecutando Puppeteer...")
        result = subprocess.run(
            ['node', js_path],
            capture_output=True,
            text=True,
            timeout=35,
            cwd=project_dir
        )

        if result.returncode == 0 and os.path.exists(pdf_path):
            print(f"✅ PDF generado exitosamente: {pdf_path}")

            # Leer PDF
            with open(pdf_path, 'rb') as pdf_file:
                pdf_bytes = pdf_file.read()

            # Limpiar archivos temporales
            try:
                os.unlink(html_path)
                os.unlink(js_path)
                os.unlink(pdf_path)
            except:
                pass

            return pdf_bytes
        else:
            error_msg = f"Error generando PDF: stdout={result.stdout}, stderr={result.stderr}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

    except Exception as e:
        print(f"❌ Error en generar_pdf_con_puppeteer_local: {str(e)}")
        raise


# Endpoint de prueba
@app.route('/test-twilio')
def test_twilio():
    """Endpoint de prueba para verificar que el código se cargó"""
    return jsonify({
        'status': 'ok',
        'message': 'Twilio integration code loaded successfully',
        'twilio_available': TWILIO_AVAILABLE,
        'routes_registered': True
    })

# Endpoint de prueba para generar PDF con imagen de DO Spaces
@app.route('/test-pdf-do-spaces')
def test_pdf_do_spaces():
    """
    Endpoint de prueba simple: genera un PDF con la imagen del bucket de DO Spaces
    usando Puppeteer
    """
    try:
        import tempfile
        import subprocess

        # URL de la imagen en DO Spaces
        imagen_url = "https://bsl-app-bucket.sfo3.digitaloceanspaces.com/wix-images/wix-img-d25ac21688d9.jpg"

        # Crear HTML simple con la imagen
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Prueba PDF con imagen DO Spaces</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 40px;
                    text-align: center;
                }}
                h1 {{
                    color: #333;
                    margin-bottom: 30px;
                }}
                img {{
                    max-width: 500px;
                    border: 2px solid #ddd;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                p {{
                    color: #666;
                    margin-top: 20px;
                }}
            </style>
        </head>
        <body>
            <h1>🎉 Prueba de PDF con imagen de DO Spaces</h1>
            <img src="{imagen_url}" alt="Imagen de prueba">
            <p><strong>URL:</strong> {imagen_url}</p>
            <p>Esta imagen fue descargada de Digital Ocean Spaces y renderizada en PDF con Puppeteer.</p>
        </body>
        </html>
        """

        # Guardar HTML temporal
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as html_file:
            html_file.write(html_content)
            html_path = html_file.name

        # Archivo PDF de salida
        pdf_path = html_path.replace('.html', '.pdf')

        # Script de Puppeteer para generar PDF
        project_dir = os.path.dirname(os.path.abspath(__file__))
        puppeteer_script = f"""
const puppeteer = require('{project_dir}/node_modules/puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ]
    }});

    const page = await browser.newPage();

    await page.goto('file://{html_path}', {{
        waitUntil: 'networkidle0',
        timeout: 30000
    }});

    await page.pdf({{
        path: '{pdf_path}',
        format: 'Letter',
        printBackground: true,
        margin: {{
            top: '20px',
            right: '20px',
            bottom: '20px',
            left: '20px'
        }}
    }});

    await browser.close();
    console.log('PDF generado exitosamente');
}})();
"""

        # Guardar script de Puppeteer
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as js_file:
            js_file.write(puppeteer_script)
            js_path = js_file.name

        # Ejecutar Puppeteer
        print(f"🎭 Ejecutando Puppeteer para generar PDF de prueba...")
        result = subprocess.run(
            ['node', js_path],
            capture_output=True,
            text=True,
            timeout=35,
            cwd=project_dir
        )

        if result.returncode == 0 and os.path.exists(pdf_path):
            print(f"✅ PDF generado exitosamente: {pdf_path}")

            # Leer PDF y devolverlo como respuesta
            with open(pdf_path, 'rb') as pdf_file:
                pdf_bytes = pdf_file.read()

            # Limpiar archivos temporales
            try:
                os.unlink(html_path)
                os.unlink(js_path)
                os.unlink(pdf_path)
            except:
                pass

            # Devolver PDF
            response = make_response(pdf_bytes)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = 'inline; filename=test-do-spaces.pdf'
            return response
        else:
            print(f"❌ Error generando PDF:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return jsonify({
                'success': False,
                'error': 'Error generando PDF',
                'stdout': result.stdout,
                'stderr': result.stderr
            }), 500

    except Exception as e:
        print(f"❌ Error en test-pdf-do-spaces: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# ENDPOINTS PARA VER Y EDITAR FORMULARIOS
# ============================================================================

@app.route('/api/formularios', methods=['GET', 'OPTIONS'])
def get_formularios():
    """
    Obtiene todos los formularios de la base de datos PostgreSQL
    Soporta filtros opcionales por query params
    """
    if request.method == 'OPTIONS':
        return '', 200

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        # Obtener password de PostgreSQL
        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            return jsonify({
                "success": False,
                "error": "POSTGRES_PASSWORD no configurado"
            }), 500

        # Conectar a PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )

        # Usar RealDictCursor para obtener resultados como diccionarios
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Query base
        query = "SELECT * FROM formularios ORDER BY fecha_registro DESC"

        # Ejecutar query
        cur.execute(query)
        rows = cur.fetchall()

        # Convertir a lista de diccionarios
        formularios = []
        for row in rows:
            formulario = dict(row)
            # Convertir fecha_registro a string si existe
            if 'fecha_registro' in formulario and formulario['fecha_registro']:
                formulario['fecha_registro'] = formulario['fecha_registro'].isoformat()
            formularios.append(formulario)

        cur.close()
        conn.close()

        return jsonify({
            "success": True,
            "total": len(formularios),
            "data": formularios
        }), 200

    except Exception as e:
        print(f"❌ Error obteniendo formularios: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/actualizar-formulario', methods=['POST', 'OPTIONS'])
def actualizar_formulario():
    """
    Actualiza un formulario en PostgreSQL y sincroniza con Wix
    Recibe JSON con id (PostgreSQL) y campos a actualizar
    """
    if request.method == 'OPTIONS':
        return '', 200

    try:
        import psycopg2

        # Obtener datos del request
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "No se recibieron datos"
            }), 400

        formulario_id = data.get('id')
        wix_id = data.get('wix_id')

        if not formulario_id:
            return jsonify({
                "success": False,
                "error": "El campo 'id' es requerido"
            }), 400

        # Obtener password de PostgreSQL
        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            return jsonify({
                "success": False,
                "error": "POSTGRES_PASSWORD no configurado"
            }), 500

        # Conectar a PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor()

        # Construir UPDATE query dinámicamente
        campos_actualizables = [
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'numero_id', 'cargo', 'empresa', 'cod_empresa', 'celular',
            'genero', 'edad', 'fecha_nacimiento', 'lugar_nacimiento', 'ciudad_residencia',
            'hijos', 'profesion_oficio', 'empresa1', 'empresa2', 'estado_civil',
            'nivel_educativo', 'email', 'estatura', 'peso', 'ejercicio',
            'cirugia_ocular', 'consumo_licor', 'cirugia_programada', 'condicion_medica',
            'dolor_cabeza', 'dolor_espalda', 'ruido_jaqueca', 'embarazo',
            'enfermedad_higado', 'enfermedad_pulmonar', 'fuma', 'hernias',
            'hormigueos', 'presion_alta', 'problemas_azucar', 'problemas_cardiacos',
            'problemas_sueno', 'usa_anteojos', 'usa_lentes_contacto', 'varices',
            'hepatitis', 'familia_hereditarias', 'familia_geneticas', 'familia_diabetes',
            'familia_hipertension', 'familia_infartos', 'familia_cancer',
            'familia_trastornos', 'familia_infecciosas'
        ]

        # Filtrar solo los campos que vienen en el request
        updates = []
        values = []
        for campo in campos_actualizables:
            if campo in data:
                updates.append(f"{campo} = %s")
                values.append(data[campo])

        if not updates:
            return jsonify({
                "success": False,
                "error": "No se especificaron campos para actualizar"
            }), 400

        # Agregar el ID al final de los valores
        values.append(formulario_id)

        # Ejecutar UPDATE
        update_query = f"""
            UPDATE formularios
            SET {', '.join(updates)}
            WHERE id = %s
        """

        print(f"🔄 Actualizando formulario {formulario_id} en PostgreSQL...")
        cur.execute(update_query, values)
        conn.commit()

        cur.close()
        conn.close()

        print(f"✅ Formulario {formulario_id} actualizado en PostgreSQL")

        # SINCRONIZAR CON WIX si existe wix_id
        wix_updated = False
        wix_error = None

        if wix_id:
            try:
                print(f"🔄 Sincronizando con Wix (ID: {wix_id})...")

                # URL base de Wix (puede ser producción o desarrollo)
                wix_base_url = "https://bsl-formulario-f5qx3.ondigitalocean.app"

                # Preparar datos para Wix (mapear nombres de campos)
                wix_data = {
                    '_id': wix_id
                }

                # Mapear campos de PostgreSQL a Wix
                campo_mapping = {
                    'primer_nombre': 'primerNombre',
                    'segundo_nombre': 'segundoNombre',
                    'primer_apellido': 'primerApellido',
                    'segundo_apellido': 'segundoApellido',
                    'numero_id': 'numeroId',
                    'celular': 'celular',
                    'cargo': 'cargo',
                    'empresa': 'empresa',
                    'cod_empresa': 'codEmpresa',
                    'genero': 'genero',
                    'edad': 'edad',
                    'fecha_nacimiento': 'fechaNacimiento',
                    'lugar_nacimiento': 'lugarNacimiento',
                    'ciudad_residencia': 'ciudadResidencia',
                    'hijos': 'hijos',
                    'profesion_oficio': 'profesionOficio',
                    'empresa1': 'empresa1',
                    'empresa2': 'empresa2',
                    'estado_civil': 'estadoCivil',
                    'nivel_educativo': 'nivelEducativo',
                    'email': 'email'
                }

                # Agregar campos al payload de Wix
                for pg_field, wix_field in campo_mapping.items():
                    if pg_field in data:
                        wix_data[wix_field] = data[pg_field]

                # Llamar al endpoint de actualización de Wix
                wix_response = requests.post(
                    f"{wix_base_url}/actualizarFormulario",
                    json=wix_data,
                    timeout=10
                )

                if wix_response.status_code == 200:
                    wix_result = wix_response.json()
                    if wix_result.get('success'):
                        print(f"✅ Formulario sincronizado con Wix")
                        wix_updated = True
                    else:
                        wix_error = wix_result.get('error', 'Error desconocido en Wix')
                        print(f"⚠️ Error al actualizar en Wix: {wix_error}")
                else:
                    wix_error = f"HTTP {wix_response.status_code}"
                    print(f"⚠️ Error al llamar a Wix: {wix_error}")

            except Exception as e:
                wix_error = str(e)
                print(f"⚠️ Excepción al sincronizar con Wix: {wix_error}")

        return jsonify({
            "success": True,
            "message": "Formulario actualizado correctamente",
            "postgres_updated": True,
            "wix_updated": wix_updated,
            "wix_error": wix_error
        }), 200

    except Exception as e:
        print(f"❌ Error actualizando formulario: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/ver-formularios.html', methods=['GET'])
def ver_formularios_page():
    """
    Sirve la página HTML para ver y editar formularios
    """
    html_content = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ver y Editar Formularios - BSL</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Figtree', sans-serif;
            background: #F9FAFB;
            padding: 40px 20px;
            color: #333;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        h1 {
            font-size: 32px;
            font-weight: 700;
            color: #1F2937;
            margin-bottom: 40px;
            text-align: center;
        }

        .loading {
            text-align: center;
            padding: 60px 20px;
            font-size: 18px;
            color: #6B7280;
        }

        .formularios-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 24px;
        }

        .formulario-card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .formulario-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
        }

        .formulario-header {
            border-bottom: 2px solid #E5E7EB;
            padding-bottom: 16px;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .formulario-id {
            display: inline-block;
            background: #00B8E6;
            color: white;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
        }

        .edit-btn {
            background: #10B981;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        .edit-btn:hover {
            background: #059669;
        }

        .section-title {
            font-size: 16px;
            font-weight: 600;
            color: #1F2937;
            margin: 16px 0 12px 0;
        }

        .dato {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #F3F4F6;
        }

        .dato-label {
            font-weight: 500;
            color: #6B7280;
        }

        .dato-value {
            font-weight: 400;
            color: #1F2937;
        }

        .foto-container {
            margin: 16px 0;
            text-align: center;
        }

        .foto-container img {
            max-width: 100%;
            max-height: 200px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        /* Modal styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            overflow: auto;
            background-color: rgba(0, 0, 0, 0.5);
        }

        .modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 30px;
            border: 1px solid #888;
            border-radius: 12px;
            width: 90%;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
        }

        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }

        .modal-header h2 {
            font-size: 24px;
            font-weight: 700;
            color: #1F2937;
        }

        .close {
            color: #aaa;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }

        .close:hover,
        .close:focus {
            color: #000;
        }

        .form-group {
            margin-bottom: 16px;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #374151;
        }

        .form-group input,
        .form-group select {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #D1D5DB;
            border-radius: 6px;
            font-size: 14px;
            font-family: 'Figtree', sans-serif;
        }

        .form-group input:focus,
        .form-group select:focus {
            outline: none;
            border-color: #00B8E6;
            box-shadow: 0 0 0 3px rgba(0, 184, 230, 0.1);
        }

        .form-actions {
            display: flex;
            gap: 12px;
            margin-top: 24px;
        }

        .btn-primary {
            flex: 1;
            background: #00B8E6;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        .btn-primary:hover {
            background: #0095BD;
        }

        .btn-primary:disabled {
            background: #9CA3AF;
            cursor: not-allowed;
        }

        .btn-secondary {
            flex: 1;
            background: #6B7280;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }

        .btn-secondary:hover {
            background: #4B5563;
        }

        .success-message {
            background: #D1FAE5;
            color: #065F46;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 16px;
            display: none;
        }

        .error-message {
            background: #FEE2E2;
            color: #991B1B;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 16px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Ver y Editar Formularios</h1>
        <div id="loading" class="loading">Cargando formularios...</div>
        <div id="formularios-container" class="formularios-grid"></div>
    </div>

    <!-- Modal de edición -->
    <div id="editModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>✏️ Editar Formulario</h2>
                <span class="close" onclick="closeModal()">&times;</span>
            </div>

            <div id="successMessage" class="success-message"></div>
            <div id="errorMessage" class="error-message"></div>

            <form id="editForm">
                <input type="hidden" id="edit_id" name="id">
                <input type="hidden" id="edit_wix_id" name="wix_id">

                <div class="section-title">Información Personal</div>

                <div class="form-group">
                    <label>Primer Nombre</label>
                    <input type="text" id="edit_primer_nombre" name="primer_nombre">
                </div>

                <div class="form-group">
                    <label>Segundo Nombre</label>
                    <input type="text" id="edit_segundo_nombre" name="segundo_nombre">
                </div>

                <div class="form-group">
                    <label>Primer Apellido</label>
                    <input type="text" id="edit_primer_apellido" name="primer_apellido">
                </div>

                <div class="form-group">
                    <label>Segundo Apellido</label>
                    <input type="text" id="edit_segundo_apellido" name="segundo_apellido">
                </div>

                <div class="form-group">
                    <label>Número de Identificación</label>
                    <input type="text" id="edit_numero_id" name="numero_id">
                </div>

                <div class="form-group">
                    <label>Celular</label>
                    <input type="text" id="edit_celular" name="celular">
                </div>

                <div class="form-group">
                    <label>Email</label>
                    <input type="email" id="edit_email" name="email">
                </div>

                <div class="section-title">Información Laboral</div>

                <div class="form-group">
                    <label>Cargo</label>
                    <input type="text" id="edit_cargo" name="cargo">
                </div>

                <div class="form-group">
                    <label>Empresa</label>
                    <input type="text" id="edit_empresa" name="empresa">
                </div>

                <div class="form-group">
                    <label>Código Empresa</label>
                    <input type="text" id="edit_cod_empresa" name="cod_empresa">
                </div>

                <div class="section-title">Información Adicional</div>

                <div class="form-group">
                    <label>Género</label>
                    <select id="edit_genero" name="genero">
                        <option value="">Seleccionar...</option>
                        <option value="MASCULINO">Masculino</option>
                        <option value="FEMENINO">Femenino</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Edad</label>
                    <input type="number" id="edit_edad" name="edad">
                </div>

                <div class="form-group">
                    <label>Fecha de Nacimiento</label>
                    <input type="text" id="edit_fecha_nacimiento" name="fecha_nacimiento" placeholder="DD/MM/YYYY">
                </div>

                <div class="form-group">
                    <label>Ciudad de Residencia</label>
                    <input type="text" id="edit_ciudad_residencia" name="ciudad_residencia">
                </div>

                <div class="form-actions">
                    <button type="button" class="btn-secondary" onclick="closeModal()">Cancelar</button>
                    <button type="submit" class="btn-primary" id="saveBtn">Guardar Cambios</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        let formularios = [];
        let currentFormulario = null;

        // Cargar formularios al iniciar
        window.addEventListener('DOMContentLoaded', async () => {
            await loadFormularios();
        });

        async function loadFormularios() {
            try {
                const response = await fetch('/api/formularios');
                const data = await response.json();

                if (data.success) {
                    formularios = data.data;
                    renderFormularios();
                } else {
                    document.getElementById('loading').innerHTML = '❌ Error: ' + data.error;
                }
            } catch (error) {
                document.getElementById('loading').innerHTML = '❌ Error al cargar formularios: ' + error.message;
            }
        }

        function renderFormularios() {
            const container = document.getElementById('formularios-container');
            const loading = document.getElementById('loading');

            loading.style.display = 'none';

            if (formularios.length === 0) {
                container.innerHTML = '<p style="text-align: center; padding: 40px;">No se encontraron formularios</p>';
                return;
            }

            container.innerHTML = formularios.map(form => {
                const fecha = new Date(form.fecha_registro).toLocaleString('es-CO');

                return `
                    <div class="formulario-card">
                        <div class="formulario-header">
                            <div>
                                <div class="formulario-id">ID: ${form.id}</div>
                                ${form.wix_id ? `<div class="formulario-id" style="background: #10B981; margin-top: 8px;">Wix ID: ${form.wix_id}</div>` : ''}
                            </div>
                            <button class="edit-btn" onclick="openEditModal(${form.id})">✏️ Editar</button>
                        </div>

                        ${form.foto ? `
                            <div class="foto-container">
                                <img src="${form.foto}" alt="Foto del paciente">
                            </div>
                        ` : ''}

                        <div class="section-title">👤 Información Personal</div>
                        <div class="dato">
                            <span class="dato-label">Nombre Completo:</span>
                            <span class="dato-value">${form.primer_nombre || ''} ${form.segundo_nombre || ''} ${form.primer_apellido || ''} ${form.segundo_apellido || ''}</span>
                        </div>
                        <div class="dato">
                            <span class="dato-label">Número ID:</span>
                            <span class="dato-value">${form.numero_id || 'N/A'}</span>
                        </div>
                        <div class="dato">
                            <span class="dato-label">Celular:</span>
                            <span class="dato-value">${form.celular || 'N/A'}</span>
                        </div>
                        <div class="dato">
                            <span class="dato-label">Email:</span>
                            <span class="dato-value">${form.email || 'N/A'}</span>
                        </div>

                        <div class="section-title">💼 Información Laboral</div>
                        <div class="dato">
                            <span class="dato-label">Cargo:</span>
                            <span class="dato-value">${form.cargo || 'N/A'}</span>
                        </div>
                        <div class="dato">
                            <span class="dato-label">Empresa:</span>
                            <span class="dato-value">${form.empresa || 'N/A'}</span>
                        </div>
                        <div class="dato">
                            <span class="dato-label">Código Empresa:</span>
                            <span class="dato-value">${form.cod_empresa || 'N/A'}</span>
                        </div>

                        <div class="section-title">📅 Otros Datos</div>
                        <div class="dato">
                            <span class="dato-label">Género:</span>
                            <span class="dato-value">${form.genero || 'N/A'}</span>
                        </div>
                        <div class="dato">
                            <span class="dato-label">Edad:</span>
                            <span class="dato-value">${form.edad || 'N/A'}</span>
                        </div>
                        <div class="dato">
                            <span class="dato-label">Fecha Nacimiento:</span>
                            <span class="dato-value">${form.fecha_nacimiento || 'N/A'}</span>
                        </div>
                        <div class="dato">
                            <span class="dato-label">Ciudad:</span>
                            <span class="dato-value">${form.ciudad_residencia || 'N/A'}</span>
                        </div>
                        <div class="dato">
                            <span class="dato-label">Fecha Registro:</span>
                            <span class="dato-value">${fecha}</span>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function openEditModal(formularioId) {
            currentFormulario = formularios.find(f => f.id === formularioId);
            if (!currentFormulario) return;

            // Llenar el formulario con los datos actuales
            document.getElementById('edit_id').value = currentFormulario.id;
            document.getElementById('edit_wix_id').value = currentFormulario.wix_id || '';
            document.getElementById('edit_primer_nombre').value = currentFormulario.primer_nombre || '';
            document.getElementById('edit_segundo_nombre').value = currentFormulario.segundo_nombre || '';
            document.getElementById('edit_primer_apellido').value = currentFormulario.primer_apellido || '';
            document.getElementById('edit_segundo_apellido').value = currentFormulario.segundo_apellido || '';
            document.getElementById('edit_numero_id').value = currentFormulario.numero_id || '';
            document.getElementById('edit_celular').value = currentFormulario.celular || '';
            document.getElementById('edit_email').value = currentFormulario.email || '';
            document.getElementById('edit_cargo').value = currentFormulario.cargo || '';
            document.getElementById('edit_empresa').value = currentFormulario.empresa || '';
            document.getElementById('edit_cod_empresa').value = currentFormulario.cod_empresa || '';
            document.getElementById('edit_genero').value = currentFormulario.genero || '';
            document.getElementById('edit_edad').value = currentFormulario.edad || '';
            document.getElementById('edit_fecha_nacimiento').value = currentFormulario.fecha_nacimiento || '';
            document.getElementById('edit_ciudad_residencia').value = currentFormulario.ciudad_residencia || '';

            // Limpiar mensajes
            document.getElementById('successMessage').style.display = 'none';
            document.getElementById('errorMessage').style.display = 'none';

            // Mostrar modal
            document.getElementById('editModal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('editModal').style.display = 'none';
            currentFormulario = null;
        }

        // Cerrar modal al hacer clic fuera
        window.onclick = function(event) {
            const modal = document.getElementById('editModal');
            if (event.target === modal) {
                closeModal();
            }
        }

        // Manejar envío del formulario
        document.getElementById('editForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const saveBtn = document.getElementById('saveBtn');
            const successMsg = document.getElementById('successMessage');
            const errorMsg = document.getElementById('errorMessage');

            // Ocultar mensajes
            successMsg.style.display = 'none';
            errorMsg.style.display = 'none';

            // Deshabilitar botón
            saveBtn.disabled = true;
            saveBtn.textContent = 'Guardando...';

            try {
                // Recopilar datos del formulario
                const formData = {
                    id: parseInt(document.getElementById('edit_id').value),
                    wix_id: document.getElementById('edit_wix_id').value || null,
                    primer_nombre: document.getElementById('edit_primer_nombre').value,
                    segundo_nombre: document.getElementById('edit_segundo_nombre').value,
                    primer_apellido: document.getElementById('edit_primer_apellido').value,
                    segundo_apellido: document.getElementById('edit_segundo_apellido').value,
                    numero_id: document.getElementById('edit_numero_id').value,
                    celular: document.getElementById('edit_celular').value,
                    email: document.getElementById('edit_email').value,
                    cargo: document.getElementById('edit_cargo').value,
                    empresa: document.getElementById('edit_empresa').value,
                    cod_empresa: document.getElementById('edit_cod_empresa').value,
                    genero: document.getElementById('edit_genero').value,
                    edad: parseInt(document.getElementById('edit_edad').value) || null,
                    fecha_nacimiento: document.getElementById('edit_fecha_nacimiento').value,
                    ciudad_residencia: document.getElementById('edit_ciudad_residencia').value
                };

                // Enviar petición
                const response = await fetch('/api/actualizar-formulario', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                const result = await response.json();

                if (result.success) {
                    successMsg.textContent = '✅ Formulario actualizado correctamente';
                    if (result.wix_updated) {
                        successMsg.textContent += ' (sincronizado con Wix)';
                    } else if (result.wix_error) {
                        successMsg.textContent += ` (PostgreSQL actualizado, pero error en Wix: ${result.wix_error})`;
                    }
                    successMsg.style.display = 'block';

                    // Recargar formularios después de 1.5 segundos
                    setTimeout(async () => {
                        await loadFormularios();
                        closeModal();
                    }, 1500);
                } else {
                    errorMsg.textContent = '❌ Error: ' + result.error;
                    errorMsg.style.display = 'block';
                }
            } catch (error) {
                errorMsg.textContent = '❌ Error al guardar: ' + error.message;
                errorMsg.style.display = 'block';
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Guardar Cambios';
            }
        });
    </script>
</body>
</html>"""

    return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}


# ================================================
# ENDPOINTS V2: PUPPETEER + POSTGRESQL → WIX FALLBACK
# (Reemplazo de endpoints Alegra que usaban iLovePDF)
# ================================================

@app.route("/preview-certificado-v2/<wix_id>", methods=["GET", "OPTIONS"])
def preview_certificado_v2(wix_id):
    """
    Endpoint para previsualizar el certificado en HTML con lógica:
    1. PostgreSQL FORMULARIO (prioridad)
    2. Wix FORMULARIO (fallback si PostgreSQL no tiene datos)

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Returns:
        HTML renderizado del certificado con datos demográficos
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print(f"🔍 [V2] Previsualizando certificado HTML para Wix ID: {wix_id}")

        # Consultar datos desde Wix HTTP Functions
        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")

        # 1. Obtener datos de HistoriaClinica
        try:
            wix_url = f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}"
            response = requests.get(wix_url, timeout=10)

            if response.status_code == 200:
                wix_response = response.json()
                datos_wix = wix_response.get("data", {})

                if not datos_wix:
                    print(f"❌ [V2] Error: Wix retornó respuesta vacía para ID: {wix_id}")
                    return f"<html><body><h1>Error</h1><p>No se encontraron datos del paciente en el sistema (ID: {wix_id})</p></body></html>", 404

                print(f"✅ [V2] Datos obtenidos de HistoriaClinica para ID: {wix_id}")
            else:
                print(f"❌ [V2] Error consultando Wix: {response.status_code}")
                return f"<html><body><h1>Error</h1><p>Error al obtener datos del paciente (código {response.status_code})</p></body></html>", 500

        except Exception as e:
            print(f"❌ [V2] Error de conexión a Wix: {str(e)}")
            traceback.print_exc()
            return f"<html><body><h1>Error</h1><p>Error de conexión con el sistema de datos. Intenta nuevamente.</p></body></html>", 500

        # 2. Consultar FORMULARIO desde PostgreSQL (fuente principal)
        print(f"📋 [V2] Consultando FORMULARIO desde PostgreSQL con wix_id={wix_id}")

        datos_formulario = obtener_datos_formulario_postgres(wix_id)

        if datos_formulario:
            print(f"✅ [V2] Datos del formulario obtenidos desde PostgreSQL")

            # Agregar datos demográficos a datos_wix
            if datos_formulario.get('edad'):
                datos_wix['edad'] = datos_formulario.get('edad')
            if datos_formulario.get('genero'):
                datos_wix['genero'] = datos_formulario.get('genero')
            if datos_formulario.get('estadoCivil'):
                datos_wix['estadoCivil'] = datos_formulario.get('estadoCivil')
            if datos_formulario.get('hijos'):
                datos_wix['hijos'] = datos_formulario.get('hijos')
            if datos_formulario.get('email'):
                datos_wix['email'] = datos_formulario.get('email')
            if datos_formulario.get('profesionUOficio'):
                datos_wix['profesionUOficio'] = datos_formulario.get('profesionUOficio')
            if datos_formulario.get('ciudadDeResidencia'):
                datos_wix['ciudadDeResidencia'] = datos_formulario.get('ciudadDeResidencia')
            if datos_formulario.get('fechaNacimiento'):
                datos_wix['fechaNacimiento'] = datos_formulario.get('fechaNacimiento')

            # Foto y firma del paciente
            if datos_formulario.get('foto'):
                foto_pg = datos_formulario.get('foto')
                # Si es un URI de Wix, convertir a URL pública (iLovePDF puede cargarla directamente)
                if foto_pg and foto_pg.startswith('wix:image://v1/'):
                    print(f"🔄 [V2] Convirtiendo URI de Wix (PostgreSQL) a URL pública...")
                    parts = foto_pg.replace('wix:image://v1/', '').split('/')
                    if len(parts) > 0:
                        image_id = parts[0]
                        foto_url_publica = f"https://static.wixstatic.com/media/{image_id}"
                        datos_wix['foto_paciente'] = foto_url_publica
                        print(f"✅ [V2] URL pública de foto: {foto_url_publica}")
                else:
                    datos_wix['foto_paciente'] = foto_pg
                print(f"✅ [V2] Foto obtenida de PostgreSQL")
            else:
                datos_wix['foto_paciente'] = None

            if datos_formulario.get('firma'):
                datos_wix['firma_paciente'] = datos_formulario.get('firma')
                print(f"✅ [V2] Firma obtenida de PostgreSQL")
            else:
                datos_wix['firma_paciente'] = None

            # Campos de seguridad social
            if datos_formulario.get('eps'):
                datos_wix['eps'] = datos_formulario.get('eps')
            if datos_formulario.get('arl'):
                datos_wix['arl'] = datos_formulario.get('arl')
            if datos_formulario.get('pensiones'):
                datos_wix['pensiones'] = datos_formulario.get('pensiones')
            if datos_formulario.get('nivelEducativo'):
                datos_wix['nivel_educativo'] = datos_formulario.get('nivelEducativo')

            print(f"📊 [V2] Datos integrados desde PostgreSQL: edad={datos_wix.get('edad')}, genero={datos_wix.get('genero')}, eps={datos_wix.get('eps')}")
        else:
            print(f"⚠️ [V2] No se encontró formulario en PostgreSQL, intentando Wix como fallback...")

            # Fallback: Consultar FORMULARIO desde Wix
            try:
                formulario_url = f"{wix_base_url}/formularioPorIdGeneral?idGeneral={wix_id}"
                print(f"🔗 [V2] URL de consulta Wix: {formulario_url}")
                formulario_response = requests.get(formulario_url, timeout=10)

                if formulario_response.status_code == 200:
                    formulario_data = formulario_response.json()

                    if formulario_data.get('success') and formulario_data.get('item'):
                        formulario = formulario_data['item']
                        print(f"✅ [V2] Datos demográficos obtenidos de Wix FORMULARIO (fallback)")

                        # Agregar datos demográficos a datos_wix
                        datos_wix['edad'] = formulario.get('edad')
                        datos_wix['genero'] = formulario.get('genero')
                        datos_wix['estadoCivil'] = formulario.get('estadoCivil')
                        datos_wix['hijos'] = formulario.get('hijos')
                        datos_wix['email'] = formulario.get('email')
                        datos_wix['profesionUOficio'] = formulario.get('profesionUOficio')
                        datos_wix['ciudadDeResidencia'] = formulario.get('ciudadDeResidencia')
                        datos_wix['fechaNacimiento'] = formulario.get('fechaNacimiento')
                        # Procesar foto de Wix (convertir wix:image:// a URL pública)
                        # iLovePDF usa Puppeteer/Chromium que puede cargar URLs de Wix directamente
                        foto_wix = formulario.get('foto')
                        if foto_wix and foto_wix.startswith('wix:image://v1/'):
                            print(f"🔄 [V2] Convirtiendo URI de Wix a URL pública...")
                            parts = foto_wix.replace('wix:image://v1/', '').split('/')
                            if len(parts) > 0:
                                image_id = parts[0]
                                foto_url_publica = f"https://static.wixstatic.com/media/{image_id}"
                                datos_wix['foto_paciente'] = foto_url_publica
                                print(f"✅ [V2] URL pública de foto: {foto_url_publica}")
                        else:
                            datos_wix['foto_paciente'] = foto_wix

                        datos_wix['firma_paciente'] = formulario.get('firma')

                        # Campos de seguridad social desde Wix
                        if formulario.get('eps'):
                            datos_wix['eps'] = formulario.get('eps')
                        if formulario.get('arl'):
                            datos_wix['arl'] = formulario.get('arl')
                        if formulario.get('pensiones'):
                            datos_wix['pensiones'] = formulario.get('pensiones')
                        if formulario.get('nivelEducativo'):
                            datos_wix['nivel_educativo'] = formulario.get('nivelEducativo')
                    else:
                        print(f"⚠️ [V2] No se encontró formulario en Wix para idGeneral: {wix_id}")
                        datos_wix['foto_paciente'] = None
                        datos_wix['firma_paciente'] = None
                else:
                    print(f"⚠️ [V2] Error al consultar FORMULARIO en Wix: {formulario_response.status_code}")
                    datos_wix['foto_paciente'] = None
                    datos_wix['firma_paciente'] = None
            except Exception as e:
                print(f"❌ [V2] Error consultando FORMULARIO en Wix: {e}")
                datos_wix['foto_paciente'] = None
                datos_wix['firma_paciente'] = None

        # 3. Ahora generar el preview HTML completo con los datos enriquecidos
        print(f"✅ [V2] Generando preview HTML completo con datos de FORMULARIO")

        # Guardar datos enriquecidos temporalmente en flask.g para que preview_certificado_html los use
        import flask
        flask.g.datos_wix_enriquecidos = datos_wix
        flask.g.usar_datos_formulario = True

        # Llamar internamente al preview normal que ya tiene toda la lógica de renderizado
        return preview_certificado_html(wix_id)

    except Exception as e:
        print(f"❌ [V2] Error general: {str(e)}")
        traceback.print_exc()
        return f"<html><body><h1>Error</h1><p>{str(e)}</p></body></html>", 500


@app.route("/generar-certificado-v2/<wix_id>", methods=["GET", "OPTIONS"])
def generar_certificado_v2(wix_id):
    """
    Endpoint que muestra loader mientras se genera el certificado con Puppeteer V2
    (Usa la lógica de fallback PostgreSQL → Wix FORMULARIO)

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    # Mostrar página de loader (reutiliza el mismo loader que Puppeteer)
    # Pero con endpoint API diferente
    loader_html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generando Certificado...</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: #f5f5f5;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .logo {{
            width: 150px;
            height: 150px;
            margin-bottom: 20px;
            animation: pulse 1.5s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.7; transform: scale(0.95); }}
        }}
        h2 {{
            color: #333;
            margin-bottom: 10px;
        }}
        p {{
            color: #666;
        }}
        .spinner {{
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        .error {{
            color: #e74c3c;
            display: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <img src="https://static.wixstatic.com/media/e09c3b_93e0f27ed89a4f3a9d10cdeb0d0a4186~mv2.png"
             alt="BSL Logo" class="logo">
        <h2 id="status-text">Generando su certificado...</h2>
        <div class="spinner" id="spinner"></div>
        <p id="status-detail">Por favor espere mientras preparamos su documento</p>
        <p class="error" id="error-msg"></p>
    </div>
    <script>
        async function generarPDF() {{
            try {{
                const response = await fetch('/api/generar-certificado-pdf-v2/{wix_id}');

                if (response.ok) {{
                    // Si es exitoso, descargar el PDF
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'certificado_medico.pdf';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();

                    // Mostrar éxito
                    document.getElementById('status-text').textContent = '¡Certificado generado!';
                    document.getElementById('status-detail').textContent = 'La descarga debería comenzar automáticamente';
                    document.getElementById('spinner').style.display = 'none';
                }} else {{
                    const error = await response.json();
                    throw new Error(error.error || 'Error desconocido');
                }}
            }} catch (error) {{
                document.getElementById('status-text').textContent = 'Error al generar certificado';
                document.getElementById('spinner').style.display = 'none';
                document.getElementById('error-msg').style.display = 'block';
                document.getElementById('error-msg').textContent = error.message;
            }}
        }}

        // Iniciar generación al cargar
        generarPDF();
    </script>
</body>
</html>'''
    return loader_html, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route("/api/generar-certificado-pdf-v2/<wix_id>", methods=["GET", "OPTIONS"])
def api_generar_certificado_pdf_v2(wix_id):
    """
    Endpoint API que genera el PDF del certificado usando Puppeteer
    con lógica de fallback: PostgreSQL FORMULARIO → Wix FORMULARIO

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Query params opcionales:
        guardar_drive: true/false (default: false)
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print(f"📋 [V2/iLovePDF] Generando certificado para Wix ID: {wix_id}")

        # Obtener parámetros opcionales
        guardar_drive = request.args.get('guardar_drive', 'false').lower() == 'true'

        print(f"🔧 [V2] Motor de conversión: iLovePDF")
        print(f"🔧 [V2] Lógica de datos: PostgreSQL → Wix FORMULARIO fallback")

        # Construir URL del preview HTML V2 (con fallback PostgreSQL → Wix)
        # NOTA: No usar cache buster (?v=) porque iLovePDF puede tener problemas con query params
        preview_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/preview-certificado-v2/{wix_id}"
        print(f"🔗 [V2] URL del preview: {preview_url}")

        # Obtener numeroId para el nombre del archivo
        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")
        numero_id = wix_id  # fallback
        try:
            wix_url = f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}"
            response = requests.get(wix_url, timeout=10)
            if response.status_code == 200:
                wix_response = response.json()
                datos_wix = wix_response.get("data", {})
                numero_id = datos_wix.get('numeroId', wix_id)
        except:
            pass

        # Generar PDF usando iLovePDF
        print(f"📄 [V2] Iniciando generación con iLovePDF...")
        try:
            pdf_content = ilovepdf_html_to_pdf_from_url(
                html_url=preview_url,
                output_filename=f"certificado_v2_{numero_id}"
            )

            # Guardar PDF localmente
            print("💾 [V2] Guardando PDF localmente...")
            documento_sanitized = str(numero_id).replace(" ", "_").replace("/", "_").replace("\\", "_")
            local = f"certificado_v2_{documento_sanitized}.pdf"

            with open(local, "wb") as f:
                f.write(pdf_content)

            print(f"✅ [V2] PDF generado con iLovePDF: {local} ({len(pdf_content)} bytes)")

            # Enviar archivo como descarga
            response = send_file(
                local,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"certificado_medico_{documento_sanitized}.pdf"
            )

            # Configurar CORS
            response.headers["Access-Control-Allow-Origin"] = "*"

            # Limpiar archivo temporal después del envío
            @response.call_on_close
            def cleanup():
                try:
                    os.remove(local)
                    print(f"🗑️  [V2] Archivo temporal eliminado: {local}")
                except Exception as e:
                    print(f"⚠️  [V2] Error al eliminar archivo temporal: {e}")

            return response

        except Exception as e:
            print(f"❌ [V2] Error generando PDF con iLovePDF: {e}")
            traceback.print_exc()
            error_response = jsonify({
                "success": False,
                "error": f"Error generando PDF con iLovePDF: {str(e)}"
            })
            error_response.headers["Access-Control-Allow-Origin"] = "*"
            return error_response, 500

    except Exception as e:
        print(f"❌ [V2] Error general: {e}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "error": str(e),
            "wix_id": wix_id
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"

        return error_response, 500


# =====================================================
# ENDPOINT V2 CON SUBIDA A GOOGLE DRIVE
# =====================================================

# Carpeta de Google Drive para certificados V2
GOOGLE_DRIVE_FOLDER_ID_CERTIFICADOS_V2 = os.getenv(
    "GOOGLE_DRIVE_FOLDER_ID_CERTIFICADOS_V2",
    "1gUOuJdmS38bSk7cqu5evXOl9PdZ17HTJ"  # valor por defecto
)


@app.route("/generar-certificado-v2-drive/<wix_id>", methods=["GET", "OPTIONS"])
def generar_certificado_v2_drive(wix_id):
    """
    Endpoint que muestra loader mientras se genera el certificado V2 y lo sube a Drive

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    loader_html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generando Certificado...</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: #f5f5f5;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .logo {{
            width: 150px;
            height: 150px;
            margin-bottom: 20px;
            animation: pulse 1.5s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.7; transform: scale(0.95); }}
        }}
        h2 {{
            color: #333;
            margin-bottom: 10px;
        }}
        p {{
            color: #666;
        }}
        .spinner {{
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        .error {{
            color: #e74c3c;
            display: none;
        }}
        .success-link {{
            display: none;
            margin-top: 20px;
        }}
        .success-link a {{
            color: #3498db;
            text-decoration: none;
            font-weight: bold;
        }}
        .success-link a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <img src="https://static.wixstatic.com/media/e09c3b_93e0f27ed89a4f3a9d10cdeb0d0a4186~mv2.png"
             alt="BSL Logo" class="logo">
        <h2 id="status-text">Generando su certificado...</h2>
        <div class="spinner" id="spinner"></div>
        <p id="status-detail">Por favor espere mientras preparamos su documento</p>
        <p class="error" id="error-msg"></p>
        <div class="success-link" id="success-link">
            <a id="drive-link" href="#" target="_blank">📄 Abrir certificado en Google Drive</a>
        </div>
    </div>
    <script>
        async function generarPDF() {{
            try {{
                const response = await fetch('/api/generar-certificado-pdf-v2-drive/{wix_id}');
                const data = await response.json();

                if (data.success) {{
                    document.getElementById('status-text').textContent = '¡Certificado generado!';
                    document.getElementById('status-detail').textContent = 'El certificado ha sido guardado en Google Drive';
                    document.getElementById('spinner').style.display = 'none';
                    document.getElementById('drive-link').href = data.drive_link;
                    document.getElementById('success-link').style.display = 'block';
                }} else {{
                    throw new Error(data.error || 'Error desconocido');
                }}
            }} catch (error) {{
                document.getElementById('status-text').textContent = 'Error al generar certificado';
                document.getElementById('spinner').style.display = 'none';
                document.getElementById('error-msg').style.display = 'block';
                document.getElementById('error-msg').textContent = error.message;
            }}
        }}

        generarPDF();
    </script>
</body>
</html>'''
    return loader_html, 200, {
        'Content-Type': 'text/html; charset=utf-8',
        'Access-Control-Allow-Origin': '*'
    }


@app.route("/api/generar-certificado-pdf-v2-drive/<wix_id>", methods=["GET", "OPTIONS"])
def api_generar_certificado_pdf_v2_drive(wix_id):
    """
    Endpoint API que genera el PDF del certificado V2 y lo sube a Google Drive

    Args:
        wix_id: ID del registro en la colección HistoriaClinica de Wix

    Returns:
        JSON con success, drive_link, file_name
    """
    if request.method == "OPTIONS":
        response_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
        return ("", 204, response_headers)

    try:
        print(f"📋 [V2-Drive] Generando certificado para Wix ID: {wix_id}")
        print(f"🔧 [V2-Drive] Motor de conversión: iLovePDF")
        print(f"🔧 [V2-Drive] Destino: Google Drive (carpeta: {GOOGLE_DRIVE_FOLDER_ID_CERTIFICADOS_V2})")

        # Construir URL del preview HTML V2
        preview_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/preview-certificado-v2/{wix_id}"
        print(f"🔗 [V2-Drive] URL del preview: {preview_url}")

        # Obtener numeroId para el nombre del archivo
        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")
        numero_id = wix_id  # fallback
        try:
            wix_url = f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}"
            response = requests.get(wix_url, timeout=10)
            if response.status_code == 200:
                wix_response = response.json()
                datos_wix = wix_response.get("data", {})
                numero_id = datos_wix.get('numeroId', wix_id)
        except:
            pass

        # Generar PDF usando iLovePDF
        print(f"📄 [V2-Drive] Iniciando generación con iLovePDF...")
        pdf_content = ilovepdf_html_to_pdf_from_url(
            html_url=preview_url,
            output_filename=f"certificado_v2_{numero_id}"
        )

        # Guardar PDF localmente
        documento_sanitized = str(numero_id).replace(" ", "_").replace("/", "_").replace("\\", "_")
        local_filename = f"certificado_v2_{documento_sanitized}.pdf"

        with open(local_filename, "wb") as f:
            f.write(pdf_content)

        print(f"✅ [V2-Drive] PDF generado: {local_filename} ({len(pdf_content)} bytes)")

        # Subir a Google Drive
        print(f"☁️ [V2-Drive] Subiendo a Google Drive...")
        nombre_drive = f"certificado_medico_{documento_sanitized}.pdf"

        if DEST == "drive":
            drive_link = subir_pdf_a_drive(local_filename, nombre_drive, GOOGLE_DRIVE_FOLDER_ID_CERTIFICADOS_V2)
        elif DEST == "drive-oauth":
            drive_link = subir_pdf_a_drive_oauth(local_filename, nombre_drive, GOOGLE_DRIVE_FOLDER_ID_CERTIFICADOS_V2)
        else:
            # Fallback a drive normal si el destino es GCS u otro
            from drive_uploader import subir_pdf_a_drive
            drive_link = subir_pdf_a_drive(local_filename, nombre_drive, GOOGLE_DRIVE_FOLDER_ID_CERTIFICADOS_V2)

        print(f"✅ [V2-Drive] Subido a Drive: {drive_link}")

        # Limpiar archivo temporal
        try:
            os.remove(local_filename)
            print(f"🗑️ [V2-Drive] Archivo temporal eliminado: {local_filename}")
        except Exception as e:
            print(f"⚠️ [V2-Drive] Error al eliminar archivo temporal: {e}")

        # Respuesta exitosa
        response_data = jsonify({
            "success": True,
            "drive_link": drive_link,
            "file_name": nombre_drive,
            "wix_id": wix_id
        })
        response_data.headers["Access-Control-Allow-Origin"] = "*"
        return response_data

    except Exception as e:
        print(f"❌ [V2-Drive] Error: {e}")
        traceback.print_exc()

        error_response = jsonify({
            "success": False,
            "error": str(e),
            "wix_id": wix_id
        })
        error_response.headers["Access-Control-Allow-Origin"] = "*"
        return error_response, 500


# ============================================================================
# ENDPOINT PARA INFORME DE CONDICIONES DE SALUD
# ============================================================================

# Condiciones para SVE (Sistema de Vigilancia Epidemiológica)
SVE_VISUAL_CONDITIONS = [
    'ASTIGMATISMO H522',
    "ALTERACION VISUAL  NO ESPECIFICADA H539",
    'ALTERACIONES VISUALES SUBJETIVAS H531',
    'CONJUNTIVITIS  NO ESPECIFICADA H109',
    'DISMINUCION DE LA AGUDEZA VISUAL SIN ESPECIFICACION H547',
    'DISMINUCION INDETERMINADA DE LA AGUDEZA VISUAL EN AMBOS OJOS (AMETROPÍA) H543',
    'MIOPIA H521',
    'PRESBICIA H524',
    'VISION SUBNORMAL DE AMBOS OJOS H542',
    'DEFECTOS DEL CAMPO VISUAL H534'
]

SVE_AUDITORY_CONDITIONS = [
    'EFECTOS DEL RUIDO SOBRE EL OIDO INTERNO H833',
    'PRESBIACUSIA H911',
    'HIPOACUSIA  NO ESPECIFICADA H919',
    'OTITIS MEDIA  NO ESPECIFICADA H669',
    'OTRAS ENFERMEDADES DE LAS CUERDAS VOCALES J383',
    'OTROS TRASTORNOS DE LA VISION BINOCULAR H533'
]

SVE_WEIGHT_CONDITIONS = [
    'AUMENTO ANORMAL DE PESO',
    'OBESIDAD ALIMENTARIA, E66.0',
    'OBESIDAD CONSTITUCIONAL, E66.8',
    'HIPOTIROIDISMO  NO ESPECIFICADO E039'
]


@app.route('/api/informe-condiciones-salud', methods=['GET', 'OPTIONS'])
def informe_condiciones_salud():
    """
    Genera un informe de condiciones de salud obteniendo datos de Wix.
    Parámetros: codEmpresa, fechaInicio, fechaFin
    """
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    try:
        cod_empresa = request.args.get('codEmpresa')
        fecha_inicio = request.args.get('fechaInicio')
        fecha_fin = request.args.get('fechaFin')

        if not cod_empresa or not fecha_inicio or not fecha_fin:
            return jsonify({
                'success': False,
                'error': 'Parámetros requeridos: codEmpresa, fechaInicio, fechaFin'
            }), 400

        logger.info(f"📊 Generando informe para empresa: {cod_empresa}, período: {fecha_inicio} - {fecha_fin}")

        # Paso 1: Obtener datos de HistoriaClinica desde PostgreSQL
        historia_clinica_items = obtener_historia_clinica_postgres(cod_empresa, fecha_inicio, fecha_fin)
        total_atenciones = len(historia_clinica_items)

        logger.info(f"✅ Total atenciones encontradas: {total_atenciones}")

        if total_atenciones == 0:
            return jsonify({
                'success': True,
                'totalAtenciones': 0,
                'totalFormularios': 0,
                'message': 'No se encontraron registros para los criterios dados',
                'codEmpresa': cod_empresa,
                'fechaInicio': fecha_inicio,
                'fechaFin': fecha_fin
            })

        # Paso 2: Obtener datos de la empresa
        empresa_info = obtener_empresa_wix(cod_empresa)

        # Paso 3: Obtener datos de FORMULARIO desde PostgreSQL
        # Estrategia 1: Por empresa y rango de fechas (más confiable)
        formulario_items = obtener_formularios_por_empresa_postgres(cod_empresa, fecha_inicio, fecha_fin)
        total_formularios = len(formulario_items)

        # Estrategia 2 (fallback): Si no hay formularios, intentar por wix_id
        if total_formularios == 0:
            logger.info("⚠️ No se encontraron formularios por empresa, intentando por wix_id")
            historia_ids = [item.get('_id') for item in historia_clinica_items if item.get('_id')]
            formulario_items = obtener_formularios_por_ids_postgres(historia_ids)
            total_formularios = len(formulario_items)

        logger.info(f"✅ Total formularios encontrados: {total_formularios}")

        # Paso 4: Generar estadísticas
        estadisticas = {
            'genero': contar_genero(formulario_items),
            'edad': contar_edad(formulario_items),
            'estadoCivil': contar_estado_civil(formulario_items),
            'nivelEducativo': contar_nivel_educativo(formulario_items),
            'hijos': contar_hijos(formulario_items),
            'ciudadResidencia': contar_ciudad_residencia(formulario_items),
            'profesionUOficio': contar_profesion(formulario_items),
            'encuestaSalud': contar_encuesta_salud(formulario_items),
            'diagnosticos': contar_diagnosticos(historia_clinica_items),
            'sve': generar_sve(historia_clinica_items)
        }

        # Agregar información teórica del informe
        informacion_teorica = {
            'marcoGeneral': {
                'titulo': 'Marco General',
                'descripcion': 'La calidad institucional en BIENESTAR Y SALUD LABORAL SAS se enmarca en la atención pertinente, oportuna, segura y eficaz emitida al usuario remitido por el cliente empresarial. Los exámenes de preingreso y periódicos son una herramienta indispensable para la implementación de los Sistemas de Vigilancia Epidemiológica.'
            },
            'objetivos': [
                {
                    'numero': '01',
                    'titulo': 'Conocer las características demográficas de la población trabajadora',
                    'icono': 'demographics'
                },
                {
                    'numero': '02',
                    'titulo': 'Evaluar las condiciones de salud de la población trabajadora de la empresa',
                    'icono': 'health'
                },
                {
                    'numero': '03',
                    'titulo': 'Detectar de forma oportuna, alteraciones de salud en los trabajadores',
                    'icono': 'detection'
                },
                {
                    'numero': '04',
                    'titulo': 'Determinar los hábitos más frecuentes que puedan favorecer enfermedades en la población evaluada',
                    'icono': 'habits'
                },
                {
                    'numero': '05',
                    'titulo': 'Identificar la prevalencia de enfermedad relacionada con el trabajo',
                    'icono': 'prevalence'
                }
            ],
            'metodologia': {
                'titulo': 'Metodología para evaluar',
                'descripcion': 'De acuerdo a su sistema de vigilancia epidemiológica de conservación de la salud de sus trabajadores realizará los exámenes médicos ocupacionales correspondientes al año mencionado, con el fin de dar cumplimiento a la legislación vigente e investigar y monitorear las condiciones de salud de sus trabajadores.',
                'pruebas': [
                    {
                        'nombre': 'Evaluación médica',
                        'descripcion': 'Se realizan con el fin de determinar en forma preventiva, posibles alteraciones temporales, permanentes o agravadas del estado de salud del trabajador que en contacto con su puesto de trabajo alterarían el perfil biológico de cada persona'
                    },
                    {
                        'nombre': 'Prueba Osteomuscular',
                        'descripcion': 'Se tiene como herramienta fundamental de trabajo, la realización del examen postural y osteomuscular bien sea de ingreso, periódico o de retiro'
                    },
                    {
                        'nombre': 'Optometría',
                        'descripcion': 'Es un examen de alta sensibilidad que evalúa la capacidad visual tanto en el joven como en el adulto, y permite identificar si la visión es normal o si presenta alguna patología que deba ser diagnosticada'
                    },
                    {
                        'nombre': 'Audiometría tamiz',
                        'descripcion': 'Es una prueba subjetiva utilizada para saber si la audición de un sujeto es normal o anormal, a través de ella se puede establecer el umbral mínimo de audición.'
                    }
                ]
            },
            'contenidoInforme': [
                'Información sociodemográfica de la población trabajadora (sexo, grupos etarios, composición familiar, estrato socioeconómico)',
                'Información de antecedentes de exposición laboral a diferentes factores de riesgos ocupacionales',
                'Información de exposición laboral actual, según la manifestación de los trabajadores y los resultados objetivos analizados durante la evaluación médica',
                'Sintomatología reportada por los trabajadores',
                'Resultados generales de las pruebas clínicas o paraclínicas complementarias a los exámenes físicos realizados',
                'Diagnósticos encontrados en la población trabajadora',
                'Análisis y conclusiones de la evaluación',
                'Recomendaciones'
            ],
            'conceptosMedicos': [
                {
                    'concepto': 'Elegible para el cargo sin recomendaciones laborales',
                    'descripcion': 'En BSL usamos este concepto para describir a una persona que cumple con los requisitos necesarios para ocupar un puesto de trabajo sin necesidad de recomendaciones adicionales relacionadas con su capacidad física o mental.',
                    'color': 'green'
                },
                {
                    'concepto': 'Elegible para el cargo con recomendaciones laborales',
                    'descripcion': 'Se refiere a una persona que cumple con los requisitos mínimos para ocupar un puesto de trabajo, pero con ciertas recomendaciones o consideraciones específicas en relación con su capacidad física o mental.',
                    'color': 'yellow'
                },
                {
                    'concepto': 'No elegible para el cargo por fuera del profesiograma',
                    'descripcion': 'Se refiere a una situación en la que una persona no cumple con los requisitos establecidos en el profesiograma para ocupar un determinado puesto de trabajo.',
                    'color': 'red'
                },
                {
                    'concepto': 'Pendiente',
                    'descripcion': 'Se refiere a una situación en la que una persona no ha sido evaluada o se requiere más información antes de determinar su elegibilidad para ocupar un cargo específico.',
                    'color': 'orange'
                }
            ],
            'sugerenciasGenerales': [
                'Proporcionar equipos de protección personal adecuados para todos los trabajadores',
                'Establecer un programa de ejercicios de estiramiento y fortalecimiento para los trabajadores',
                'Establecer un programa de vigilancia auditiva para los trabajadores expuestos a ruido',
                'Establecer un programa de prevención de estrés laboral para los trabajadores',
                'Establecer un programa de educación para los trabajadores sobre cómo prevenir lesiones musculoesqueléticas',
                'Establecer un programa de evaluación de riesgos para identificar y evaluar los riesgos para la salud y la seguridad en el lugar de trabajo',
                'Establecer un programa de capacitación para los trabajadores sobre cómo prevenir lesiones y enfermedades relacionadas con el trabajo',
                'Establecer un programa de vigilancia de la salud para los trabajadores expuestos a sustancias químicas peligrosas',
                'Establecer un programa de vigilancia de la salud para los trabajadores expuestos a la radiación',
                'Establecer un programa de vigilancia de la salud para los trabajadores expuestos a la exposición a temperaturas extremas'
            ]
        }

        response_data = {
            'success': True,
            'totalAtenciones': total_atenciones,
            'totalFormularios': total_formularios,
            'empresaInfo': empresa_info,
            'codEmpresa': cod_empresa,
            'fechaInicio': fecha_inicio,
            'fechaFin': fecha_fin,
            'estadisticas': estadisticas,
            'informacionTeorica': informacion_teorica
        }

        response = jsonify(response_data)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    except Exception as e:
        logger.error(f"❌ Error generando informe: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def obtener_historia_clinica_postgres(cod_empresa, fecha_inicio, fecha_fin):
    """Obtiene registros de HistoriaClinica desde PostgreSQL"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            logger.warning("⚠️ POSTGRES_PASSWORD no configurada")
            return []

        # Conectar a PostgreSQL
        logger.info(f"🔌 [PostgreSQL] Conectando para obtener HistoriaClinica")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Consultar HistoriaClinica
        query = """
            SELECT *
            FROM "HistoriaClinica"
            WHERE "codEmpresa" = %s
              AND "fechaAtencion" >= %s::date
              AND "fechaAtencion" <= %s::date
            ORDER BY "fechaAtencion" DESC
        """

        cur.execute(query, (cod_empresa, fecha_inicio, fecha_fin))
        rows = cur.fetchall()

        # Convertir a lista de diccionarios
        items = [dict(row) for row in rows]

        cur.close()
        conn.close()

        logger.info(f"✅ [PostgreSQL] Obtenidos {len(items)} registros de HistoriaClinica")
        return items

    except ImportError:
        logger.error("⚠️ [PostgreSQL] psycopg2 no está instalado")
        return []
    except Exception as e:
        logger.error(f"❌ [PostgreSQL] Error obteniendo HistoriaClinica: {e}")
        traceback.print_exc()
        return []


def obtener_formularios_por_empresa_postgres(cod_empresa, fecha_inicio, fecha_fin):
    """Obtiene formularios por codEmpresa y rango de fechas desde PostgreSQL"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            logger.warning("⚠️ POSTGRES_PASSWORD no configurada")
            return []

        # Conectar a PostgreSQL
        logger.info(f"🔌 [PostgreSQL] Conectando para obtener Formularios por empresa")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Consultar formularios por cod_empresa y rango de fechas
        query = """
            SELECT *
            FROM formularios
            WHERE cod_empresa = %s
              AND fecha_registro >= %s::date
              AND fecha_registro <= %s::date
        """

        cur.execute(query, (cod_empresa, fecha_inicio, fecha_fin))
        rows = cur.fetchall()

        # Convertir a lista de diccionarios
        items = [dict(row) for row in rows]

        cur.close()
        conn.close()

        logger.info(f"✅ [PostgreSQL] Obtenidos {len(items)} formularios por empresa")
        return items

    except ImportError:
        logger.error("⚠️ [PostgreSQL] psycopg2 no está instalado")
        return []
    except Exception as e:
        logger.error(f"❌ [PostgreSQL] Error obteniendo formularios por empresa: {e}")
        traceback.print_exc()
        return []


def obtener_formularios_por_ids_postgres(historia_ids):
    """Obtiene formularios por wix_ids de HistoriaClinica desde PostgreSQL"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        if not historia_ids:
            return []

        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            logger.warning("⚠️ POSTGRES_PASSWORD no configurada")
            return []

        # Conectar a PostgreSQL
        logger.info(f"🔌 [PostgreSQL] Conectando para obtener Formularios")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Los _id de HistoriaClinica corresponden a wix_id en formularios
        # Consultar formularios por wix_id
        query = """
            SELECT *
            FROM formularios
            WHERE wix_id = ANY(%s)
        """

        cur.execute(query, (historia_ids,))
        rows = cur.fetchall()

        # Convertir a lista de diccionarios
        items = [dict(row) for row in rows]

        cur.close()
        conn.close()

        logger.info(f"✅ [PostgreSQL] Obtenidos {len(items)} formularios")
        return items

    except ImportError:
        logger.error("⚠️ [PostgreSQL] psycopg2 no está instalado")
        return []
    except Exception as e:
        logger.error(f"❌ [PostgreSQL] Error obteniendo formularios: {e}")
        traceback.print_exc()
        return []


def obtener_historia_clinica_wix(cod_empresa, fecha_inicio, fecha_fin):
    """Obtiene registros de HistoriaClinica desde Wix API"""
    try:
        # Usar el endpoint existente de estadísticas o crear consulta directa
        url = f"https://www.bsl.com.co/_functions/historiaClinicaPorEmpresa"
        params = {
            'codEmpresa': cod_empresa,
            'fechaInicio': fecha_inicio,
            'fechaFin': fecha_fin
        }

        response = requests_session.get(url, params=params, timeout=60)

        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data.get('items', [])

        # Si el endpoint no existe, usar consulta alternativa
        logger.warning(f"⚠️ Endpoint historiaClinicaPorEmpresa no disponible, usando alternativa")
        return consultar_historia_clinica_directo(cod_empresa, fecha_inicio, fecha_fin)

    except Exception as e:
        logger.error(f"Error obteniendo HistoriaClinica: {e}")
        return []


def consultar_historia_clinica_directo(cod_empresa, fecha_inicio, fecha_fin):
    """
    Consulta directa a Wix para obtener HistoriaClinica.
    """
    try:
        url = f"https://www.bsl.com.co/_functions/pacientesPorEmpresa"
        params = {
            'codEmpresa': cod_empresa,
            'fechaInicio': fecha_inicio,
            'fechaFin': fecha_fin,
            'limit': 1000
        }

        response = requests_session.get(url, params=params, timeout=60)

        if response.status_code == 200:
            data = response.json()
            return data.get('items', data.get('data', []))

        logger.warning(f"⚠️ No se pudo obtener datos de HistoriaClinica: {response.status_code}")
        return []

    except Exception as e:
        logger.error(f"Error en consulta directa: {e}")
        return []


def obtener_empresa_wix(cod_empresa):
    """Obtiene información de la empresa desde Wix"""
    try:
        return {
            'codEmpresa': cod_empresa,
            'empresa': cod_empresa,
            'nit': None
        }
    except Exception as e:
        logger.error(f"Error obteniendo empresa: {e}")
        return None


def obtener_formularios_por_ids_wix(historia_ids):
    """Obtiene formularios por IDs de HistoriaClinica desde Wix"""
    try:
        if not historia_ids:
            return []

        all_formularios = []
        batch_size = 50

        for i in range(0, len(historia_ids), batch_size):
            batch_ids = historia_ids[i:i + batch_size]

            url = f"https://www.bsl.com.co/_functions/formulariosPorIds"
            response = requests_session.post(url, json={'ids': batch_ids}, timeout=60)

            if response.status_code == 200:
                data = response.json()
                items = data.get('items', data.get('data', []))
                all_formularios.extend(items)

        return all_formularios

    except Exception as e:
        logger.error(f"Error obteniendo formularios: {e}")
        return []


# Funciones de conteo de estadísticas
def contar_genero(items):
    total = len(items)
    masculino = sum(1 for item in items if str(item.get('genero', '')).upper().strip() == 'MASCULINO')
    femenino = sum(1 for item in items if str(item.get('genero', '')).upper().strip() == 'FEMENINO')

    return {
        'total': total,
        'masculino': {
            'cantidad': masculino,
            'porcentaje': (masculino / total * 100) if total > 0 else 0
        },
        'femenino': {
            'cantidad': femenino,
            'porcentaje': (femenino / total * 100) if total > 0 else 0
        }
    }


def contar_edad(items):
    total = len(items)
    rangos = {'15-20': 0, '21-30': 0, '31-40': 0, '41-50': 0, 'mayor50': 0}

    for item in items:
        try:
            edad = int(item.get('edad', 0))
            if 15 <= edad <= 20:
                rangos['15-20'] += 1
            elif 21 <= edad <= 30:
                rangos['21-30'] += 1
            elif 31 <= edad <= 40:
                rangos['31-40'] += 1
            elif 41 <= edad <= 50:
                rangos['41-50'] += 1
            elif edad > 50:
                rangos['mayor50'] += 1
        except (ValueError, TypeError):
            pass

    return {
        'total': total,
        'rangos': {
            key: {
                'cantidad': value,
                'porcentaje': (value / total * 100) if total > 0 else 0
            } for key, value in rangos.items()
        }
    }


def contar_estado_civil(items):
    total = len(items)
    estados = {'soltero': 0, 'casado': 0, 'divorciado': 0, 'viudo': 0, 'unionLibre': 0}

    for item in items:
        # PostgreSQL usa estado_civil, Wix usa estadoCivil
        estado = str(item.get('estado_civil', item.get('estadoCivil', ''))).upper().strip()
        if estado == 'SOLTERO':
            estados['soltero'] += 1
        elif estado == 'CASADO':
            estados['casado'] += 1
        elif estado == 'DIVORCIADO':
            estados['divorciado'] += 1
        elif estado == 'VIUDO':
            estados['viudo'] += 1
        elif estado in ['UNIÓN LIBRE', 'UNION LIBRE']:
            estados['unionLibre'] += 1

    return {
        'total': total,
        'estados': {
            key: {
                'cantidad': value,
                'porcentaje': (value / total * 100) if total > 0 else 0
            } for key, value in estados.items()
        }
    }


def contar_nivel_educativo(items):
    total = len(items)
    niveles = {'primaria': 0, 'secundaria': 0, 'universitario': 0, 'postgrado': 0}

    for item in items:
        # PostgreSQL usa nivel_educativo, Wix usa nivelEducativo
        nivel = str(item.get('nivel_educativo', item.get('nivelEducativo', ''))).upper().strip()
        if nivel == 'PRIMARIA':
            niveles['primaria'] += 1
        elif nivel == 'SECUNDARIA':
            niveles['secundaria'] += 1
        elif nivel == 'UNIVERSITARIO':
            niveles['universitario'] += 1
        elif nivel == 'POSTGRADO':
            niveles['postgrado'] += 1

    return {
        'total': total,
        'niveles': {
            key: {
                'cantidad': value,
                'porcentaje': (value / total * 100) if total > 0 else 0
            } for key, value in niveles.items()
        }
    }


def contar_hijos(items):
    total = len(items)
    grupos = {'sinHijos': 0, 'unHijo': 0, 'dosHijos': 0, 'tresOMas': 0}

    for item in items:
        try:
            hijos = int(item.get('hijos', 0))
            if hijos == 0:
                grupos['sinHijos'] += 1
            elif hijos == 1:
                grupos['unHijo'] += 1
            elif hijos == 2:
                grupos['dosHijos'] += 1
            elif hijos >= 3:
                grupos['tresOMas'] += 1
        except (ValueError, TypeError):
            pass

    return {
        'total': total,
        'grupos': {
            key: {
                'cantidad': value,
                'porcentaje': (value / total * 100) if total > 0 else 0
            } for key, value in grupos.items()
        }
    }


def contar_ciudad_residencia(items):
    total = len(items)
    ciudades_map = {}

    for item in items:
        # PostgreSQL usa ciudad_residencia, Wix usa ciudadDeResidencia
        ciudad = str(item.get('ciudad_residencia', item.get('ciudadDeResidencia', ''))).upper().strip()
        if ciudad:
            ciudades_map[ciudad] = ciudades_map.get(ciudad, 0) + 1

    ciudades = sorted([
        {
            'nombre': ciudad,
            'cantidad': cantidad,
            'porcentaje': (cantidad / total * 100) if total > 0 else 0
        }
        for ciudad, cantidad in ciudades_map.items()
    ], key=lambda x: x['cantidad'], reverse=True)

    return {'total': total, 'ciudades': ciudades}


def contar_profesion(items):
    total = len(items)
    profesiones_map = {}

    for item in items:
        # PostgreSQL usa profesion_oficio, Wix usa profesionUOficio
        profesion = str(item.get('profesion_oficio', item.get('profesionUOficio', ''))).upper().strip()
        if profesion:
            profesiones_map[profesion] = profesiones_map.get(profesion, 0) + 1

    profesiones = sorted([
        {
            'nombre': profesion,
            'cantidad': cantidad,
            'porcentaje': (cantidad / total * 100) if total > 0 else 0
        }
        for profesion, cantidad in profesiones_map.items()
    ], key=lambda x: x['cantidad'], reverse=True)

    return {'total': total, 'profesiones': profesiones}


def contar_encuesta_salud(items):
    total = len(items)
    respuestas_map = {}

    # Campos de salud en PostgreSQL (snake_case) vs Wix (camelCase o array)
    campos_salud_postgres = [
        ('dolor_cabeza', 'Dolor de Cabeza'),
        ('dolor_espalda', 'Dolor de Espalda'),
        ('ruido_jaqueca', 'Ruido/Jaqueca'),
        ('problemas_sueno', 'Problemas de Sueño'),
        ('presion_alta', 'Presión Alta'),
        ('problemas_azucar', 'Problemas de Azúcar'),
        ('problemas_cardiacos', 'Problemas Cardíacos'),
        ('enfermedad_pulmonar', 'Enfermedad Pulmonar'),
        ('enfermedad_higado', 'Enfermedad del Hígado'),
        ('hernias', 'Hernias'),
        ('hormigueos', 'Hormigueos'),
        ('varices', 'Varices'),
        ('hepatitis', 'Hepatitis'),
        ('cirugia_ocular', 'Cirugía Ocular'),
        ('cirugia_programada', 'Cirugía Programada'),
        ('condicion_medica', 'Condición Médica'),
        ('embarazo', 'Embarazo'),
        ('fuma', 'Fuma'),
        ('consumo_licor', 'Consumo de Licor'),
        ('ejercicio', 'Ejercicio'),
        ('usa_anteojos', 'Usa Anteojos'),
        ('usa_lentes_contacto', 'Usa Lentes de Contacto')
    ]

    for item in items:
        # Intentar primero el formato Wix (array encuestaSalud)
        encuesta = item.get('encuestaSalud', [])
        if isinstance(encuesta, list) and len(encuesta) > 0:
            for respuesta in encuesta:
                resp = str(respuesta).upper().strip()
                if resp:
                    respuestas_map[resp] = respuestas_map.get(resp, 0) + 1
        else:
            # Formato PostgreSQL (campos individuales)
            for campo_db, nombre_display in campos_salud_postgres:
                valor = str(item.get(campo_db, '')).upper().strip()
                # Solo contar respuestas afirmativas (SÍ, SI, S, TRUE, 1, etc.)
                if valor in ['SÍ', 'SI', 'S', 'TRUE', '1', 'YES', 'Y']:
                    respuestas_map[nombre_display.upper()] = respuestas_map.get(nombre_display.upper(), 0) + 1

    respuestas = sorted([
        {
            'nombre': respuesta,
            'cantidad': cantidad,
            'porcentaje': (cantidad / total * 100) if total > 0 else 0
        }
        for respuesta, cantidad in respuestas_map.items()
    ], key=lambda x: x['cantidad'], reverse=True)

    return {'total': total, 'respuestas': respuestas}


def contar_diagnosticos(items):
    total = len(items)
    diagnosticos_map = {}

    for item in items:
        md_dx1 = str(item.get('mdDx1', '')).strip()
        if md_dx1:
            for dx in md_dx1.replace(';', ',').split(','):
                dx_clean = dx.strip().upper()
                if dx_clean:
                    diagnosticos_map[dx_clean] = diagnosticos_map.get(dx_clean, 0) + 1

    diagnosticos = sorted([
        {
            'nombre': dx,
            'cantidad': cantidad,
            'porcentaje': (cantidad / total * 100) if total > 0 else 0
        }
        for dx, cantidad in diagnosticos_map.items()
    ], key=lambda x: x['cantidad'], reverse=True)

    return {'total': total, 'diagnosticos': diagnosticos}


def generar_sve(items):
    """Genera datos del Sistema de Vigilancia Epidemiológica"""
    pacientes = []
    resumen = {'visual': 0, 'auditivo': 0, 'controlPeso': 0}

    for item in items:
        nombres = f"{item.get('primerNombre', '')} {item.get('primerApellido', '')}".strip()
        documento = item.get('numeroId', '')

        all_dx = []
        for dx_field in ['mdDx1', 'mdDx2']:
            dx_value = str(item.get(dx_field, '')).strip()
            if dx_value:
                all_dx.extend([d.strip().upper() for d in dx_value.replace(';', ',').split(',')])

        for dx in all_dx:
            sistema = None
            if dx in SVE_VISUAL_CONDITIONS:
                sistema = 'Visual'
                resumen['visual'] += 1
            elif dx in SVE_AUDITORY_CONDITIONS:
                sistema = 'Auditivo'
                resumen['auditivo'] += 1
            elif dx in SVE_WEIGHT_CONDITIONS:
                sistema = 'Control de Peso'
                resumen['controlPeso'] += 1

            if sistema:
                pacientes.append({
                    'nombres': nombres,
                    'documento': documento,
                    'sistema': sistema,
                    'diagnostico': dx
                })

    return {
        'pacientes': pacientes,
        'resumen': resumen,
        'totalPacientesAfectados': len(pacientes)
    }


@app.route('/informes.html', methods=['GET'])
def serve_informes():
    """Sirve la página de informes"""
    return send_from_directory('static', 'informes.html')


@app.route('/api/generar-pdf-informe', methods=['POST', 'OPTIONS'])
def generar_pdf_informe():
    """
    Genera un PDF profesional del informe de condiciones de salud usando Playwright.

    Recibe:
        - codEmpresa: Código de la empresa
        - fechaInicio: Fecha de inicio del período
        - fechaFin: Fecha fin del período

    Retorna:
        - PDF file para descarga directa
    """
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    try:
        data = request.get_json()
        cod_empresa = data.get('codEmpresa')
        fecha_inicio = data.get('fechaInicio')
        fecha_fin = data.get('fechaFin')

        if not cod_empresa or not fecha_inicio or not fecha_fin:
            return jsonify({
                'success': False,
                'error': 'Faltan parámetros requeridos: codEmpresa, fechaInicio, fechaFin'
            }), 400

        logger.info(f"📄 Generando PDF del informe para {cod_empresa} ({fecha_inicio} - {fecha_fin})")

        # 1. Obtener los datos del informe (reutilizar la lógica existente)
        historia_clinica_items = obtener_historia_clinica_postgres(cod_empresa, fecha_inicio, fecha_fin)
        total_atenciones = len(historia_clinica_items)

        # Obtener formularios por empresa y fecha
        formulario_items = obtener_formularios_por_empresa_postgres(cod_empresa, fecha_inicio, fecha_fin)
        total_formularios = len(formulario_items)

        # Fallback: si no hay formularios con Strategy 1, intentar Strategy 2
        if total_formularios == 0:
            logger.info("⚠️ Strategy 1 (cod_empresa + fecha) retornó 0 formularios. Intentando Strategy 2 (wix_id)...")
            historia_ids = [item.get('_id') for item in historia_clinica_items if item.get('_id')]
            formulario_items = obtener_formularios_por_ids_postgres(historia_ids)
            total_formularios = len(formulario_items)

        logger.info(f"✅ Encontrados {total_atenciones} atenciones y {total_formularios} formularios")

        # Calcular estadísticas (usando las funciones existentes)
        estadisticas = {
            'genero': contar_genero(formulario_items),
            'edad': contar_edad(formulario_items),
            'estadoCivil': contar_estado_civil(formulario_items),
            'nivelEducativo': contar_nivel_educativo(formulario_items),
            'hijos': contar_hijos(formulario_items),
            'ciudadResidencia': contar_ciudad_residencia(formulario_items),
            'profesionUOficio': contar_profesion(formulario_items),
            'encuestaSalud': contar_encuesta_salud(formulario_items),
            'diagnosticos': contar_diagnosticos(historia_clinica_items),
            'sve': generar_sve(historia_clinica_items)
        }

        # Información teórica (copiada del endpoint existente)
        info_teorica = {
            'marcoGeneral': {
                'titulo': 'Marco General',
                'descripcion': 'La calidad institucional en BIENESTAR Y SALUD LABORAL SAS se enmarca en la atención pertinente, oportuna, segura y eficaz emitida al usuario remitido por el cliente empresarial. Los exámenes de preingreso y periódicos son una herramienta indispensable para la implementación de los Sistemas de Vigilancia Epidemiológica.'
            },
            'objetivos': [
                {
                    'numero': '01',
                    'titulo': 'Conocer las características demográficas de la población trabajadora',
                    'icono': 'demographics'
                },
                {
                    'numero': '02',
                    'titulo': 'Evaluar las condiciones de salud de la población trabajadora de la empresa',
                    'icono': 'health'
                },
                {
                    'numero': '03',
                    'titulo': 'Detectar de forma oportuna, alteraciones de salud en los trabajadores',
                    'icono': 'detection'
                },
                {
                    'numero': '04',
                    'titulo': 'Determinar los hábitos más frecuentes que puedan favorecer enfermedades en la población evaluada',
                    'icono': 'habits'
                },
                {
                    'numero': '05',
                    'titulo': 'Identificar la prevalencia de enfermedad relacionada con el trabajo',
                    'icono': 'prevalence'
                }
            ],
            'metodologia': {
                'titulo': 'Metodología para evaluar',
                'descripcion': 'De acuerdo a su sistema de vigilancia epidemiológica de conservación de la salud de sus trabajadores realizará los exámenes médicos ocupacionales correspondientes al año mencionado, con el fin de dar cumplimiento a la legislación vigente e investigar y monitorear las condiciones de salud de sus trabajadores.',
                'pruebas': [
                    {
                        'nombre': 'Evaluación médica',
                        'descripcion': 'Se realizan con el fin de determinar en forma preventiva, posibles alteraciones temporales, permanentes o agravadas del estado de salud del trabajador que en contacto con su puesto de trabajo alterarían el perfil biológico de cada persona'
                    },
                    {
                        'nombre': 'Prueba Osteomuscular',
                        'descripcion': 'Se tiene como herramienta fundamental de trabajo, la realización del examen postural y osteomuscular bien sea de ingreso, periódico o de retiro'
                    },
                    {
                        'nombre': 'Optometría',
                        'descripcion': 'Es un examen de alta sensibilidad que evalúa la capacidad visual tanto en el joven como en el adulto, y permite identificar si la visión es normal o si presenta alguna patología que deba ser diagnosticada'
                    },
                    {
                        'nombre': 'Audiometría tamiz',
                        'descripcion': 'Es una prueba subjetiva utilizada para saber si la audición de un sujeto es normal o anormal, a través de ella se puede establecer el umbral mínimo de audición.'
                    }
                ]
            },
            'contenidoInforme': [
                'Información sociodemográfica de la población trabajadora (sexo, grupos etarios, composición familiar, estrato socioeconómico)',
                'Información de antecedentes de exposición laboral a diferentes factores de riesgos ocupacionales',
                'Información de exposición laboral actual, según la manifestación de los trabajadores y los resultados objetivos analizados durante la evaluación médica',
                'Sintomatología reportada por los trabajadores',
                'Resultados generales de las pruebas clínicas o paraclínicas complementarias a los exámenes físicos realizados',
                'Diagnósticos encontrados en la población trabajadora',
                'Análisis y conclusiones de la evaluación',
                'Recomendaciones'
            ],
            'conceptosMedicos': [
                {
                    'concepto': 'Elegible para el cargo sin recomendaciones laborales',
                    'descripcion': 'En BSL usamos este concepto para describir a una persona que cumple con los requisitos necesarios para ocupar un puesto de trabajo sin necesidad de recomendaciones adicionales relacionadas con su capacidad física o mental.',
                    'color': 'green'
                },
                {
                    'concepto': 'Elegible para el cargo con recomendaciones laborales',
                    'descripcion': 'Se refiere a una persona que cumple con los requisitos mínimos para ocupar un puesto de trabajo, pero con ciertas recomendaciones o consideraciones específicas en relación con su capacidad física o mental.',
                    'color': 'yellow'
                },
                {
                    'concepto': 'No elegible para el cargo por fuera del profesiograma',
                    'descripcion': 'Se refiere a una situación en la que una persona no cumple con los requisitos establecidos en el profesiograma para ocupar un determinado puesto de trabajo.',
                    'color': 'red'
                },
                {
                    'concepto': 'Pendiente',
                    'descripcion': 'Se refiere a una situación en la que una persona no ha sido evaluada o se requiere más información antes de determinar su elegibilidad para ocupar un cargo específico.',
                    'color': 'orange'
                }
            ],
            'sugerenciasGenerales': [
                'Proporcionar equipos de protección personal adecuados para todos los trabajadores',
                'Establecer un programa de ejercicios de estiramiento y fortalecimiento para los trabajadores',
                'Establecer un programa de vigilancia auditiva para los trabajadores expuestos a ruido',
                'Establecer un programa de prevención de estrés laboral para los trabajadores',
                'Establecer un programa de educación para los trabajadores sobre cómo prevenir lesiones musculoesqueléticas',
                'Establecer un programa de evaluación de riesgos para identificar y evaluar los riesgos para la salud y la seguridad en el lugar de trabajo',
                'Establecer un programa de capacitación para los trabajadores sobre cómo prevenir lesiones y enfermedades relacionadas con el trabajo',
                'Establecer un programa de vigilancia de la salud para los trabajadores expuestos a sustancias químicas peligrosas',
                'Establecer un programa de vigilancia de la salud para los trabajadores expuestos a la radiación',
                'Establecer un programa de vigilancia de la salud para los trabajadores expuestos a la exposición a temperaturas extremas'
            ]
        }

        # 2. Convertir logo BSL a base64
        logo_path = os.path.join(os.path.dirname(__file__), 'static', 'logo-bsl.png')
        logo_base64 = ''
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as f:
                logo_base64 = base64.b64encode(f.read()).decode('utf-8')

        # 3. Formatear fechas en español
        def formatear_fecha_espanol(fecha_str):
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
                dia = fecha.day
                mes = MESES_ESPANOL.get(fecha.month, str(fecha.month))
                año = fecha.year
                return f"{dia} de {mes} de {año}"
            except:
                return fecha_str

        fecha_inicio_formato = formatear_fecha_espanol(fecha_inicio)
        fecha_fin_formato = formatear_fecha_espanol(fecha_fin)
        fecha_elaboracion = datetime.now().strftime('%d de %B de %Y')

        # Intentar usar locale si está disponible
        try:
            fecha_elaboracion = datetime.now().strftime('%d de %B de %Y')
        except:
            mes_actual = MESES_ESPANOL.get(datetime.now().month, str(datetime.now().month))
            fecha_elaboracion = f"{datetime.now().day} de {mes_actual} de {datetime.now().year}"

        # 4. Renderizar template HTML con Jinja2
        template_path = os.path.join(os.path.dirname(__file__), 'templates', 'informe_pdf.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()

        template = Template(template_content)
        html_rendered = template.render(
            empresa_nombre=cod_empresa,
            empresa_nit='',  # TODO: obtener NIT de la empresa si está disponible
            fecha_inicio_formato=fecha_inicio_formato,
            fecha_fin_formato=fecha_fin_formato,
            fecha_elaboracion=fecha_elaboracion,
            total_atenciones=total_atenciones,
            total_formularios=total_formularios,
            total_diagnosticos=len(estadisticas.get('diagnosticos', {}).get('diagnosticos', [])),
            logo_base64=logo_base64,
            info_teorica=info_teorica,
            stats=estadisticas
        )

        # 5. Guardar HTML temporal
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_html:
            temp_html.write(html_rendered)
            temp_html_path = temp_html.name

        # 6. Generar PDF con WeasyPrint
        from weasyprint import HTML, CSS

        pdf_path = temp_html_path.replace('.html', '.pdf')

        try:
            logger.info(f"🔄 Generando PDF con WeasyPrint...")

            # Generar PDF directamente desde el HTML
            HTML(filename=temp_html_path).write_pdf(
                pdf_path,
                stylesheets=[
                    # CSS adicional para mejorar la impresión
                    CSS(string='''
                        @page {
                            size: A4;
                            margin: 20mm 15mm 25mm 15mm;
                        }
                        body {
                            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                        }
                    ''')
                ]
            )

            logger.info(f"✅ PDF generado exitosamente con WeasyPrint: {pdf_path}")

        except Exception as e:
            logger.error(f"❌ Error generando PDF con WeasyPrint: {str(e)}")
            raise

        finally:
            # Limpiar archivo HTML temporal
            try:
                os.unlink(temp_html_path)
            except:
                pass

        # 7. Enviar PDF como respuesta
        filename = f"Informe_{cod_empresa}_{fecha_inicio}_{fecha_fin}.pdf"

        response = send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

        # Registrar callback para eliminar el PDF temporal después de enviarlo
        @response.call_on_close
        def cleanup():
            try:
                os.unlink(pdf_path)
            except:
                pass

        return response

    except Exception as e:
        logger.error(f"❌ Error generando PDF del informe: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# FUNCIONES DE OPENAI PARA RECOMENDACIONES
# ============================================================================

def call_openai(prompt, max_tokens=1500):
    """
    Llama a la API de OpenAI para generar recomendaciones médico-laborales.
    Similar a la función callOpenAI de Wix.
    """
    if not openai_client:
        logger.warning("⚠️ OpenAI client no disponible")
        return None

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un médico laboral experto en salud ocupacional. Generas recomendaciones concisas y profesionales para informes de condiciones de salud empresariales. No uses markdown ni introducciones."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )

        return {
            'success': True,
            'content': response.choices[0].message.content,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
        }

    except Exception as e:
        logger.error(f"❌ Error llamando a OpenAI: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def generar_prompt_genero(cod_empresa, porcentaje_masculino, porcentaje_femenino):
    """Genera prompt para recomendaciones por género"""
    return f"""Según los porcentajes de población de la empresa {cod_empresa},
el {porcentaje_masculino:.2f}% son hombres y el {porcentaje_femenino:.2f}% son mujeres.
Sugiere dos recomendaciones DE UNA FRASE médico-laborales para cada grupo dirigidas a LA EMPRESA. No hagas introducciones."""


def generar_prompt_edad(cod_empresa, rangos):
    """Genera prompt para recomendaciones por edad"""
    return f"""Según los porcentajes de población de la empresa {cod_empresa},
hay un {rangos['15-20']:.2f}% de personas entre 15-20 años,
un {rangos['21-30']:.2f}% entre 21-30 años,
un {rangos['31-40']:.2f}% entre 31-40 años,
un {rangos['41-50']:.2f}% entre 41-50 años y
un {rangos['mayor50']:.2f}% mayores a 50 años.
Eres médico laboral y estás elaborando el informe de condiciones de salud.
Sugiere exactamente dos recomendaciones breves (una frase cada una) para cada grupo de edad.
No incluyas introducciones. No uses markdown."""


def generar_prompt_estado_civil(cod_empresa, porcentajes):
    """Genera prompt para recomendaciones por estado civil"""
    return f"""Según los porcentajes de población de la empresa {cod_empresa},
hay un {porcentajes['soltero']:.2f}% de personas solteras,
un {porcentajes['casado']:.2f}% casadas,
un {porcentajes['divorciado']:.2f}% divorciadas,
un {porcentajes['viudo']:.2f}% viudas y
un {porcentajes['unionLibre']:.2f}% en unión libre.
Eres médico laboral y estás elaborando el informe de condiciones de salud.
Sugiere exactamente a la empresa dos recomendaciones breves (una frase cada una) para cada grupo.
No incluyas introducciones. No uses markdown."""


def generar_prompt_nivel_educativo(cod_empresa, porcentajes):
    """Genera prompt para recomendaciones por nivel educativo"""
    return f"""Según los porcentajes de población de la empresa {cod_empresa},
hay un {porcentajes['primaria']:.2f}% de personas con nivel educativo de Primaria,
un {porcentajes['secundaria']:.2f}% con nivel de Secundaria,
un {porcentajes['universitario']:.2f}% con nivel Universitario,
y un {porcentajes['postgrado']:.2f}% con nivel de Postgrado.
Eres médico laboral y estás elaborando el informe de condiciones de salud.
Sugiere exactamente dos recomendaciones breves (una frase cada una) para cada grupo.
No incluyas introducciones. No uses markdown."""


def generar_prompt_hijos(cod_empresa, porcentajes):
    """Genera prompt para recomendaciones por número de hijos"""
    return f"""Según los porcentajes de población de la empresa {cod_empresa},
hay un {porcentajes['sinHijos']:.2f}% de personas sin hijos,
un {porcentajes['unHijo']:.2f}% con 1 hijo,
un {porcentajes['dosHijos']:.2f}% con 2 hijos,
y un {porcentajes['tresOMas']:.2f}% con 3 o más hijos.
Eres médico laboral y estás elaborando el informe de condiciones de salud.
Sugiere exactamente dos recomendaciones breves (una frase cada una) para cada grupo.
No incluyas introducciones. No uses markdown."""


def generar_prompt_ciudad(cod_empresa, ciudades):
    """Genera prompt para recomendaciones por ciudad"""
    prompt = f"Según los porcentajes de población de la empresa {cod_empresa}, la distribución por ciudad de residencia es:\n"
    for ciudad in ciudades[:10]:  # Limitar a las 10 principales
        prompt += f"- {ciudad['nombre']}: {ciudad['porcentaje']:.2f}%\n"
    prompt += "Sugiere una recomendación médico-laboral para cada grupo dirigidas a LA EMPRESA. No hagas introducciones. No uses markdowns"
    return prompt


def generar_prompt_profesion(cod_empresa, profesiones):
    """Genera prompt para recomendaciones por profesión"""
    prompt = f"Según los porcentajes de población de la empresa {cod_empresa}, la distribución por profesión u oficio es:\n"
    for prof in profesiones[:10]:  # Limitar a las 10 principales
        prompt += f"- {prof['nombre']}: {prof['porcentaje']:.2f}%\n"
    prompt += "Sugiere dos recomendaciones DE UNA FRASE médico-laborales para cada grupo dirigidas a LA EMPRESA. No hagas introducciones ni uses markdown"
    return prompt


def generar_prompt_encuesta_salud(cod_empresa, respuestas):
    """Genera prompt para recomendaciones basadas en encuesta de salud"""
    prompt = f"Según los resultados de la encuesta de salud en la empresa {cod_empresa}, las respuestas más frecuentes fueron:\n"
    for resp in respuestas[:15]:  # Limitar a las 15 principales
        prompt += f"- {resp['nombre']}: {resp['porcentaje']:.2f}%\n"
    prompt += """Sugiere dos recomendaciones DE UNA FRASE médico-laborales para cada grupo dirigidas a LA EMPRESA. No hagas introducciones ni uses markdown. Al finalizar las recomendaciones provee un análisis de salud de la población basado en la información de la encuesta teniendo en cuenta que es una empresa con cargos administrativos"""
    return prompt


def generar_prompt_diagnosticos(cod_empresa, diagnosticos):
    """Genera prompt para recomendaciones basadas en diagnósticos"""
    prompt = f"Según los diagnósticos más comunes en la empresa {cod_empresa}, la distribución es:\n"
    for dx in diagnosticos[:15]:  # Limitar a los 15 principales
        prompt += f"- {dx['nombre']}: {dx['porcentaje']:.2f}%\n"
    prompt += """Explica y sugiere dos recomendaciones DE UNA FRASE médico-laborales para cada grupo dirigidas a LA EMPRESA. No hagas introducciones ni uses markdown. Al finalizar las recomendaciones provee un análisis detallado de salud de la población basado en la información de la encuesta teniendo en cuenta que es una empresa con cargos administrativos"""
    return prompt


@app.route('/api/informe-recomendaciones-ia', methods=['POST', 'OPTIONS'])
def generar_recomendaciones_ia():
    """
    Genera recomendaciones de IA para un tipo específico de estadística.
    Body: { tipo: string, codEmpresa: string, datos: object }
    Tipos válidos: genero, edad, estadoCivil, nivelEducativo, hijos, ciudad, profesion, encuestaSalud, diagnosticos
    """
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    if not openai_client:
        return jsonify({
            'success': False,
            'error': 'OpenAI no está configurado. Configure la variable de entorno OPENAI_API_KEY'
        }), 503

    try:
        data = request.get_json()
        tipo = data.get('tipo')
        cod_empresa = data.get('codEmpresa', 'N/A')
        datos = data.get('datos', {})

        if not tipo:
            return jsonify({
                'success': False,
                'error': 'El parámetro "tipo" es requerido'
            }), 400

        prompt = None

        # Generar el prompt según el tipo de estadística
        if tipo == 'genero':
            prompt = generar_prompt_genero(
                cod_empresa,
                datos.get('masculino', {}).get('porcentaje', 0),
                datos.get('femenino', {}).get('porcentaje', 0)
            )
        elif tipo == 'edad':
            rangos = datos.get('rangos', {})
            prompt = generar_prompt_edad(cod_empresa, {
                '15-20': rangos.get('15-20', {}).get('porcentaje', 0),
                '21-30': rangos.get('21-30', {}).get('porcentaje', 0),
                '31-40': rangos.get('31-40', {}).get('porcentaje', 0),
                '41-50': rangos.get('41-50', {}).get('porcentaje', 0),
                'mayor50': rangos.get('mayor50', {}).get('porcentaje', 0)
            })
        elif tipo == 'estadoCivil':
            prompt = generar_prompt_estado_civil(cod_empresa, {
                'soltero': datos.get('soltero', {}).get('porcentaje', 0),
                'casado': datos.get('casado', {}).get('porcentaje', 0),
                'divorciado': datos.get('divorciado', {}).get('porcentaje', 0),
                'viudo': datos.get('viudo', {}).get('porcentaje', 0),
                'unionLibre': datos.get('unionLibre', {}).get('porcentaje', 0)
            })
        elif tipo == 'nivelEducativo':
            prompt = generar_prompt_nivel_educativo(cod_empresa, {
                'primaria': datos.get('primaria', {}).get('porcentaje', 0),
                'secundaria': datos.get('secundaria', {}).get('porcentaje', 0),
                'universitario': datos.get('universitario', {}).get('porcentaje', 0),
                'postgrado': datos.get('postgrado', {}).get('porcentaje', 0)
            })
        elif tipo == 'hijos':
            prompt = generar_prompt_hijos(cod_empresa, {
                'sinHijos': datos.get('sinHijos', {}).get('porcentaje', 0),
                'unHijo': datos.get('unHijo', {}).get('porcentaje', 0),
                'dosHijos': datos.get('dosHijos', {}).get('porcentaje', 0),
                'tresOMas': datos.get('tresOMas', {}).get('porcentaje', 0)
            })
        elif tipo == 'ciudad':
            # datos puede ser un array directamente o un objeto con propiedad 'ciudades'
            ciudades = datos if isinstance(datos, list) else datos.get('ciudades', [])
            prompt = generar_prompt_ciudad(cod_empresa, ciudades)
        elif tipo == 'profesion':
            # datos puede ser un array directamente o un objeto con propiedad 'profesiones'
            profesiones = datos if isinstance(datos, list) else datos.get('profesiones', [])
            prompt = generar_prompt_profesion(cod_empresa, profesiones)
        elif tipo == 'encuestaSalud':
            # datos puede ser un array/objeto directamente o un objeto con propiedad 'respuestas'
            respuestas = datos if isinstance(datos, (list, dict)) and 'respuestas' not in datos else datos.get('respuestas', datos)
            prompt = generar_prompt_encuesta_salud(cod_empresa, respuestas)
        elif tipo == 'diagnosticos':
            # datos puede ser un array directamente o un objeto con propiedad 'diagnosticos'
            diagnosticos = datos if isinstance(datos, list) else datos.get('diagnosticos', [])
            prompt = generar_prompt_diagnosticos(cod_empresa, diagnosticos)
        else:
            return jsonify({
                'success': False,
                'error': f'Tipo "{tipo}" no válido. Tipos permitidos: genero, edad, estadoCivil, nivelEducativo, hijos, ciudad, profesion, encuestaSalud, diagnosticos'
            }), 400

        logger.info(f"🤖 Generando recomendación IA para tipo: {tipo}, empresa: {cod_empresa}")

        # Llamar a OpenAI
        resultado = call_openai(prompt)

        if resultado and resultado.get('success'):
            response = jsonify({
                'success': True,
                'tipo': tipo,
                'recomendacion': resultado['content'],
                'usage': resultado.get('usage')
            })
        else:
            response = jsonify({
                'success': False,
                'error': resultado.get('error', 'Error desconocido al llamar a OpenAI')
            })

        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    except Exception as e:
        logger.error(f"❌ Error generando recomendaciones IA: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# INICIALIZACIÓN DE TABLAS DE CONVERSACIONES WHATSAPP
# ============================================================================

def inicializar_tablas_conversaciones():
    """Crea las tablas de conversaciones WhatsApp si no existen"""
    try:
        import psycopg2

        print("📋 Verificando variables de entorno de PostgreSQL...")
        pg_vars = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_USER', 'POSTGRES_DB']
        for var in pg_vars:
            val = os.getenv(var)
            if val:
                print(f"   ✅ {var}: {val}")
            else:
                print(f"   ❌ {var}: NO DEFINIDA")

        print("📡 Conectando a PostgreSQL...")
        # Construir conexión desde variables de entorno
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            database=os.getenv("POSTGRES_DB"),
            sslmode="require"
        )
        print("   ✅ Conectado exitosamente")

        cur = conn.cursor()

        # Leer y ejecutar script SQL
        sql_path = os.path.join(os.path.dirname(__file__), 'sql', 'init_conversaciones_whatsapp.sql')
        print(f"📄 Buscando archivo SQL en: {sql_path}")

        if not os.path.exists(sql_path):
            msg = f"⚠️ No se encontró el archivo SQL: {sql_path}"
            logger.warning(msg)
            print(f"   ❌ {msg}")
            print(f"   📂 Directorio actual: {os.path.dirname(__file__)}")
            print(f"   📂 Archivos en directorio: {os.listdir(os.path.dirname(__file__))[:10]}")
            return

        print("   ✅ Archivo SQL encontrado")

        print("🔧 Ejecutando script SQL...")
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
            print(f"   📝 Script SQL: {len(sql_script)} caracteres")
            cur.execute(sql_script)

        conn.commit()
        print("   ✅ Script ejecutado y cambios confirmados")

        # Verificar que las tablas se crearon
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('conversaciones_whatsapp', 'sistema_asignacion')
        """)
        tables = [row[0] for row in cur.fetchall()]
        print(f"📊 Tablas creadas: {tables}")

        cur.close()
        conn.close()

        logger.info("✅ Tablas de conversaciones WhatsApp inicializadas correctamente")
        print("✅ INICIALIZACIÓN COMPLETADA EXITOSAMENTE")

    except Exception as e:
        logger.error(f"❌ Error inicializando tablas de conversaciones: {e}")
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Inicializar tablas de conversaciones al arrancar
    print("\n" + "=" * 70)
    print("🔧 INICIALIZANDO TABLAS DE CONVERSACIONES WHATSAPP")
    print("=" * 70)
    inicializar_tablas_conversaciones()
    print("=" * 70 + "\n")

    # Usar socketio.run() en lugar de app.run() para soportar WebSockets
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)