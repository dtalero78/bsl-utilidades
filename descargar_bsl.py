import os
import requests
import base64
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static")

CORS(app, resources={
    r"/generar-pdf": {"origins": "https://www.bsl.com.co"},
    r"/descargar-pdf-empresas": {"origins": "https://www.bsl.com.co"}
})

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

# --- Endpoint: GENERAR PDF Y SUBIR A STORAGE ---
@app.route("/generar-pdf", methods=["OPTIONS"])
def options_pdf():
    return ("", 204, {
        "Access-Control-Allow-Origin": "https://www.bsl.com.co",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

@app.route("/generar-pdf", methods=["POST"])
def generar_pdf():
    try:
        documento = request.json.get("documento")
        if not documento:
            raise Exception("No se recibió el nombre del documento.")

        api2 = "https://v2018.api2pdf.com/chrome/url"
        url_obj = f"https://www.bsl.com.co/descarga-whp/{documento}"
        res = requests.post(api2, headers={
            "Authorization": API2PDF_KEY,
            "Content-Type": "application/json"
        }, json={"url": url_obj, "inlinePdf": False, "fileName": f"{documento}.pdf"})
        data = res.json()
        if not data.get("success"):
            raise Exception(data.get("error", "Error API2PDF"))
        pdf_url = data["pdf"]

        local = f"{documento}.pdf"
        r2 = requests.get(pdf_url)
        with open(local, "wb") as f:
            f.write(r2.content)

        # Subir a almacenamiento
        if DEST == "drive":
            enlace = subir_pdf_a_drive(local, f"{documento}.pdf")
        elif DEST == "drive-oauth":
            folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
            enlace = subir_pdf_a_drive_oauth(local, f"{documento}.pdf", folder_id)
        elif DEST == "gcs":
            enlace = subir_pdf_a_gcs(local, f"{documento}.pdf")
        else:
            raise Exception(f"Destino {DEST} no soportado")

        os.remove(local)
        return jsonify({"message": "✅ OK", "url": enlace})

    except Exception as e:
        print("❌", e)
        return jsonify({"error": str(e)}), 500

# --- Endpoint: GENERAR Y DESCARGAR PDF DIRECTO ---
@app.route("/descargar-pdf-empresas", methods=["OPTIONS"])
def options_descargar_pdf_empresas():
    return ("", 204, {
        "Access-Control-Allow-Origin": "https://www.bsl.com.co",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

@app.route("/descargar-pdf-empresas", methods=["POST"])
def descargar_pdf_empresas():
    try:
        documento = request.json.get("documento")
        if not documento:
            raise Exception("No se recibió el nombre del documento.")

        api2 = "https://v2018.api2pdf.com/chrome/url"
        url_obj = f"https://www.bsl.com.co/descarga-whp/{documento}"
        res = requests.post(api2, headers={
            "Authorization": API2PDF_KEY,
            "Content-Type": "application/json"
        }, json={"url": url_obj, "inlinePdf": False, "fileName": f"{documento}.pdf"})
        data = res.json()
        if not data.get("success"):
            raise Exception(data.get("error", "Error API2PDF"))
        pdf_url = data["pdf"]

        local = f"{documento}.pdf"
        r2 = requests.get(pdf_url)
        with open(local, "wb") as f:
            f.write(r2.content)

        response = send_file(
            local,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{documento}.pdf"
        )
        response.headers["Access-Control-Allow-Origin"] = "https://www.bsl.com.co"

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
        resp.headers["Access-Control-Allow-Origin"] = "https://www.bsl.com.co"
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
