import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()

CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE")
DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

if not CREDENTIALS_FILE or not DRIVE_FOLDER_ID:
    raise Exception("❌ Faltan variables GOOGLE_CREDENTIALS_FILE o GOOGLE_DRIVE_FOLDER_ID en .env")

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

    print(f"✅ Archivo subido a Drive: {uploaded_file['webViewLink']}")
    return uploaded_file['webViewLink']
