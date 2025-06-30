# descargar_bsl.py
import os, requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from gcs_uploader import subir_pdf_a_gcs
from drive_uploader import subir_pdf_a_drive

load_dotenv()

API2PDF_KEY = os.getenv("API2PDF_KEY")
DEST = os.getenv("STORAGE_DESTINATION", "gcs")  # "gcs" o "drive"

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
        # 1) Generar PDF
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

        # 2) Bajar PDF local
        local = f"{documento}.pdf"
        r2 = requests.get(pdf_url)
        with open(local, "wb") as f:
            f.write(r2.content)

        # 3) Subir a GCS o Drive (service account)
        if DEST == "drive":
            enlace = subir_pdf_a_drive(local, f"{documento}.pdf")
        else:
            enlace = subir_pdf_a_gcs(local, f"{documento}.pdf")

        # 4) Borra local y responde
        os.remove(local)
        return jsonify({"message": "✅ OK", "url": enlace})

    except Exception as e:
        print("❌", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
