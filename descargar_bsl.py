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
    r"/generar-pdf": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"]},
    r"/descargar-pdf-empresas": {"origins": ["https://www.bsl.com.co", "https://www.lgs.com.co", "https://www.lgsplataforma.com"]}
})

# Configuración de carpetas por empresa
EMPRESA_FOLDERS = {
    "BSL": os.getenv("GOOGLE_DRIVE_FOLDER_ID_BSL", os.getenv("GOOGLE_DRIVE_FOLDER_ID")),  # Backward compatibility
    "LGS": os.getenv("GOOGLE_DRIVE_FOLDER_ID_LGS", "1lP8EMIgqZHEVs0JRE6cgXWihx6M7Jxjf")
}

# Configuración de dominios por empresa
EMPRESA_DOMAINS = {
    "BSL": "https://www.bsl.com.co",
    "LGS": "https://www.lgs.com.co"
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
    # Verificar el header Origin
    origin = request.headers.get('Origin', '')
    if 'bsl.com.co' in origin:
        return 'BSL'
    elif 'lgs.com.co' in origin or 'lgsplataforma.com' in origin:
        return 'LGS'
    
    # Verificar el header Referer como fallback
    referer = request.headers.get('Referer', '')
    if 'bsl.com.co' in referer:
        return 'BSL'
    elif 'lgs.com.co' in referer or 'lgsplataforma.com' in referer:
        return 'LGS'
    
    # Verificar si viene como parámetro en el JSON
    data = request.get_json() or {}
    empresa = data.get('empresa', '').upper()
    if empresa in EMPRESA_FOLDERS:
        return empresa
    
    # Default a BSL para backward compatibility
    return 'BSL'

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

        # Construir URL basándose en la empresa
        domain = EMPRESA_DOMAINS.get(empresa, EMPRESA_DOMAINS['BSL'])
        api2 = "https://v2018.api2pdf.com/chrome/url"
        url_obj = f"{domain}/descarga-whp/{documento}"
        
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
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    
    if origin in allowed_origins:
        response_headers["Access-Control-Allow-Origin"] = origin
    
    return ("", 204, response_headers)

@app.route("/descargar-pdf-empresas", methods=["POST"])
def descargar_pdf_empresas():
    try:
        # Determinar empresa
        empresa = determinar_empresa(request)
        
        documento = request.json.get("documento")
        if not documento:
            raise Exception("No se recibió el nombre del documento.")

        # Construir URL basándose en la empresa
        domain = EMPRESA_DOMAINS.get(empresa, EMPRESA_DOMAINS['BSL'])
        api2 = "https://v2018.api2pdf.com/chrome/url"
        url_obj = f"{domain}/descarga-whp/{documento}"
        
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
@app.route("/")
def serve_frontend():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)