import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# Este es el scope necesario para acceder solo a los archivos que subas con tu app
SCOPES = ['https://www.googleapis.com/auth/drive.file']

load_dotenv()

CREDENTIALS_FILE = os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE")
TOKEN_FILE = os.getenv("GOOGLE_OAUTH_TOKEN_FILE")

def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)

def subir_pdf_a_drive_oauth(ruta_local, nombre_visible, folder_id=None):
    """Sube un PDF a Google Drive (modo usuario OAuth)"""

    # 🔍 Verificación de existencia del archivo
    if not ruta_local or not os.path.exists(ruta_local):
        raise Exception(f"❌ El archivo '{ruta_local}' no existe o es inválido")

    service = get_authenticated_service()

    file_metadata = {'name': nombre_visible}
    if folder_id:
        file_metadata['parents'] = [folder_id]

    media = MediaFileUpload(ruta_local, mimetype='application/pdf')

    archivo = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    print(f"✅ PDF subido a Drive: {archivo['webViewLink']}")
    return archivo['webViewLink']
