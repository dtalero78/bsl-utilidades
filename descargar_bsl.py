import os
import requests
import base64
from flask import Flask, request, jsonify, send_file, send_from_directory, redirect, render_template, make_response, Response, stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit
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
from do_spaces_uploader import subir_imagen_a_do_spaces

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Inicializar SocketIO para WebSockets
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=True, engineio_logger=False)

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
    "CAYENA", "SITEL", "KM2", "TTEC", "CP360", "SALVATECH", "PARTICULAR",
    "STORI", "OMEGA", "EVERTEC", "ZIMMER", "HUNTY", "FDN",
    "SIIGO", "RIPPLING", "RESSOLVE", "CENTRAL", "EVERTECBOGOTA", "ATR",
    "AVANTO", "RICOH", "HEALTHATOM", "TAMESIS"
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
DEST = os.getenv("STORAGE_DESTINATION", "drive")  # drive, drive-oauth, gcs

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
                firma
            FROM formularios
            WHERE wix_id = %s
            LIMIT 1;
        """, (wix_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            print(f"ℹ️  [PostgreSQL] No se encontró registro con wix_id: {wix_id}")
            return None

        foto, edad, genero, estado_civil, hijos, email, profesion_oficio, ciudad_residencia, fecha_nacimiento, primer_nombre, primer_apellido, firma = row

        print(f"✅ [PostgreSQL] Datos del formulario encontrados para {primer_nombre} {primer_apellido}")

        # Construir diccionario con los datos
        datos_formulario = {}

        # Foto (validar que sea data URI)
        if foto and foto.startswith("data:image/"):
            foto_size_kb = len(foto) / 1024
            print(f"📸 [PostgreSQL] Foto encontrada: {foto_size_kb:.1f} KB")
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
                    datos_formulario['fechaNacimiento'] = fecha_obj.strftime('%d de %B de %Y')
                except:
                    datos_formulario['fechaNacimiento'] = fecha_nacimiento
            else:
                # Si es un objeto datetime de PostgreSQL
                datos_formulario['fechaNacimiento'] = fecha_nacimiento.strftime('%d de %B de %Y')
            print(f"🎂 [PostgreSQL] Fecha de nacimiento: {datos_formulario['fechaNacimiento']}")

        # Firma del paciente (validar que sea data URI)
        if firma and firma.startswith("data:image/"):
            firma_size_kb = len(firma) / 1024
            print(f"✍️  [PostgreSQL] Firma encontrada: {firma_size_kb:.1f} KB")
            datos_formulario['firma'] = firma
        else:
            print(f"ℹ️  [PostgreSQL] Sin firma válida")
            datos_formulario['firma'] = None

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
            timeout=90,  # 90 segundos para dar tiempo a que carguen las imágenes de Wix
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
    Función principal que determina si mostrar el aviso de sin soporte

    Returns:
        tuple: (mostrar_aviso: bool, texto_aviso: str)
    """
    # PRIORIDAD 1: Verificar el estado de pago primero
    # Si NO está pagado (null, undefined, vacío, o cualquier valor != "Pagado"), mostrar aviso
    pv_estado = datos_wix.get('pvEstado', '')
    cod_empresa = datos_wix.get('codEmpresa', '')

    print(f"🔍 DEBUG determinar_mostrar_sin_soporte:")
    print(f"   pvEstado: '{pv_estado}' (tipo: {type(pv_estado).__name__})")
    print(f"   codEmpresa: '{cod_empresa}'")
    print(f"   pvEstado != 'Pagado': {pv_estado != 'Pagado'}")

    if pv_estado != "Pagado":
        # Solo ocultar el aviso si es empresa especial o código numérico
        es_especial = es_empresa_especial(cod_empresa)
        print(f"   es_empresa_especial('{cod_empresa}'): {es_especial}")

        if es_especial:
            print(f"   ✅ NO mostrar aviso (empresa especial)")
            return False, ""

        # Mostrar aviso rojo (incluso si es Periódico, PostIncapacidad, etc.)
        print(f"   ⚠️ MOSTRAR AVISO ROJO (pvEstado no es 'Pagado' y empresa no es especial)")
        texto = "ESTE CERTIFICADO SERÁ LIBERADO EN EL MOMENTO EN QUE LA EMPRESA REALICE EL PAGO CORRESPONDIENTE"
        return True, texto

    # Si está pagado, mostrar concepto normal
    print(f"   ✅ NO mostrar aviso (pvEstado es 'Pagado')")
    return False, ""

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
            "fecha_atencion": data.get("fecha_atencion", fecha_actual.strftime("%d de %B de %Y")),
            "ciudad": data.get("ciudad", "Bogotá"),
            "vigencia": data.get("vigencia", "Tres años"),
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
            "tipo_examen": data.get("tipo_examen", "Ingreso"),
            "foto_paciente": obtener_foto_desde_postgres(data.get("wix_id")) if data.get("wix_id") else data.get("foto_paciente", None),

            # Exámenes realizados
            "examenes_realizados": data.get("examenes_realizados", [
                {"nombre": "Examen Médico Osteomuscular", "fecha": fecha_actual.strftime("%d de %B de %Y")},
                {"nombre": "Audiometría", "fecha": fecha_actual.strftime("%d de %B de %Y")},
                {"nombre": "Optometría", "fecha": fecha_actual.strftime("%d de %B de %Y")}
            ]),

            # Concepto médico
            "concepto_medico": data.get("concepto_medico", "ELEGIBLE PARA EL CARGO SIN RECOMENDACIONES LABORALES"),

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
            "medico_nombre": data.get("medico_nombre", "JUAN JOSE REATIGA"),
            "medico_registro": data.get("medico_registro", "REGISTRO MEDICO NO 14791"),
            "medico_licencia": data.get("medico_licencia", "LICENCIA SALUD OCUPACIONAL 460"),
            "firma_medico_url": data.get("firma_medico_url"),
            "firma_paciente_url": data.get("firma_paciente_url"),

            "optometra_nombre": data.get("optometra_nombre", "Dr. Miguel Garzón Rincón"),
            "optometra_registro": data.get("optometra_registro", "Optómetra Ocupacional Res. 6473 04/07/2017"),
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
            "fecha_atencion": data.get("fecha_atencion", fecha_actual.strftime("%d de %B de %Y")),
            "ciudad": data.get("ciudad", "Bogotá"),
            "vigencia": data.get("vigencia", "Tres años"),
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
            "tipo_examen": data.get("tipo_examen", "Ingreso"),
            "foto_paciente": obtener_foto_desde_postgres(data.get("wix_id")) if data.get("wix_id") else data.get("foto_paciente", None),

            # Exámenes realizados
            "examenes_realizados": data.get("examenes_realizados", [
                {"nombre": "Examen Médico Osteomuscular", "fecha": fecha_actual.strftime("%d de %B de %Y")},
                {"nombre": "Audiometría", "fecha": fecha_actual.strftime("%d de %B de %Y")},
                {"nombre": "Optometría", "fecha": fecha_actual.strftime("%d de %B de %Y")}
            ]),

            # Concepto médico
            "concepto_medico": data.get("concepto_medico", "ELEGIBLE PARA EL CARGO SIN RECOMENDACIONES LABORALES"),

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
            "medico_nombre": data.get("medico_nombre", "JUAN JOSE REATIGA"),
            "medico_registro": data.get("medico_registro", "REGISTRO MEDICO NO 14791"),
            "medico_licencia": data.get("medico_licencia", "LICENCIA SALUD OCUPACIONAL 460"),
            "firma_medico_url": data.get("firma_medico_url"),
            "firma_paciente_url": data.get("firma_paciente_url"),

            "optometra_nombre": data.get("optometra_nombre", "Dr. Miguel Garzón Rincón"),
            "optometra_registro": data.get("optometra_registro", "Optómetra Ocupacional Res. 6473 04/07/2017"),
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
        medicos_disponibles = ["SIXTA", "JUAN 134", "CESAR", "MARY", "NUBIA", "PRESENCIAL"]

        # Contador para registros que NO son BOGOTA (para distribución equitativa)
        contador_no_bogota = 0

        for idx, row in enumerate(csv_reader, start=1):
            try:
                # Normalizar los nombres de las columnas (eliminar espacios al inicio/final)
                row_normalized = {key.strip(): value for key, value in row.items()}

                # Obtener el nombre completo y separarlo (soportar múltiples nombres de columna)
                nombre_completo = (
                    row_normalized.get('NOMBRES APELLIDOS Y', '') or
                    row_normalized.get('NOMBRES COMPLETOS', '') or
                    row_normalized.get('NOMBRES Y APELLIDOS', '')
                ).strip()

                print(f"🔍 Fila {idx} - Nombre encontrado: '{nombre_completo}'")
                print(f"🔍 Columnas disponibles: {list(row_normalized.keys())}")

                nombres_separados = separar_nombre_completo(nombre_completo)

                # Calcular fecha de atención (un día después de hoy por defecto)
                fecha_atencion = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

                # Extraer ciudad
                ciudad = row_normalized.get('CIUDAD', '').strip()

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

                # Extraer otros campos del CSV
                persona = {
                    "fila": idx,
                    "nombreCompleto": nombre_completo,
                    "primerNombre": nombres_separados["primerNombre"],
                    "segundoNombre": nombres_separados["segundoNombre"],
                    "primerApellido": nombres_separados["primerApellido"],
                    "segundoApellido": nombres_separados["segundoApellido"],
                    "numeroId": row_normalized.get('No IDENTIFICACION', '').strip(),
                    "cargo": row_normalized.get('CARGO', '').strip(),
                    "celular": row_normalized.get('TELEFONOS', '').strip(),
                    "ciudad": ciudad,
                    "tipoExamen": row_normalized.get('TIPO DE EXAMEN OCUPACIONAL', '').strip(),
                    "fechaAtencion": fecha_atencion,
                    "horaAtencion": hora_atencion,
                    "medico": medico_asignado
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
                {"nombre": "Examen Médico Osteomuscular", "fecha": fecha_actual.strftime("%d de %B de %Y")}
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
            "fecha_emision": fecha_actual.strftime("%d de %B de %Y"),
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

        # Consultar datos desde Wix HTTP Functions
        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")

        print(f"🔍 Consultando Wix HTTP Function: {wix_base_url}/historiaClinicaPorId?_id={wix_id}")

        try:
            # Llamar al endpoint de Wix
            wix_url = f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}"
            response = requests.get(wix_url, timeout=10)

            print(f"📡 Respuesta Wix: {response.status_code}")

            if response.status_code == 200:
                wix_response = response.json()
                datos_wix = wix_response.get("data", {})

                if not datos_wix:
                    print(f"❌ Error: Wix retornó respuesta vacía para ID: {wix_id}")
                    return jsonify({
                        "success": False,
                        "error": "No se encontraron datos del paciente en el sistema"
                    }), 404

                print(f"✅ Datos obtenidos de Wix para ID: {wix_id}")
                print(f"📋 Paciente: {datos_wix.get('primerNombre', '')} {datos_wix.get('primerApellido', '')}")
            else:
                print(f"❌ Error consultando Wix: {response.status_code}")
                return jsonify({
                    "success": False,
                    "error": f"Error al obtener datos del paciente (código {response.status_code})"
                }), 500

        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión con Wix: {e}")
            traceback.print_exc()
            return jsonify({
                "success": False,
                "error": "Error de conexión con el sistema de datos. Intenta nuevamente."
            }), 500

        # Transformar datos de Wix al formato del endpoint de certificado
        nombre_completo = f"{datos_wix.get('primerNombre', '')} {datos_wix.get('segundoNombre', '')} {datos_wix.get('primerApellido', '')} {datos_wix.get('segundoApellido', '')}".strip()

        fecha_consulta = datos_wix.get('fechaConsulta')
        if isinstance(fecha_consulta, datetime):
            fecha_formateada = fecha_consulta.strftime('%d de %B de %Y')
        elif isinstance(fecha_consulta, str):
            # Parsear fecha ISO de Wix (ej: "2025-09-30T16:31:00.927Z")
            try:
                fecha_obj = datetime.fromisoformat(fecha_consulta.replace('Z', '+00:00'))
                fecha_formateada = fecha_obj.strftime('%d de %B de %Y')
            except (ValueError, AttributeError):
                fecha_formateada = datetime.now().strftime('%d de %B de %Y')
        else:
            fecha_formateada = datetime.now().strftime('%d de %B de %Y')

        # Construir exámenes realizados
        examenes_realizados = []
        for examen in datos_wix.get('examenes', []):
            examenes_realizados.append({
                "nombre": examen,
                "fecha": fecha_formateada
            })

        # ===== CONSULTAR DATOS VISUALES (Optometría/Visiometría) =====
        datos_visual = None
        examenes = datos_wix.get('examenes', [])
        tiene_examen_visual = any(e in ['Optometría', 'Visiometría'] for e in examenes)

        if tiene_examen_visual:
            try:
                wix_id_historia = datos_wix.get('_id', '')
                visual_url = f"https://www.bsl.com.co/_functions/visualPorIdGeneral?idGeneral={wix_id_historia}"
                print(f"🔍 Consultando datos visuales para HistoriaClinica ID: {wix_id_historia}")

                visual_response = requests.get(visual_url, timeout=10)

                if visual_response.status_code == 200:
                    visual_data = visual_response.json()
                    if visual_data.get('success') and visual_data.get('data'):
                        datos_visual = visual_data['data'][0] if len(visual_data['data']) > 0 else None
                        print(f"✅ Datos visuales obtenidos correctamente")
                    else:
                        print(f"⚠️ No se encontraron datos visuales para {wix_id_historia}")
                else:
                    print(f"⚠️ Error al consultar datos visuales: {visual_response.status_code}")
            except Exception as e:
                print(f"❌ Error consultando datos visuales: {e}")

        # ===== CONSULTAR DATOS DE AUDIOMETRÍA =====
        datos_audiometria = None
        tiene_examen_audio = any(e in ['Audiometría'] for e in examenes)

        if tiene_examen_audio:
            try:
                wix_id_historia = datos_wix.get('_id', '')
                audio_url = f"https://www.bsl.com.co/_functions/audiometriaPorIdGeneral?idGeneral={wix_id_historia}"
                print(f"🔍 Consultando datos de audiometría para HistoriaClinica ID: {wix_id_historia}")

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
                            print(f"✅ Datos de audiometría obtenidos y transformados correctamente")
                            print(f"📊 Diagnóstico: {diagnostico_final}")
                        else:
                            datos_audiometria = None
                    else:
                        print(f"⚠️ No se encontraron datos de audiometría para {wix_id_historia}")
                else:
                    print(f"⚠️ Error al consultar datos de audiometría: {audio_response.status_code}")
            except Exception as e:
                print(f"❌ Error consultando datos de audiometría: {e}")

        # ===== CONSULTAR DATOS DEL FORMULARIO DESDE POSTGRESQL =====
        wix_id_historia = datos_wix.get('_id', wix_id)
        print(f"🔍 Consultando datos del formulario desde PostgreSQL para wix_id: {wix_id_historia}")

        datos_formulario = obtener_datos_formulario_postgres(wix_id_historia)

        if datos_formulario:
            print(f"✅ Datos del formulario obtenidos desde PostgreSQL")

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

            # Foto del paciente
            if datos_formulario.get('foto'):
                datos_wix['foto_paciente'] = datos_formulario.get('foto')
                print(f"✅ Usando foto de PostgreSQL (data URI base64)")
            else:
                datos_wix['foto_paciente'] = None
                print(f"ℹ️  No hay foto disponible en PostgreSQL")

            # Firma del paciente
            if datos_formulario.get('firma'):
                datos_wix['firma_paciente'] = datos_formulario.get('firma')
                print(f"✅ Usando firma de PostgreSQL (data URI base64)")
            else:
                datos_wix['firma_paciente'] = None
                print(f"ℹ️  No hay firma disponible en PostgreSQL")

            print(f"📊 Datos del formulario integrados: edad={datos_wix.get('edad')}, genero={datos_wix.get('genero')}, hijos={datos_wix.get('hijos')}")
        else:
            print(f"⚠️ No se encontraron datos del formulario en PostgreSQL para wix_id: {wix_id_historia}")
            datos_wix['foto_paciente'] = None
            datos_wix['firma_paciente'] = None

        # ===== LÓGICA DE TEXTOS DINÁMICOS SEGÚN EXÁMENES (como en Wix) =====
        textos_examenes = {
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

        for examen in datos_wix.get('examenes', []):
            descripcion = textos_examenes.get(examen, "Resultados dentro de parámetros normales.")
            resultados_generales.append({
                "examen": examen,
                "descripcion": descripcion
            })

        # Si hay observaciones (sin análisis postural), agregarlas al primer examen
        if observaciones_sin_analisis and len(resultados_generales) > 0:
            resultados_generales[0]["descripcion"] += f"\n\n{observaciones_sin_analisis}"

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
            "PRESENCIAL": "FIRMA-PRESENCIAL.jpeg"
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
                "registro": "REGISTRO MEDICO NO 14791",
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
                "registro": "REGISTRO MEDICO NO 14791",
                "licencia": "LICENCIA SALUD OCUPACIONAL 460",
                "fecha": "6 DE JULIO DE 2020"
            },
            "PRESENCIAL": {
                "nombre": "JUAN JOSE REATIGA",
                "registro": "REGISTRO MEDICO NO 14791",
                "licencia": "LICENCIA SALUD OCUPACIONAL 460",
                "fecha": "6 DE JULIO DE 2020"
            }
        }

        # Obtener firma del médico desde archivos locales
        firma_medico_filename = firma_medico_map.get(medico, "FIRMA-JUAN134.jpeg")
        firma_medico_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/static/{firma_medico_filename}"

        # Obtener datos del médico
        datos_medico = medico_datos_map.get(medico, medico_datos_map["JUAN 134"])
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
            "tipo_examen": datos_wix.get('tipoExamen', ''),
            "foto_paciente": datos_wix.get('foto_paciente', None),

            # Información de la consulta
            "fecha_atencion": fecha_formateada,
            "ciudad": "Bogotá",
            "vigencia": "Tres años",
            "ips_sede": "Sede norte DHSS0244914",

            # Exámenes
            "examenes_realizados": examenes_realizados,
            "examenes": examenes,  # Lista de exámenes para verificar tipo

            # Resultados generales (con textos dinámicos)
            "resultados_generales": resultados_generales,

            # Análisis postural (si existe)
            "analisis_postural": analisis_postural,

            # Concepto médico
            "concepto_medico": datos_wix.get('mdConceptoFinal', 'ELEGIBLE PARA EL CARGO'),

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

        try:
            wix_url = f"{wix_base_url}/historiaClinicaPorId?_id={wix_id}"
            response = requests.get(wix_url, timeout=10)

            if response.status_code == 200:
                wix_response = response.json()
                datos_wix = wix_response.get("data", {})

                if not datos_wix:
                    print(f"❌ Error: Wix retornó respuesta vacía para ID: {wix_id}")
                    return f"<html><body><h1>Error</h1><p>No se encontraron datos del paciente en el sistema (ID: {wix_id})</p></body></html>", 404

                print(f"✅ Datos obtenidos de Wix para ID: {wix_id}")
            else:
                print(f"❌ Error consultando Wix: {response.status_code}")
                return f"<html><body><h1>Error</h1><p>Error al obtener datos del paciente (código {response.status_code})</p></body></html>", 500

        except Exception as e:
            print(f"❌ Error de conexión a Wix: {str(e)}")
            traceback.print_exc()
            return f"<html><body><h1>Error</h1><p>Error de conexión con el sistema de datos. Intenta nuevamente.</p></body></html>", 500

        # Transformar datos de Wix al formato del certificado
        nombre_completo = f"{datos_wix.get('primerNombre', '')} {datos_wix.get('segundoNombre', '')} {datos_wix.get('primerApellido', '')} {datos_wix.get('segundoApellido', '')}".strip()

        fecha_consulta = datos_wix.get('fechaConsulta')
        if isinstance(fecha_consulta, datetime):
            fecha_formateada = fecha_consulta.strftime('%d de %B de %Y')
        elif isinstance(fecha_consulta, str):
            # Parsear fecha ISO de Wix (ej: "2025-09-30T16:31:00.927Z")
            try:
                fecha_obj = datetime.fromisoformat(fecha_consulta.replace('Z', '+00:00'))
                fecha_formateada = fecha_obj.strftime('%d de %B de %Y')
            except (ValueError, AttributeError):
                fecha_formateada = datetime.now().strftime('%d de %B de %Y')
        else:
            fecha_formateada = datetime.now().strftime('%d de %B de %Y')

        # Construir exámenes realizados
        examenes_realizados = []
        for examen in datos_wix.get('examenes', []):
            examenes_realizados.append({
                "nombre": examen,
                "fecha": fecha_formateada
            })

        # ===== CONSULTAR DATOS VISUALES (Optometría/Visiometría) =====
        datos_visual = None
        examenes = datos_wix.get('examenes', [])
        tiene_examen_visual = any(e in ['Optometría', 'Visiometría'] for e in examenes)

        if tiene_examen_visual:
            try:
                wix_id_historia = datos_wix.get('_id', wix_id)  # Usar wix_id del parámetro si no viene en datos_wix
                visual_url = f"https://www.bsl.com.co/_functions/visualPorIdGeneral?idGeneral={wix_id_historia}"
                print(f"🔍 Consultando datos visuales para HistoriaClinica ID: {wix_id_historia}", flush=True)

                visual_response = requests.get(visual_url, timeout=10)

                if visual_response.status_code == 200:
                    visual_data = visual_response.json()
                    if visual_data.get('success') and visual_data.get('data'):
                        datos_visual = visual_data['data'][0] if len(visual_data['data']) > 0 else None
                        print(f"✅ Datos visuales obtenidos correctamente", flush=True)
                        print(f"📊 Datos: {datos_visual}", flush=True)
                    else:
                        print(f"⚠️ No se encontraron datos visuales para {wix_id_historia}", flush=True)
                        datos_visual = None
                else:
                    print(f"⚠️ Error al consultar datos visuales: {visual_response.status_code}", flush=True)
                    datos_visual = None
            except Exception as e:
                print(f"❌ Error consultando datos visuales: {e}", flush=True)
                datos_visual = None

        # ===== CONSULTAR DATOS DE AUDIOMETRÍA =====
        datos_audiometria = None
        tiene_examen_audio = any(e in ['Audiometría'] for e in examenes)

        if tiene_examen_audio:
            try:
                wix_id_historia = datos_wix.get('_id', wix_id)  # Usar wix_id del parámetro si no viene en datos_wix
                audio_url = f"https://www.bsl.com.co/_functions/audiometriaPorIdGeneral?idGeneral={wix_id_historia}"
                print(f"🔍 Consultando datos de audiometría para HistoriaClinica ID: {wix_id_historia}", flush=True)

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
                            print(f"✅ Datos de audiometría obtenidos y transformados correctamente", flush=True)
                            print(f"📊 Diagnóstico: {diagnostico_final}", flush=True)
                        else:
                            datos_audiometria = None
                    else:
                        print(f"⚠️ No se encontraron datos de audiometría para {wix_id_historia}", flush=True)
                        datos_audiometria = None
                else:
                    print(f"⚠️ Error al consultar datos de audiometría: {audio_response.status_code}", flush=True)
                    datos_audiometria = None
            except Exception as e:
                print(f"❌ Error consultando datos de audiometría: {e}", flush=True)
                datos_audiometria = None

        # ===== CONSULTAR DATOS DEL FORMULARIO DESDE POSTGRESQL =====
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

            print(f"📊 Datos del formulario integrados: edad={datos_wix.get('edad')}, genero={datos_wix.get('genero')}, hijos={datos_wix.get('hijos')}", flush=True)
        else:
            print(f"⚠️ No se encontraron datos del formulario en PostgreSQL para wix_id: {wix_id_historia}", flush=True)
            datos_wix['foto_paciente'] = None
            datos_wix['firma_paciente'] = None

        # Textos dinámicos según exámenes
        textos_examenes = {
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

        for examen in datos_wix.get('examenes', []):
            descripcion = textos_examenes.get(examen, "Resultados dentro de parámetros normales.")
            resultados_generales.append({
                "examen": examen,
                "descripcion": descripcion
            })

        if observaciones_sin_analisis and len(resultados_generales) > 0:
            resultados_generales[0]["descripcion"] += f"\n\n{observaciones_sin_analisis}"

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
            "PRESENCIAL": "FIRMA-PRESENCIAL.jpeg"
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
                "registro": "REGISTRO MEDICO NO 14791",
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
                "registro": "REGISTRO MEDICO NO 14791",
                "licencia": "LICENCIA SALUD OCUPACIONAL 460",
                "fecha": "6 DE JULIO DE 2020"
            },
            "PRESENCIAL": {
                "nombre": "JUAN JOSE REATIGA",
                "registro": "REGISTRO MEDICO NO 14791",
                "licencia": "LICENCIA SALUD OCUPACIONAL 460",
                "fecha": "6 DE JULIO DE 2020"
            }
        }

        # Obtener firma del médico desde archivos locales
        firma_medico_filename = firma_medico_map.get(medico, "FIRMA-JUAN134.jpeg")
        firma_medico_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/static/{firma_medico_filename}"

        # Obtener datos del médico
        datos_medico = medico_datos_map.get(medico, medico_datos_map["JUAN 134"])
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
            "tipo_examen": datos_wix.get('tipoExamen', ''),
            "foto_paciente": datos_wix.get('foto_paciente', None),
            "fecha_atencion": fecha_formateada,
            "ciudad": "Bogotá",
            "vigencia": "Tres años",
            "ips_sede": "Sede norte DHSS0244914",
            "examenes_realizados": examenes_realizados,
            "examenes": examenes,  # Lista de exámenes para verificar tipo
            "resultados_generales": resultados_generales,
            "analisis_postural": analisis_postural,
            "concepto_medico": datos_wix.get('mdConceptoFinal', 'ELEGIBLE PARA EL CARGO'),
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
            "optometra_registro": "Optómetra Ocupacional Res. 6473 04/07/2017",
            "firma_optometra_url": firma_optometra_url,
            "examenes_detallados": [],
            "logo_url": "https://bsl-utilidades-yp78a.ondigitalocean.app/static/logo-bsl.png"
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

        wix_base_url = os.getenv("WIX_BASE_URL", "https://www.bsl.com.co/_functions")

        # Si viene historiaId, buscar directamente por _id
        if historia_id:
            print(f"   Historia ID: {historia_id}")
            wix_url = f"{wix_base_url}/medidataPaciente?historiaId={historia_id}"
        else:
            print(f"   Cédula: {numero_id}")
            wix_url = f"{wix_base_url}/historiaClinicaPorNumeroId?numeroId={numero_id}"

        print(f"🔍 Consultando Wix: {wix_url}")

        wix_response = requests.get(wix_url, timeout=10)

        if wix_response.status_code == 404:
            mensaje_error = "No se encontró certificado para este registro" if historia_id else f"No se encontró certificado para cédula: {numero_id}"
            print(f"❌ {mensaje_error}")
            return jsonify({
                "success": False,
                "message": mensaje_error + ". Verifica los datos ingresados."
            }), 404

        if wix_response.status_code != 200:
            print(f"❌ Error en Wix: {wix_response.status_code}")
            print(f"   Respuesta: {wix_response.text[:200]}")
            return jsonify({
                "success": False,
                "message": "Error al consultar la información. Intenta nuevamente."
            }), 500

        wix_data = wix_response.json()
        print(f"✅ Respuesta de Wix: {wix_data}")

        # Si vino por historiaId, la respuesta es diferente (tiene historiaClinica y formulario)
        if historia_id:
            datos_wix = wix_data.get('historiaClinica', {})
            wix_id = historia_id
        else:
            # La respuesta tiene formato: { "_id": "...", "data": {...} }
            datos_wix = wix_data.get('data')
            wix_id = wix_data.get('_id')

        if not datos_wix or not wix_id:
            return jsonify({
                "success": False,
                "message": "No se encontró un certificado con esos datos"
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
        import time
        cache_buster = int(time.time() * 1000)  # timestamp en milisegundos

        # Generar el PDF (hacer request al endpoint)
        pdf_response = requests.get(f"https://bsl-utilidades-yp78a.ondigitalocean.app/api/generar-certificado-pdf/{wix_id}?v={cache_buster}", timeout=60)

        if pdf_response.status_code != 200:
            return jsonify({
                "success": False,
                "message": "Error al generar el certificado PDF"
            }), 500

        # Guardar PDF temporalmente y subirlo a un lugar accesible
        # Para simplificar, vamos a usar la URL del preview como link CON CACHE-BUSTING
        certificado_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/api/generar-certificado-pdf/{wix_id}?v={cache_buster}"

        # Enviar por WhatsApp
        print(f"📤 Enviando certificado por WhatsApp a {celular}")

        whatsapp_url = "https://gate.whapi.cloud/messages/document"
        whatsapp_headers = {
            "accept": "application/json",
            "authorization": "Bearer due3eWCwuBM2Xqd6cPujuTRqSbMb68lt",
            "content-type": "application/json"
        }

        # Obtener nombre del paciente y cédula
        nombre_completo = f"{datos_wix.get('primerNombre', '')} {datos_wix.get('segundoNombre', '')} {datos_wix.get('primerApellido', '')} {datos_wix.get('segundoApellido', '')}".strip()
        cedula = numero_id if numero_id else datos_wix.get('numeroId', 'N/A')

        whatsapp_payload = {
            "to": celular,
            "media": certificado_url,
            "caption": f"🏥 *Certificado Médico Ocupacional*\n\n*Paciente:* {nombre_completo}\n*Cédula:* {cedula}\n\n✅ Tu certificado está listo.\n\n_Bienestar y Salud Laboral SAS_"
        }

        try:
            whatsapp_response = requests.post(
                whatsapp_url,
                headers=whatsapp_headers,
                json=whatsapp_payload,
                timeout=10  # Reducido a 10 segundos
            )

            if whatsapp_response.status_code in [200, 201]:
                print(f"✅ Certificado enviado exitosamente por WhatsApp")
                return jsonify({
                    "success": True,
                    "message": "Certificado enviado exitosamente por WhatsApp"
                }), 200
            else:
                print(f"❌ Error enviando por WhatsApp: {whatsapp_response.status_code}")
                print(f"   Respuesta: {whatsapp_response.text}")
                return jsonify({
                    "success": False,
                    "message": "Error al enviar el mensaje por WhatsApp. Verifica el número."
                }), 500

        except requests.exceptions.Timeout:
            # Timeout en la respuesta de WhatsApp, pero el mensaje probablemente se envió
            print(f"⏱️  Timeout esperando respuesta de WhatsApp (mensaje probablemente enviado)")
            return jsonify({
                "success": True,
                "message": "Certificado enviado por WhatsApp (confirmación pendiente)"
            }), 200

        except requests.exceptions.RequestException as e:
            print(f"❌ Error de conexión con WhatsApp: {str(e)}")
            return jsonify({
                "success": False,
                "message": "Error de conexión con WhatsApp. Intenta nuevamente."
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


# ============================================================================
# TWILIO-BSL WHATSAPP INTEGRATION
# ============================================================================

# Configuración Twilio
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+573153369631')
WIX_BASE_URL = os.getenv('WIX_BASE_URL', 'https://www.bsl.com.co/_functions')

# Configuración Whapi (segunda línea de WhatsApp)
WHAPI_TOKEN = os.getenv('WHAPI_TOKEN', 'due3eWCwuBM2Xqd6cPujuTRqSbMb68lt')
WHAPI_BASE_URL = os.getenv('WHAPI_BASE_URL', 'https://gate.whapi.cloud')
WHAPI_PHONE_NUMBER = '573008021701'  # Número de la línea Whapi

# Inicializar cliente Twilio
twilio_client = None
if TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Cliente Twilio inicializado correctamente")
    except Exception as e:
        logger.warning(f"No se pudo inicializar Twilio: {str(e)}")
elif not TWILIO_AVAILABLE:
    logger.warning("SDK de Twilio no instalado. Instalar con: pip install twilio")

# ============================================================================
# SSE (Server-Sent Events) System for Real-Time Notifications
# ============================================================================

# Estructura para manejar suscriptores SSE
def broadcast_websocket_event(event_type, data):
    """Envía un evento a todos los clientes conectados vía WebSocket"""
    try:
        socketio.emit(event_type, data, namespace='/twilio-chat')
        logger.info(f"📡 Evento WebSocket enviado: {event_type}")
    except Exception as e:
        logger.error(f"❌ Error enviando evento WebSocket: {e}")

# Funciones de integración Wix CHATBOT
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
        logger.info(f"   De: {TWILIO_WHATSAPP_NUMBER}")
        logger.info(f"   Para: {to_number}")
        logger.info(f"   Contenido: {message_body[:50]}...")

        # NO guardamos en Wix - solo Twilio
        return message.sid
    except Exception as e:
        logger.error(f"❌ Error enviando WhatsApp: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# ============================================================================
# WHAPI INTEGRATION FUNCTIONS
# ============================================================================

def obtener_conversaciones_whapi():
    """Obtiene todas las conversaciones de Whapi"""
    try:
        url = f"{WHAPI_BASE_URL}/chats"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {WHAPI_TOKEN}"
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        chats = data.get('chats', [])

        logger.info(f"✅ Obtenidos {len(chats)} chats de Whapi")
        return chats
    except Exception as e:
        logger.error(f"❌ Error obteniendo conversaciones de Whapi: {str(e)}")
        return []

def obtener_mensajes_whapi(chat_id):
    """Obtiene mensajes de un chat específico de Whapi"""
    try:
        url = f"{WHAPI_BASE_URL}/messages/list/{chat_id}"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {WHAPI_TOKEN}"
        }

        params = {
            "count": 100  # Obtener últimos 100 mensajes
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        messages = data.get('messages', [])

        logger.info(f"✅ Obtenidos {len(messages)} mensajes de Whapi para chat {chat_id}")
        return messages
    except Exception as e:
        logger.error(f"❌ Error obteniendo mensajes de Whapi: {str(e)}")
        return []

def formatear_mensaje_whapi(msg, chat_id):
    """Formatea un mensaje de Whapi al formato esperado por el frontend"""
    try:
        from datetime import datetime

        # Determinar dirección del mensaje
        from_me = msg.get('from_me', False)

        # Convertir timestamp Unix a ISO string para compatibilidad con Twilio
        timestamp = msg.get('timestamp', 0)
        if isinstance(timestamp, int):
            date_sent = datetime.fromtimestamp(timestamp).isoformat()
        else:
            date_sent = timestamp

        return {
            'id': msg.get('id', ''),
            'chat_id': chat_id,
            'from': WHAPI_PHONE_NUMBER if from_me else chat_id,
            'to': chat_id if from_me else WHAPI_PHONE_NUMBER,
            'body': msg.get('text', {}).get('body', '') if msg.get('type') == 'text' else '(media)',
            'date_sent': date_sent,
            'status': 'delivered',
            'direction': 'outbound' if from_me else 'inbound',
            'media_count': 1 if msg.get('type') != 'text' else 0,
            'source': 'whapi'
        }
    except Exception as e:
        logger.error(f"❌ Error formateando mensaje de Whapi: {str(e)}")
        return None

def enviar_mensaje_whapi(to_number, message_body, media_url=None):
    """Envía un mensaje de WhatsApp usando Whapi"""
    try:
        # Limpiar número de destino
        numero_clean = to_number.replace('whatsapp:', '').replace('+', '')
        chat_id = f"{numero_clean}@s.whatsapp.net"

        # Preparar datos del mensaje
        url = f"{WHAPI_BASE_URL}/messages/text"
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {WHAPI_TOKEN}",
            "content-type": "application/json"
        }

        payload = {
            "typing_time": 0,
            "to": chat_id,
            "body": message_body
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        message_id = data.get('id', '')

        logger.info(f"✅ Mensaje enviado via Whapi. ID: {message_id}")
        logger.info(f"   De: {WHAPI_PHONE_NUMBER}")
        logger.info(f"   Para: {chat_id}")
        logger.info(f"   Contenido: {message_body[:50]}...")

        return message_id
    except Exception as e:
        logger.error(f"❌ Error enviando mensaje via Whapi: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# Rutas Twilio-BSL
@app.route('/twilio-chat')
def twilio_chat_interface():
    """Interfaz principal del chat WhatsApp"""
    return render_template('twilio/chat.html')

@app.route('/twilio-chat/health')
def twilio_health():
    """Health check del servicio Twilio"""
    return jsonify({
        'status': 'healthy',
        'service': 'twilio-bsl',
        'timestamp': datetime.now().isoformat(),
        'twilio_configured': twilio_client is not None
    })

@app.route('/twilio-chat/api/conversaciones')
def twilio_get_conversaciones():
    """Obtiene todas las conversaciones - COMBINANDO Twilio + Whapi"""
    try:
        conversaciones = {}

        # ==================== OBTENER MENSAJES DE TWILIO ====================
        if twilio_client:
            try:
                logger.info("📱 Obteniendo mensajes de Twilio...")
                messages = twilio_client.messages.list(from_=TWILIO_WHATSAPP_NUMBER, limit=100)
                incoming = twilio_client.messages.list(to=TWILIO_WHATSAPP_NUMBER, limit=100)
                all_messages = list(messages) + list(incoming)
                all_messages.sort(key=lambda x: x.date_sent, reverse=True)

                logger.info(f"✅ Total de mensajes Twilio obtenidos: {len(all_messages)}")

                # Agrupar por conversación
                for msg in all_messages:
                    # Determinar el número del contacto
                    numero = msg.to if msg.from_ == TWILIO_WHATSAPP_NUMBER else msg.from_
                    numero_clean = numero.replace('whatsapp:', '').replace('+', '')

                    if numero_clean not in conversaciones:
                        conversaciones[numero_clean] = {
                            'numero': numero_clean,
                            'nombre': f"Usuario {numero_clean[-4:]}",
                            'messages': [],
                            'last_message_time': None,
                            'last_message_preview': '',
                            'source': 'twilio'
                        }

                    # Agregar mensaje a la conversación
                    message_data = {
                        'sid': msg.sid,
                        'from': msg.from_,
                        'to': msg.to,
                        'body': msg.body,
                        'date_sent': msg.date_sent.isoformat() if msg.date_sent else None,
                        'status': msg.status,
                        'direction': 'outbound' if msg.from_ == TWILIO_WHATSAPP_NUMBER else 'inbound',
                        'media_count': msg.num_media if hasattr(msg, 'num_media') else 0,
                        'source': 'twilio'
                    }

                    conversaciones[numero_clean]['messages'].append(message_data)

                    # Actualizar último mensaje y preview
                    if not conversaciones[numero_clean]['last_message_time'] or \
                       msg.date_sent > conversaciones[numero_clean]['last_message_time']:
                        conversaciones[numero_clean]['last_message_time'] = msg.date_sent
                        conversaciones[numero_clean]['last_message_preview'] = msg.body[:50] if msg.body else '(media)'

            except Exception as e:
                logger.error(f"⚠️ Error obteniendo mensajes de Twilio: {str(e)}")

        # ==================== OBTENER MENSAJES DE WHAPI ====================
        try:
            logger.info("📱 Obteniendo conversaciones de Whapi...")
            chats_whapi = obtener_conversaciones_whapi()
            logger.info(f"✅ Total de chats Whapi obtenidos: {len(chats_whapi)}")

            for chat in chats_whapi:
                chat_id = chat.get('id', '')
                # Limpiar el chat_id para obtener solo el número
                numero_clean = chat_id.replace('@s.whatsapp.net', '').replace('@g.us', '')

                # Obtener nombre del contacto
                nombre = chat.get('name', f"Usuario {numero_clean[-4:]}")

                if numero_clean not in conversaciones:
                    conversaciones[numero_clean] = {
                        'numero': numero_clean,
                        'nombre': nombre,
                        'messages': [],
                        'last_message_time': None,
                        'last_message_preview': '',
                        'source': 'whapi'
                    }
                else:
                    # Si ya existe (desde Twilio), agregar indicador de múltiples fuentes
                    conversaciones[numero_clean]['source'] = 'both'
                    conversaciones[numero_clean]['nombre'] = nombre  # Usar nombre de Whapi si está disponible

                # Obtener último mensaje del chat
                last_msg = chat.get('last_message', {})
                if last_msg:
                    last_msg_time = last_msg.get('timestamp', 0)
                    last_msg_text = last_msg.get('text', {}).get('body', '') if last_msg.get('type') == 'text' else '(media)'

                    # Crear timestamp comparable
                    from datetime import datetime, timezone
                    if isinstance(last_msg_time, int):
                        # Convertir a UTC aware datetime para comparar con Twilio
                        last_msg_datetime = datetime.fromtimestamp(last_msg_time, tz=timezone.utc)
                    else:
                        last_msg_datetime = datetime.now(timezone.utc)

                    # Actualizar último mensaje si es más reciente
                    # Convertir last_message_time de Twilio a aware si es naive
                    existing_time = conversaciones[numero_clean]['last_message_time']
                    if existing_time and existing_time.tzinfo is None:
                        # Si el existente es naive, convertirlo a aware UTC
                        existing_time = existing_time.replace(tzinfo=timezone.utc)

                    if not existing_time or last_msg_datetime > existing_time:
                        conversaciones[numero_clean]['last_message_time'] = last_msg_datetime
                        conversaciones[numero_clean]['last_message_preview'] = last_msg_text[:50]

        except Exception as e:
            logger.error(f"⚠️ Error obteniendo conversaciones de Whapi: {str(e)}")

        # ==================== FORMATEAR RESPUESTA ====================
        # Ordenar mensajes dentro de cada conversación
        for numero, data in conversaciones.items():
            if data['messages']:
                data['messages'].sort(key=lambda x: x['date_sent'])

        # Convertir a formato esperado por el frontend
        conversaciones_formateadas = {}
        for numero, data in conversaciones.items():
            conversaciones_formateadas[numero] = {
                'twilio_messages': data['messages'],
                'numero': numero,
                'nombre': data['nombre'],
                'last_message': data['last_message_preview'],
                'last_message_time': data['last_message_time'].isoformat() if data['last_message_time'] else None,
                'source': data['source']  # 'twilio', 'whapi', or 'both'
            }

        logger.info(f"✅ Conversaciones agrupadas: {len(conversaciones_formateadas)} (Twilio + Whapi)")

        return jsonify({
            'success': True,
            'conversaciones': conversaciones_formateadas,
            'total': len(conversaciones_formateadas),
            'source': 'twilio_and_whapi'
        })
    except Exception as e:
        logger.error(f"❌ Error obteniendo conversaciones: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/twilio-chat/api/conversacion/<numero>')
def twilio_get_conversacion(numero):
    """Obtiene conversación específica - COMBINANDO Twilio + Whapi"""
    try:
        logger.info(f"📱 Obteniendo conversación para número: {numero}")

        conversacion_messages = []

        # ==================== OBTENER MENSAJES DE TWILIO ====================
        if twilio_client:
            try:
                # Normalizar número para Twilio
                if not numero.startswith('whatsapp:'):
                    if numero.startswith('+'):
                        numero_whatsapp = f'whatsapp:{numero}'
                    else:
                        numero_whatsapp = f'whatsapp:+{numero}'
                else:
                    numero_whatsapp = numero

                # Obtener TODOS los mensajes y filtrar por número
                logger.info(f"📱 Buscando mensajes Twilio para: {numero_whatsapp}")
                all_messages = twilio_client.messages.list(limit=200)

                for msg in all_messages:
                    if msg.from_ == numero_whatsapp or msg.to == numero_whatsapp:
                        conversacion_messages.append({
                            'sid': msg.sid,
                            'from': msg.from_,
                            'to': msg.to,
                            'body': msg.body,
                            'date_sent': msg.date_sent.isoformat() if msg.date_sent else None,
                            'status': msg.status,
                            'direction': 'outbound' if msg.from_ == TWILIO_WHATSAPP_NUMBER else 'inbound',
                            'media_count': msg.num_media if hasattr(msg, 'num_media') else 0,
                            'source': 'twilio'
                        })

                logger.info(f"✅ Mensajes Twilio encontrados: {len([m for m in conversacion_messages if m['source'] == 'twilio'])}")
            except Exception as e:
                logger.error(f"⚠️ Error obteniendo mensajes de Twilio: {str(e)}")

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
        # Ordenar cronológicamente todos los mensajes combinados
        conversacion_messages.sort(key=lambda x: x.get('date_sent', ''))

        logger.info(f"✅ Total de mensajes combinados: {len(conversacion_messages)}")

        return jsonify({
            'success': True,
            'numero': numero,
            'twilio_messages': conversacion_messages,  # Mantener el nombre por compatibilidad con frontend
            'total_messages': len(conversacion_messages),
            'source': 'twilio_and_whapi'
        })
    except Exception as e:
        logger.error(f"❌ Error obteniendo conversación: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/twilio-chat/api/enviar-mensaje', methods=['POST'])
def twilio_enviar_mensaje():
    """Envía mensaje WhatsApp - Auto-detecta la línea correcta"""
    try:
        data = request.json
        to_number = data.get('to')
        message_body = data.get('message')
        media_url = data.get('media_url')
        source = data.get('source', 'auto')  # 'auto', 'twilio', 'whapi'

        if not to_number or not message_body:
            return jsonify({
                'success': False,
                'error': 'Faltan campos requeridos: to, message'
            }), 400

        message_id = None
        used_source = None

        # Si se especifica la fuente, usarla directamente
        if source == 'twilio':
            message_id = enviar_mensaje_whatsapp(to_number, message_body, media_url)
            used_source = 'twilio'
        elif source == 'whapi':
            message_id = enviar_mensaje_whapi(to_number, message_body, media_url)
            used_source = 'whapi'
        else:
            # Auto-detectar: Verificar si la conversación existe en Whapi
            numero_clean = to_number.replace('whatsapp:', '').replace('+', '')
            chat_id = f"{numero_clean}@s.whatsapp.net"

            # Intentar obtener conversaciones de Whapi
            try:
                chats_whapi = obtener_conversaciones_whapi()
                chat_ids_whapi = [chat.get('id', '') for chat in chats_whapi]

                if chat_id in chat_ids_whapi:
                    # La conversación existe en Whapi, usar Whapi
                    logger.info(f"📱 Conversación encontrada en Whapi, usando línea {WHAPI_PHONE_NUMBER}")
                    message_id = enviar_mensaje_whapi(to_number, message_body, media_url)
                    used_source = 'whapi'
                else:
                    # La conversación no existe en Whapi, usar Twilio
                    logger.info(f"📱 Conversación no encontrada en Whapi, usando Twilio")
                    message_id = enviar_mensaje_whatsapp(to_number, message_body, media_url)
                    used_source = 'twilio'
            except Exception as e:
                # Si falla la detección, usar Twilio por defecto
                logger.warning(f"⚠️ Error detectando fuente, usando Twilio por defecto: {str(e)}")
                message_id = enviar_mensaje_whatsapp(to_number, message_body, media_url)
                used_source = 'twilio'

        if message_id:
            return jsonify({
                'success': True,
                'message_id': message_id,
                'source': used_source,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Error al enviar mensaje via {used_source}'
            }), 500
    except Exception as e:
        logger.error(f"❌ Error en enviar_mensaje: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/twilio-chat/webhook/twilio', methods=['POST'])
def twilio_webhook():
    """Webhook para mensajes entrantes de Twilio - Con notificaciones SSE"""
    try:
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        body = request.form.get('Body')
        message_sid = request.form.get('MessageSid')
        num_media = request.form.get('NumMedia', '0')

        logger.info("="*60)
        logger.info("📨 MENSAJE ENTRANTE DE TWILIO")
        logger.info(f"   SID: {message_sid}")
        logger.info(f"   De: {from_number}")
        logger.info(f"   Para: {to_number}")
        logger.info(f"   Mensaje: {body}")
        logger.info(f"   Media: {num_media} archivo(s)")
        logger.info("="*60)

        # Extraer número limpio
        numero_clean = from_number.replace('whatsapp:', '').replace('+', '')

        # Enviar notificación WebSocket a todos los clientes conectados
        broadcast_websocket_event('new_message', {
            'numero': numero_clean,
            'from': from_number,
            'to': to_number,
            'body': body,
            'message_sid': message_sid,
            'num_media': int(num_media),
            'timestamp': datetime.now().isoformat()
        })

        # NO guardamos en Wix - Twilio ya lo guardó automáticamente
        # El mensaje estará disponible cuando se consulte la API de Twilio

        # Respuesta TwiML vacía (sin auto-reply)
        if TWILIO_AVAILABLE and MessagingResponse:
            resp = MessagingResponse()
            return str(resp), 200
        else:
            return '', 200
    except Exception as e:
        logger.error(f"❌ Error en webhook Twilio: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return '', 500

@app.route('/twilio-chat/webhook/whapi', methods=['GET', 'POST'])
def whapi_webhook():
    """Webhook para mensajes entrantes de Whapi - Con notificaciones SSE"""
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

        # Extraer información del mensaje de Whapi
        # La estructura de Whapi es diferente a Twilio
        event = data.get('event', {})
        messages = data.get('messages', [])

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

                logger.info("📱 Procesando mensaje de Whapi:")
                logger.info(f"   ID: {message_id}")
                logger.info(f"   Chat ID: {chat_id}")
                logger.info(f"   De: {from_number}")
                logger.info(f"   Tipo: {message_type}")
                logger.info(f"   Mensaje: {body}")
                logger.info(f"   From me: {from_me}")

                # Solo procesar mensajes entrantes (from_me = False)
                if not from_me:
                    # Extraer número limpio
                    numero_clean = chat_id.replace('@s.whatsapp.net', '').replace('@g.us', '')

                    # Enviar notificación WebSocket a todos los clientes conectados
                    broadcast_websocket_event('new_message', {
                        'numero': numero_clean,
                        'from': from_number,
                        'to': WHAPI_PHONE_NUMBER,
                        'body': body,
                        'message_id': message_id,
                        'chat_id': chat_id,
                        'type': message_type,
                        'timestamp': timestamp,
                        'source': 'whapi'
                    })

                    logger.info(f"✅ Notificación WebSocket enviada para mensaje de Whapi: {numero_clean}")

        return jsonify({'success': True}), 200

    except Exception as e:
        logger.error(f"❌ Error en webhook Whapi: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

# Servir archivos estáticos de Twilio
@app.route('/twilio-chat/static/<path:filename>')
def twilio_static(filename):
    """Servir archivos estáticos CSS/JS para Twilio"""
    return send_from_directory('static/twilio', filename)

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


if __name__ == "__main__":
    # Usar socketio.run() en lugar de app.run() para soportar WebSockets
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)