import os
import base64
import tempfile
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()

base64_str = os.getenv("GOOGLE_CREDENTIALS_BASE64")
if not base64_str:
    raise Exception("❌ Falta GOOGLE_CREDENTIALS_BASE64 en .env")

decoded_bytes = base64.b64decode(base64_str)
temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
temp_file.write(decoded_bytes)
temp_file.close()
CREDENTIALS_FILE = temp_file.name

DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
if not DRIVE_FOLDER_ID:
    raise Exception("❌ Falta GOOGLE_DRIVE_FOLDER_ID en .env")

def subir_pdf_a_drive(nombre_archivo_local, nombre_visible):
    """Sube el PDF a Google Drive y retorna el enlace público"""
    print(f"🚀 Subiendo {nombre_visible} a Google Drive...")

    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': nombre_visible,
        'parents': [DRIVE_FOLDER_ID]
    }

    media = MediaFileUpload(nombre_archivo_local, mimetype='application/pdf')
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    # Hacerlo público (imprescindible si quieres que cualquiera lo vea)
    service.permissions().create(
        fileId=uploaded_file["id"],
        body={'role': 'reader', 'type': 'anyone'}
    ).execute()

    print(f"✅ Archivo subido a Drive: {uploaded_file['webViewLink']}")
    return uploaded_file['webViewLink']
