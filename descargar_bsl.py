import os
import requests
import base64
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import traceback

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
        "pdf_selector": "#text1"  # Solo para LGS usar selector específico del contrato
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
            "delay": 10000,  # Tiempo para que cargue completamente
            "scale": 0.75,
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
        cod_empresa = data.get("codEmpresa", "").upper()
        tipo_examen = data.get("tipoExamen", "")
        
        print(f"📄 Documento solicitado: {documento}")
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

        if not documento:
            raise Exception("No se recibió el nombre del documento.")

        # Construir URL usando la nueva función
        print("🔗 Construyendo URL...")
        url_obj = construir_url_documento(empresa, documento)
        print(f"🔗 URL construida: {url_obj}")
        
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
        local = f"{empresa}_{documento}.pdf"
        print(f"💾 Archivo local: {local}")
        
        r2 = requests.get(pdf_url)
        with open(local, "wb") as f:
            f.write(r2.content)
        print("💾 PDF descargado correctamente")

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
        local = f"{empresa}_{documento}.pdf"
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