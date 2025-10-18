import os
import requests
import base64
from flask import Flask, request, jsonify, send_file, send_from_directory, redirect, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import traceback
from jinja2 import Template
import uuid
from datetime import datetime, timedelta
import tempfile
import csv
import io

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")

# Configurar CORS para todas las aplicaciones
CORS(app, resources={
    r"/": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"], "methods": ["GET", "OPTIONS"]},
    r"/generar-pdf": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"]},
    r"/subir-pdf-directo": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"]},
    r"/descargar-pdf-drive/*": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"], "methods": ["GET", "OPTIONS"]},
    r"/descargar-pdf-empresas": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"], "methods": ["GET", "POST", "OPTIONS"]},
    r"/generar-certificado-medico": {"origins": "*", "methods": ["POST", "OPTIONS"]},  # Permitir cualquier origen para Wix
    r"/images/*": {"origins": "*", "methods": ["GET", "OPTIONS"]}  # Servir imágenes públicamente
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
            "foto_paciente": data.get("foto_paciente", None),

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

            # Firmas
            "medico_nombre": data.get("medico_nombre", "JUAN JOSE REATIGA"),
            "medico_registro": data.get("medico_registro", "REGISTRO MEDICO NO 14791"),
            "medico_licencia": data.get("medico_licencia", "LICENCIA SALUD OCUPACIONAL 460"),

            "optometra_nombre": data.get("optometra_nombre", "Dr. Miguel Garzón Rincón"),
            "optometra_registro": data.get("optometra_registro", "Optómetra Ocupacional Res. 6473 04/07/2017"),

            # Exámenes detallados (página 2, opcional)
            "examenes_detallados": data.get("examenes_detallados", [])
        }

        # Renderizar template HTML
        print("🎨 Renderizando plantilla HTML...")
        html_content = render_template("certificado_medico.html", **datos_certificado)

        # Configurar API2PDF
        api2pdf_key = API2PDF_KEY

        # Modo desarrollo: si la API key es dummy, devolver HTML en lugar de PDF
        if api2pdf_key == "dummy-api-key-for-dev":
            print("🔧 Modo desarrollo: devolviendo HTML en lugar de PDF")
            # Guardar HTML temporalmente para descarga
            temp_html = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode='w')
            temp_html.write(html_content)
            temp_html.close()
            pdf_url = f"file://{temp_html.name}"
            print(f"📄 HTML de prueba guardado en: {temp_html.name}")
        else:
            if not api2pdf_key:
                raise Exception("API2PDF_KEY no configurada en variables de entorno")

            # Generar PDF con API2PDF
            print("📄 Generando PDF con API2PDF...")
            api2pdf_url = "https://v2.api2pdf.com/chrome/html"

            payload = {
                "html": html_content,
                "options": {
                    "delay": 3000,
                    "displayHeaderFooter": False,
                    "printBackground": True,
                    "format": "Letter",
                    "scale": 1,
                    "margin": {
                        "top": "0",
                        "bottom": "0",
                        "left": "0",
                        "right": "0"
                    }
                },
                "inlineHtml": True
            }

            headers = {
                "Authorization": api2pdf_key,
                "Content-Type": "application/json"
            }

            response = requests.post(api2pdf_url, json=payload, headers=headers)

            if response.status_code != 200:
                raise Exception(f"Error generando PDF: {response.text}")

            result = response.json()
            pdf_url = result.get("FileUrl") or result.get("pdf")

            if not pdf_url:
                raise Exception("No se pudo obtener la URL del PDF generado")

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

@app.route("/images/<filename>")
def serve_image(filename):
    """Servir imágenes públicamente para API2PDF"""
    try:
        return send_from_directory("static", filename)
    except FileNotFoundError:
        return "Image not found", 404

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
        medicos_disponibles = ["SIXTA", "JUAN 134", "CESAR", "MARY", "NUBIA"]

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

                # Calcular hora de atención con incrementos de 10 minutos por registro
                # idx - 1 porque idx empieza en 1
                hora_atencion = (hora_base + timedelta(minutes=(idx - 1) * 10)).strftime('%H:%M')

                # Asignar médico de forma equitativa (round-robin)
                medico_asignado = medicos_disponibles[(idx - 1) % len(medicos_disponibles)]

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
                    "ciudad": row_normalized.get('CIUDAD', '').strip(),
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)