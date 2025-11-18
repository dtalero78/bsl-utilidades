import os
import base64
import tempfile
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

BUCKET_NAME = "certificados-bsl"
BASE64_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS_BASE64")

if not BASE64_CREDENTIALS:
    raise Exception("❌ Falta GOOGLE_CREDENTIALS_BASE64 en .env")

# Crear archivo temporal desde base64
decoded_bytes = base64.b64decode(BASE64_CREDENTIALS)
temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
temp_file.write(decoded_bytes)
temp_file.close()
CREDENTIALS_FILE = temp_file.name

def subir_pdf_a_gcs(ruta_local, nombre_visible):
    """Sube un PDF a Google Cloud Storage y devuelve el enlace público"""
    print(f"🚀 Subiendo {nombre_visible} a GCS...")

    try:
        # Inicializar el cliente de GCS
        client = storage.Client.from_service_account_json(CREDENTIALS_FILE)
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(nombre_visible)

        # Subir archivo
        blob.upload_from_filename(ruta_local)
        print("✅ PDF subido correctamente")

        # Construir URL pública (si el bucket es público)
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{nombre_visible}"
        print(f"📎 Enlace público: {public_url}")
        return public_url

    except Exception as e:
        print(f"❌ Error al subir a GCS: {e}")
        raise e
