import os
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

BUCKET_NAME = "certificados-bsl"
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE")

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

        # Como el bucket tiene acceso público, no usamos make_public()
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{nombre_visible}"
        print(f"📎 Enlace público: {public_url}")
        return public_url

    except Exception as e:
        print(f"❌ Error al subir a GCS: {e}")
        raise e
