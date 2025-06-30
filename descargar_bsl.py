import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from upload_to_drive_oauth import subir_pdf_a_drive_oauth
from gcs_uploader import subir_pdf_a_gcs

# Cargar variables de entorno
load_dotenv()

API2PDF_KEY = os.getenv("API2PDF_KEY")
DESTINO = os.getenv("STORAGE_DESTINATION", "gcs")  # "gcs" o "drive"

# Inicializar Flask y configurar CORS solo para la ruta /generar-pdf
app = Flask(__name__)
CORS(app, resources={r"/generar-pdf": {"origins": "https://www.bsl.com.co"}})

@app.route("/generar-pdf", methods=["OPTIONS"])
def options_pdf():
    return ('', 204, {
        'Access-Control-Allow-Origin': 'https://www.bsl.com.co',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    })

@app.route("/generar-pdf", methods=["POST"])
def generar_pdf():
    try:
        data = request.get_json()
        documento = data.get("documento")
        print(f"📝 Generando PDF para documento: {documento}")

        # Paso 1: Generar PDF con API2PDF
        api2pdf_url = "https://v2018.api2pdf.com/chrome/url"
        url_objetivo = f"https://www.bsl.com.co/descarga-whp/{documento}"
        response = requests.post(api2pdf_url, headers={
            "Authorization": API2PDF_KEY,
            "Content-Type": "application/json"
        }, json={
            "url": url_objetivo,
            "inlinePdf": False,
            "fileName": f"{documento}.pdf"
        })

        result = response.json()
        print("📝 Respuesta API2PDF:", result)

        if not result.get("success"):
            raise Exception(result.get("error", "Error generando PDF"))

        pdf_url = result["pdf"]
        print(f"🔗 PDF generado en: {pdf_url}")

        # Paso 2: Descargar PDF localmente
        local_filename = f"{documento}.pdf"
        r = requests.get(pdf_url)
        with open(local_filename, 'wb') as f:
            f.write(r.content)
        print(f"✅ PDF guardado como: {local_filename}")

        # Paso 3: Subir a destino elegido
        if DESTINO == "drive":
            folder_id = os.getenv("GOOGLE_DRIVE_UPLOAD_FOLDER_ID")
            enlace = subir_pdf_a_drive_oauth(local_filename, f"{documento}.pdf", folder_id)
        else:
            enlace = subir_pdf_a_gcs(local_filename, f"{documento}.pdf")

        # Paso 4: Eliminar archivo temporal
        os.remove(local_filename)

        return jsonify({
            "message": "✅ PDF generado y subido",
            "archivo": local_filename,
            "url": enlace
        })

    except Exception as e:
        print(f"❌ Error al generar o subir PDF: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
