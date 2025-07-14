import os
import requests
import base64
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")

# Configurar CORS para todas las aplicaciones
CORS(app, resources={
    r"/": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"], "methods": ["GET", "OPTIONS"]},
    r"/generar-pdf": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"]},
    r"/descargar-pdf-empresas": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"], "methods": ["GET", "POST", "OPTIONS"]}
})

# Configuración de carpetas por empresa
EMPRESA_FOLDERS = {
    "BSL": os.getenv("GOOGLE_DRIVE_FOLDER_ID_BSL", os.getenv("GOOGLE_DRIVE_FOLDER_ID")),  # Backward compatibility
    "LGS": os.getenv("GOOGLE_DRIVE_FOLDER_ID_LGS", "1lP8EMIgqZHEVs0JRE6cgXWihx6M7Jxjf")
}

# Configuración de dominios y rutas por empresa
EMPRESA_CONFIG = {
    "BSL": {
        "domain": "https://www.bsl.com.co",
        "path": "/descarga-whp/",
        "query_params": ""
    },
    "LGS": {
        "domain": "https://www.lgsplataforma.com", 
        "path": "/contrato/",
        "query_params": ""  # ← CAMBIAR A STRING VACÍO
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
        # Determinar empresa
        empresa = determinar_empresa(request)
        folder_id = EMPRESA_FOLDERS.get(empresa)
        
        if not folder_id:
            raise Exception(f"No se encontró configuración para la empresa {empresa}")
        
        documento = request.json.get("documento")
        if not documento:
            raise Exception("No se recibió el nombre del documento.")

        # Construir URL usando la nueva función
        url_obj = construir_url_documento(empresa, documento)
        print(f"🔗 Generando PDF para URL: {url_obj}")
        
        api2 = "https://v2018.api2pdf.com/chrome/url"
        res = requests.post(api2, headers={
            "Authorization": API2PDF_KEY,
            "Content-Type": "application/json"
        }, json={"url": url_obj, "inlinePdf": False, "fileName": f"{documento}.pdf"})
        
        data = res.json()
        if not data.get("success"):
            raise Exception(data.get("error", "Error API2PDF"))
        pdf_url = data["pdf"]

        # Descargar PDF localmente
        local = f"{empresa}_{documento}.pdf"  # Agregar prefijo de empresa
        r2 = requests.get(pdf_url)
        with open(local, "wb") as f:
            f.write(r2.content)

        # Subir a almacenamiento según el destino configurado
        if DEST == "drive":
            enlace = subir_pdf_a_drive(local, f"{documento}.pdf", folder_id)
        elif DEST == "drive-oauth":
            enlace = subir_pdf_a_drive_oauth(local, f"{documento}.pdf", folder_id)
        elif DEST == "gcs":
            # Para GCS, podrías usar un prefijo en el nombre del archivo
            enlace = subir_pdf_a_gcs(local, f"{empresa}/{documento}.pdf")
        else:
            raise Exception(f"Destino {DEST} no soportado")

        os.remove(local)
        
        # Preparar respuesta con CORS
        response = jsonify({"message": "✅ OK", "url": enlace, "empresa": empresa})
        origin = request.headers.get('Origin')
        if origin in get_allowed_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
        
        return response

    except Exception as e:
        print("❌", e)
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
    local_file = None
    try:
        # Manejar tanto GET como POST
        if request.method == "GET":
            documento = request.args.get("documento")
            empresa = request.args.get("empresa", "BSL").upper()
        else:  # POST
            data = request.get_json() or {}
            documento = data.get("documento")
            empresa = determinar_empresa(request)
        
        # Validar parámetros requeridos
        if not documento:
            error_msg = "No se recibió el nombre del documento."
            if request.method == "GET":
                return jsonify({"error": error_msg}), 400
            else:
                raise Exception(error_msg)

        if empresa not in EMPRESA_CONFIG:
            error_msg = f"Empresa '{empresa}' no válida. Empresas disponibles: {list(EMPRESA_CONFIG.keys())}"
            if request.method == "GET":
                return jsonify({"error": error_msg}), 400
            else:
                raise Exception(error_msg)

        # Construir URL usando la función existente
        url_obj = construir_url_documento(empresa, documento)
        print(f"🔗 Generando PDF para URL: {url_obj}")
        
        # Configurar opciones de API2PDF optimizadas
        api2_options = {
            "url": url_obj,
            "inlinePdf": False,
            "fileName": f"{documento}.pdf",
            "options": {
                "printBackground": True,
                "delay": 15000,  # Aumentado para permitir carga completa
                "scale": 0.75,
                "format": "A4",
                "margin": {
                    "top": "0.5in",
                    "bottom": "0.5in",
                    "left": "0.5in",
                    "right": "0.5in"
                },
                "waitUntil": "networkidle0"  # Esperar hasta que no haya peticiones de red
            }
        }
        
        # Llamada a API2PDF
        api2_endpoint = "https://v2018.api2pdf.com/chrome/url"
        api2_response = requests.post(
            api2_endpoint, 
            headers={
                "Authorization": API2PDF_KEY,
                "Content-Type": "application/json"
            }, 
            json=api2_options,
            timeout=120  # Timeout de 2 minutos
        )
        
        # Validar respuesta de API2PDF
        if not api2_response.ok:
            error_msg = f"Error HTTP {api2_response.status_code} de API2PDF: {api2_response.text}"
            print(f"❌ {error_msg}")
            if request.method == "GET":
                return jsonify({"error": error_msg}), 500
            else:
                raise Exception(error_msg)
        
        api2_data = api2_response.json()
        if not api2_data.get("success"):
            error_msg = api2_data.get("error", "Error desconocido de API2PDF")
            print(f"❌ API2PDF falló: {error_msg}")
            if request.method == "GET":
                return jsonify({"error": error_msg}), 500
            else:
                raise Exception(error_msg)
        
        pdf_url = api2_data.get("pdf")
        if not pdf_url:
            error_msg = "API2PDF no devolvió URL del PDF"
            print(f"❌ {error_msg}")
            if request.method == "GET":
                return jsonify({"error": error_msg}), 500
            else:
                raise Exception(error_msg)

        print(f"✅ PDF generado exitosamente: {pdf_url}")

        # Descargar PDF localmente con nombre único
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        local_file = f"{empresa}_{documento}_{unique_id}.pdf"
        
        print(f"📥 Descargando PDF a archivo local: {local_file}")
        pdf_download_response = requests.get(pdf_url, timeout=60)
        
        if not pdf_download_response.ok:
            error_msg = f"Error al descargar PDF generado: HTTP {pdf_download_response.status_code}"
            print(f"❌ {error_msg}")
            if request.method == "GET":
                return jsonify({"error": error_msg}), 500
            else:
                raise Exception(error_msg)
        
        # Guardar archivo localmente
        with open(local_file, "wb") as f:
            f.write(pdf_download_response.content)
        
        print(f"✅ PDF descargado exitosamente: {len(pdf_download_response.content)} bytes")

        # Preparar respuesta de descarga
        response = send_file(
            local_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{documento}.pdf"
        )
        
        # Configurar headers CORS
        origin = request.headers.get('Origin')
        if origin in get_allowed_origins():
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"

        # Función de limpieza que se ejecuta después de enviar el archivo
        @response.call_on_close
        def cleanup_file():
            try:
                if local_file and os.path.exists(local_file):
                    os.remove(local_file)
                    print(f"🗑️ Archivo temporal eliminado: {local_file}")
            except Exception as cleanup_error:
                print(f"⚠️ Error al eliminar archivo temporal: {cleanup_error}")

        print(f"📤 Enviando PDF al cliente: {documento}.pdf")
        return response

    except requests.exceptions.Timeout as e:
        error_msg = f"Timeout al generar PDF: {str(e)}"
        print(f"⏰ {error_msg}")
        
        # Limpiar archivo si existe
        if local_file and os.path.exists(local_file):
            try:
                os.remove(local_file)
            except:
                pass
        
        if request.method == "GET":
            return jsonify({"error": error_msg}), 408
        else:
            resp = jsonify({"error": error_msg})
            origin = request.headers.get('Origin')
            if origin in get_allowed_origins():
                resp.headers["Access-Control-Allow-Origin"] = origin
            return resp, 408
            
    except requests.exceptions.RequestException as e:
        error_msg = f"Error de conexión: {str(e)}"
        print(f"🌐 {error_msg}")
        
        # Limpiar archivo si existe
        if local_file and os.path.exists(local_file):
            try:
                os.remove(local_file)
            except:
                pass
        
        if request.method == "GET":
            return jsonify({"error": error_msg}), 503
        else:
            resp = jsonify({"error": error_msg})
            origin = request.headers.get('Origin')
            if origin in get_allowed_origins():
                resp.headers["Access-Control-Allow-Origin"] = origin
            return resp, 503
            
    except Exception as e:
        error_msg = f"Error interno: {str(e)}"
        print(f"❌ {error_msg}")
        
        # Limpiar archivo si existe
        if local_file and os.path.exists(local_file):
            try:
                os.remove(local_file)
            except:
                pass
        
        if request.method == "GET":
            return jsonify({"error": error_msg}), 500
        else:
            resp = jsonify({"error": error_msg})
            origin = request.headers.get('Origin')
            if origin in get_allowed_origins():
                resp.headers["Access-Control-Allow-Origin"] = origin
            return resp, 500

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)