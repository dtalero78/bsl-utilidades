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

load_dotenv(override=True)

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

@app.route("/menu")
def serve_menu():
    """Ruta para el menú principal de utilidades"""
    return send_from_directory(app.static_folder, "menu.html")

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

            # Recomendaciones médicas adicionales
            "recomendaciones_medicas": data.get("recomendaciones_medicas", ""),

            # Firmas
            "medico_nombre": data.get("medico_nombre", "JUAN JOSE REATIGA"),
            "medico_registro": data.get("medico_registro", "REGISTRO MEDICO NO 14791"),
            "medico_licencia": data.get("medico_licencia", "LICENCIA SALUD OCUPACIONAL 460"),

            "optometra_nombre": data.get("optometra_nombre", "Dr. Miguel Garzón Rincón"),
            "optometra_registro": data.get("optometra_registro", "Optómetra Ocupacional Res. 6473 04/07/2017"),

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
                    "delay": 8000,
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
                "puppeteerWaitForMethod": "WaitForNavigation",
                "puppeteerWaitForValue": "networkidle0",
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

# --- Endpoint: GENERAR CERTIFICADO DESDE ID DE WIX ---
@app.route("/generar-certificado-desde-wix/<wix_id>", methods=["GET", "OPTIONS"])
def generar_certificado_desde_wix(wix_id):
    """
    Endpoint que consulta los datos de Wix usando el _id y genera el certificado

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
                print(f"✅ Datos obtenidos de Wix para ID: {wix_id}")
                print(f"📋 Paciente: {datos_wix.get('primerNombre', '')} {datos_wix.get('primerApellido', '')}")
            else:
                # Si falla, usar datos de ejemplo
                print(f"⚠️  Error consultando Wix ({response.status_code}), usando datos de ejemplo")
                datos_wix = {
                    "_id": wix_id,
                    "numeroId": "1018483453",
                    "primerNombre": "DANIELA",
                    "segundoNombre": "",
                    "primerApellido": "CETARES",
                    "segundoApellido": "ZARATE",
                    "cargo": "Experto Manejo de Información",
                    "empresa": "PARTICULAR",
                    "codEmpresa": "PARTICULAR",
                    "tipoExamen": "Ingreso",
                    "fechaConsulta": datetime.now(),
                    "mdConceptoFinal": "ELEGIBLE PARA EL CARGO SIN RECOMENDACIONES LABORALES",
                    "examenes": ["Examen Médico Osteomuscular", "Audiometría", "Optometría"],
                    "medico": "JUAN 134",
                    "edad": "29",
                    "genero": "FEMENINO",
                    "fechaNacimiento": "16 de febrero de 1996",
                    "estadoCivil": "Soltero",
                    "hijos": "0",
                    "email": "ldcetares16@gmail.com",
                    "profesionUOficio": ""
                }
        except requests.exceptions.RequestException as e:
            # Si hay error de conexión, usar datos de ejemplo
            print(f"⚠️  Error de conexión con Wix: {e}")
            print(f"⚠️  Usando datos de ejemplo")
            datos_wix = {
                "_id": wix_id,
                "numeroId": "1018483453",
                "primerNombre": "DANIELA",
                "segundoNombre": "",
                "primerApellido": "CETARES",
                "segundoApellido": "ZARATE",
                "cargo": "Experto Manejo de Información",
                "empresa": "PARTICULAR",
                "codEmpresa": "PARTICULAR",
                "tipoExamen": "Ingreso",
                "fechaConsulta": datetime.now(),
                "mdConceptoFinal": "ELEGIBLE PARA EL CARGO SIN RECOMENDACIONES LABORALES",
                "examenes": ["Examen Médico Osteomuscular", "Audiometría", "Optometría"],
                "medico": "JUAN 134",
                "edad": "29",
                "genero": "FEMENINO",
                "fechaNacimiento": "16 de febrero de 1996",
                "estadoCivil": "Soltero",
                "hijos": "0",
                "email": "ldcetares16@gmail.com",
                "profesionUOficio": ""
            }

        # Transformar datos de Wix al formato del endpoint de certificado
        nombre_completo = f"{datos_wix.get('primerNombre', '')} {datos_wix.get('segundoNombre', '')} {datos_wix.get('primerApellido', '')} {datos_wix.get('segundoApellido', '')}".strip()

        fecha_consulta = datos_wix.get('fechaConsulta')
        if isinstance(fecha_consulta, datetime):
            fecha_formateada = fecha_consulta.strftime('%d de %B de %Y')
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

        # ===== CONSULTAR DATOS DEL FORMULARIO (edad, hijos, etc.) =====
        datos_formulario = None
        try:
            wix_id_historia = datos_wix.get('_id', wix_id)
            formulario_url = f"https://www.bsl.com.co/_functions/formularioPorIdGeneral?idGeneral={wix_id_historia}"
            print(f"🔍 Consultando datos del formulario para HistoriaClinica ID: {wix_id_historia}")

            formulario_response = requests.get(formulario_url, timeout=10)

            if formulario_response.status_code == 200:
                formulario_data = formulario_response.json()
                if formulario_data.get('success') and formulario_data.get('item'):
                    datos_formulario = formulario_data['item']
                    if datos_formulario:
                        print(f"✅ Datos del formulario obtenidos correctamente")
                        print(f"📸 Foto en FORMULARIO: {datos_formulario.get('foto', 'NO EXISTE')}")
                        # Sobrescribir los datos de HistoriaClinica con los del FORMULARIO si existen
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
                            # Convertir fecha de nacimiento a formato string legible
                            fecha_nac = datos_formulario.get('fechaNacimiento')
                            if isinstance(fecha_nac, str):
                                try:
                                    fecha_obj = datetime.fromisoformat(fecha_nac.replace('Z', '+00:00'))
                                    datos_wix['fechaNacimiento'] = fecha_obj.strftime('%d de %B de %Y')
                                except:
                                    datos_wix['fechaNacimiento'] = fecha_nac
                            elif isinstance(fecha_nac, datetime):
                                datos_wix['fechaNacimiento'] = fecha_nac.strftime('%d de %B de %Y')
                        if datos_formulario.get('foto'):
                            # Convertir URL de Wix a URL accesible
                            foto_wix = datos_formulario.get('foto')
                            if foto_wix.startswith('wix:image://v1/'):
                                # Formato: wix:image://v1/IMAGE_ID/FILENAME#originWidth=W&originHeight=H
                                # Extraer solo el IMAGE_ID (primera parte antes del segundo /)
                                # Ejemplo: wix:image://v1/7dbe9d_abc.../file.jpg
                                # Convertir a: https://static.wixstatic.com/media/IMAGE_ID
                                parts = foto_wix.replace('wix:image://v1/', '').split('/')
                                if len(parts) > 0:
                                    image_id = parts[0]  # Solo tomar el ID de la imagen
                                    datos_wix['foto_paciente'] = f"https://static.wixstatic.com/media/{image_id}"
                                else:
                                    datos_wix['foto_paciente'] = foto_wix
                            else:
                                datos_wix['foto_paciente'] = foto_wix
                        print(f"📊 Datos del formulario integrados: edad={datos_wix.get('edad')}, genero={datos_wix.get('genero')}, hijos={datos_wix.get('hijos')}")
                    else:
                        print(f"⚠️ No se encontraron datos del formulario para {wix_id_historia}")
                else:
                    print(f"⚠️ No se encontraron datos del formulario para {wix_id_historia}")
            else:
                print(f"⚠️ Error al consultar datos del formulario: {formulario_response.status_code}")
        except Exception as e:
            print(f"❌ Error consultando datos del formulario: {e}")

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

        # Mapear médico a imagen de firma (usar URLs públicas)
        medico = datos_wix.get('medico', 'JUAN 134')
        firma_medico_map = {
            "SIXTA": "FIRMA-SIXTA.png",
            "JUAN 134": "FIRMA-JUAN134.jpeg",
            "CESAR": "FIRMA-CESAR.png",
            "MARY": "FIRMA-MARY.png",
            "PRESENCIAL": "FIRMA-PRESENCIAL.png"
        }
        # Obtener firma del médico desde archivos locales
        firma_medico_filename = firma_medico_map.get(medico, "FIRMA-JUAN134.jpeg")
        firma_medico_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/static/{firma_medico_filename}"
        print(f"✅ Firma médico: {firma_medico_filename}")

        # Firma del paciente desde FORMULARIO
        firma_paciente_wix = datos_wix.get('firma')
        firma_paciente_url = None
        if firma_paciente_wix:
            if firma_paciente_wix.startswith('wix:image://v1/'):
                # Convertir URL de Wix a URL estática accesible (mantener como URL)
                parts = firma_paciente_wix.replace('wix:image://v1/', '').split('/')
                if len(parts) > 0:
                    image_id = parts[0]
                    firma_paciente_url = f"https://static.wixstatic.com/media/{image_id}"
            else:
                firma_paciente_url = firma_paciente_wix

        # Firma del optómetra (siempre la misma)
        firma_optometra_url = "https://bsl-utilidades-yp78a.ondigitalocean.app/static/FIRMA-OPTOMETRA.png"
        print(f"✅ Firma optómetra: FIRMA-OPTOMETRA.png")

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
            "medico_nombre": "JUAN JOSE REATIGA",
            "medico_registro": "REGISTRO MEDICO NO 14791",
            "medico_licencia": "LICENCIA SALUD OCUPACIONAL 460",
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

        # Llamar al endpoint de generación de certificado internamente
        # (simular la llamada interna)
        from flask import current_app

        with current_app.test_request_context(
            '/generar-certificado-medico',
            method='POST',
            json=payload_certificado,
            headers={'Content-Type': 'application/json'}
        ):
            resultado = generar_certificado_medico()

            # Si es una tupla (response, status_code), extraer la response
            if isinstance(resultado, tuple):
                resultado = resultado[0]

            # Obtener el JSON de la respuesta
            if hasattr(resultado, 'get_json'):
                resultado_json = resultado.get_json()
            else:
                resultado_json = resultado

            # Verificar si la generación fue exitosa
            if not resultado_json.get('success'):
                # Si hubo error, retornar JSON con el error
                response = jsonify(resultado_json)
                response.headers["Access-Control-Allow-Origin"] = "*"
                return response

            # Obtener URL del PDF generado
            pdf_url = resultado_json.get('pdf_url')
            if not pdf_url:
                error_response = jsonify({
                    "success": False,
                    "error": "No se pudo obtener la URL del PDF generado"
                })
                error_response.headers["Access-Control-Allow-Origin"] = "*"
                return error_response, 500

            # Descargar PDF localmente para envío directo
            print("💾 Descargando PDF para envío directo...")
            documento_id = datos_wix.get('numeroId', wix_id)
            documento_sanitized = str(documento_id).replace(" ", "_").replace("/", "_").replace("\\", "_")
            local = f"certificado_medico_{documento_sanitized}.pdf"

            try:
                r2 = requests.get(pdf_url, timeout=30)
                r2.raise_for_status()
                with open(local, "wb") as f:
                    f.write(r2.content)

                print(f"✅ PDF descargado localmente: {local}")

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
                print(f"❌ Error descargando PDF: {e}")
                # Si falla la descarga, intentar redireccionar a la URL
                response = redirect(pdf_url)
                response.headers["Access-Control-Allow-Origin"] = "*"
                return response

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
                print(f"✅ Datos obtenidos de Wix para ID: {wix_id}")
            else:
                print(f"⚠️  Error consultando Wix ({response.status_code}), usando datos de ejemplo")
                datos_wix = {
                    "_id": wix_id,
                    "numeroId": "1018483453",
                    "primerNombre": "DANIELA",
                    "segundoNombre": "",
                    "primerApellido": "CETARES",
                    "segundoApellido": "ZARATE",
                    "cargo": "Experto Manejo de Información",
                    "empresa": "PARTICULAR",
                    "tipoExamen": "Ingreso",
                    "fechaConsulta": datetime.now(),
                    "examenes": ["Examen Médico Osteomuscular", "Audiometría", "Optometría"],
                    "medico": "JUAN 134",
                    "edad": "29",
                    "genero": "FEMENINO",
                    "fechaNacimiento": "16 de febrero de 1996",
                    "estadoCivil": "Soltero",
                    "hijos": "0",
                    "email": "ldcetares16@gmail.com",
                    "profesionUOficio": ""
                }
        except Exception as e:
            print(f"⚠️  Error de conexión a Wix: {str(e)}")
            print(f"⚠️  Usando datos de ejemplo")
            datos_wix = {
                "_id": wix_id,
                "numeroId": "1018483453",
                "primerNombre": "DANIELA",
                "segundoNombre": "",
                "primerApellido": "CETARES",
                "segundoApellido": "ZARATE",
                "cargo": "Experto Manejo de Información",
                "empresa": "PARTICULAR",
                "tipoExamen": "Ingreso",
                "fechaConsulta": datetime.now(),
                "examenes": ["Examen Médico Osteomuscular", "Audiometría", "Optometría"],
                "medico": "JUAN 134",
                "edad": "29",
                "genero": "FEMENINO",
                "fechaNacimiento": "16 de febrero de 1996",
                "estadoCivil": "Soltero",
                "hijos": "0",
                "email": "ldcetares16@gmail.com",
                "profesionUOficio": ""
            }

        # Transformar datos de Wix al formato del certificado
        nombre_completo = f"{datos_wix.get('primerNombre', '')} {datos_wix.get('segundoNombre', '')} {datos_wix.get('primerApellido', '')} {datos_wix.get('segundoApellido', '')}".strip()

        fecha_consulta = datos_wix.get('fechaConsulta')
        if isinstance(fecha_consulta, datetime):
            fecha_formateada = fecha_consulta.strftime('%d de %B de %Y')
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

        # ===== CONSULTAR DATOS DEL FORMULARIO (edad, hijos, etc.) =====
        datos_formulario = None
        try:
            wix_id_historia = datos_wix.get('_id', wix_id)
            formulario_url = f"https://www.bsl.com.co/_functions/formularioPorIdGeneral?idGeneral={wix_id_historia}"
            print(f"🔍 Consultando datos del formulario para HistoriaClinica ID: {wix_id_historia}", flush=True)

            formulario_response = requests.get(formulario_url, timeout=10)

            if formulario_response.status_code == 200:
                formulario_data = formulario_response.json()
                if formulario_data.get('success') and formulario_data.get('item'):
                    datos_formulario = formulario_data['item']
                    if datos_formulario:
                        print(f"✅ Datos del formulario obtenidos correctamente", flush=True)
                        print(f"📸 Foto en FORMULARIO: {datos_formulario.get('foto', 'NO EXISTE')}", flush=True)
                        # Sobrescribir los datos de HistoriaClinica con los del FORMULARIO si existen
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
                            # Convertir fecha de nacimiento a formato string legible
                            fecha_nac = datos_formulario.get('fechaNacimiento')
                            if isinstance(fecha_nac, str):
                                try:
                                    fecha_obj = datetime.fromisoformat(fecha_nac.replace('Z', '+00:00'))
                                    datos_wix['fechaNacimiento'] = fecha_obj.strftime('%d de %B de %Y')
                                except:
                                    datos_wix['fechaNacimiento'] = fecha_nac
                            elif isinstance(fecha_nac, datetime):
                                datos_wix['fechaNacimiento'] = fecha_nac.strftime('%d de %B de %Y')
                        if datos_formulario.get('foto'):
                            # Convertir URL de Wix a URL accesible
                            foto_wix = datos_formulario.get('foto')
                            if foto_wix.startswith('wix:image://v1/'):
                                # Formato: wix:image://v1/IMAGE_ID/FILENAME#originWidth=W&originHeight=H
                                # Extraer solo el IMAGE_ID (primera parte antes del segundo /)
                                # Ejemplo: wix:image://v1/7dbe9d_abc.../file.jpg
                                # Convertir a: https://static.wixstatic.com/media/IMAGE_ID
                                parts = foto_wix.replace('wix:image://v1/', '').split('/')
                                if len(parts) > 0:
                                    image_id = parts[0]  # Solo tomar el ID de la imagen
                                    datos_wix['foto_paciente'] = f"https://static.wixstatic.com/media/{image_id}"
                                else:
                                    datos_wix['foto_paciente'] = foto_wix
                            else:
                                datos_wix['foto_paciente'] = foto_wix
                        print(f"📊 Datos del formulario integrados: edad={datos_wix.get('edad')}, genero={datos_wix.get('genero')}, hijos={datos_wix.get('hijos')}", flush=True)
                    else:
                        print(f"⚠️ No se encontraron datos del formulario para {wix_id_historia}", flush=True)
                else:
                    print(f"⚠️ No se encontraron datos del formulario para {wix_id_historia}", flush=True)
            else:
                print(f"⚠️ Error al consultar datos del formulario: {formulario_response.status_code}", flush=True)
        except Exception as e:
            print(f"❌ Error consultando datos del formulario: {e}", flush=True)

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

        # Mapear médico a imagen de firma (usar URLs públicas)
        medico = datos_wix.get('medico', 'JUAN 134')
        firma_medico_map = {
            "SIXTA": "FIRMA-SIXTA.png",
            "JUAN 134": "FIRMA-JUAN134.jpeg",
            "CESAR": "FIRMA-CESAR.png",
            "MARY": "FIRMA-MARY.png",
            "PRESENCIAL": "FIRMA-PRESENCIAL.png"
        }
        # Obtener firma del médico desde archivos locales
        firma_medico_filename = firma_medico_map.get(medico, "FIRMA-JUAN134.jpeg")
        firma_medico_url = f"https://bsl-utilidades-yp78a.ondigitalocean.app/static/{firma_medico_filename}"
        print(f"✅ Firma médico: {firma_medico_filename}")

        # Firma del paciente desde FORMULARIO
        firma_paciente_wix = datos_wix.get('firma')
        firma_paciente_url = None
        if firma_paciente_wix:
            if firma_paciente_wix.startswith('wix:image://v1/'):
                # Convertir URL de Wix a URL estática accesible (mantener como URL)
                parts = firma_paciente_wix.replace('wix:image://v1/', '').split('/')
                if len(parts) > 0:
                    image_id = parts[0]
                    firma_paciente_url = f"https://static.wixstatic.com/media/{image_id}"
            else:
                firma_paciente_url = firma_paciente_wix

        # Firma del optómetra (siempre la misma)
        firma_optometra_url = "https://bsl-utilidades-yp78a.ondigitalocean.app/static/FIRMA-OPTOMETRA.png"
        print(f"✅ Firma optómetra: FIRMA-OPTOMETRA.png")

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
            "medico_nombre": "JUAN JOSE REATIGA",
            "medico_registro": "REGISTRO MEDICO NO 14791",
            "medico_licencia": "LICENCIA SALUD OCUPACIONAL 460",
            "firma_medico_url": firma_medico_url,
            "firma_paciente_url": firma_paciente_url,
            "optometra_nombre": "Dr. Miguel Garzón Rincón",
            "optometra_registro": "Optómetra Ocupacional Res. 6473 04/07/2017",
            "firma_optometra_url": firma_optometra_url,
            "examenes_detallados": [],
            "logo_url": "https://bsl-utilidades-yp78a.ondigitalocean.app/static/logo-bsl.png"
        }

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)