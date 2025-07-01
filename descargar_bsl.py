import os
import requests
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# Reconstruir token OAuth desde base64 si es necesario
TOKEN_B64 = os.getenv("GOOGLE_OAUTH_TOKEN_B64")
TOKEN_PATH = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token_drive_oauth.pkl")
if TOKEN_B64 and not os.path.exists(TOKEN_PATH):
    with open(TOKEN_PATH, "wb") as f:
        f.write(base64.b64decode(TOKEN_B64))

API2PDF_KEY = os.getenv("API2PDF_KEY")
DEST = os.getenv("STORAGE_DESTINATION", "drive")  # drive, drive-oauth, gcs

# Importa la función correcta según el destino
if DEST == "drive":
    from drive_uploader import subir_pdf_a_drive
elif DEST == "drive-oauth":
    from upload_to_drive_oauth import subir_pdf_a_drive_oauth
elif DEST == "gcs":
    from gcs_uploader import subir_pdf_a_gcs
else:
    raise Exception(f"Destino {DEST} no soportado")

app = Flask(__name__)
CORS(app, resources={r"/generar-pdf": {"origins": "https://www.bsl.com.co"}})

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

        # 1. Generar PDF desde la web
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

        # 2. Descargar PDF localmente
        local = f"{documento}.pdf"
        r2 = requests.get(pdf_url)
        with open(local, "wb") as f:
            f.write(r2.content)

        # 3. Subir a almacenamiento correspondiente
        if DEST == "drive":
            enlace = subir_pdf_a_drive(local, f"{documento}.pdf")
        elif DEST == "drive-oauth":
            folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
            enlace = subir_pdf_a_drive_oauth(local, f"{documento}.pdf", folder_id)
        elif DEST == "gcs":
            enlace = subir_pdf_a_gcs(local, f"{documento}.pdf")
        else:
            raise Exception(f"Destino {DEST} no soportado")

        # 4. Limpiar archivo local
        os.remove(local)
        return jsonify({"message": "✅ OK", "url": enlace})

    except Exception as e:
        print("❌", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
