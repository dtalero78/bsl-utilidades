import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from upload_to_drive_oauth import subir_pdf_a_drive_oauth

load_dotenv()

API2PDF_KEY = os.getenv("API2PDF_KEY")
DEST = os.getenv("STORAGE_DESTINATION", "drive-oauth")  # solo "drive-oauth"

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
        # 1) Generar PDF con API2PDF
        api2pdf_url = "https://v2018.api2pdf.com/chrome/url"
        url_obj = f"https://www.bsl.com.co/descarga-whp/{documento}"
        res = requests.post(api2pdf_url, headers={
            "Authorization": API2PDF_KEY,
            "Content-Type": "application/json"
        }, json={
            "url": url_obj,
            "inlinePdf": False,
            "fileName": f"{documento}.pdf"
        })
        data = res.json()
        if not data.get("success"):
            raise Exception(data.get("error", "Error generando PDF"))
        pdf_url = data["pdf"]

        # 2) Descargar PDF localmente
        local = f"{documento}.pdf"
        r2 = requests.get(pdf_url)
        with open(local, "wb") as f:
            f.write(r2.content)

        # 3) Subir a Google Drive (OAuth)
        folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        enlace = subir_pdf_a_drive_oauth(local, f"{documento}.pdf", folder_id)

        # 4) Borra el archivo local
        os.remove(local)
        return jsonify({"message": "✅ OK", "url": enlace})

    except Exception as e:
        print("❌", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
