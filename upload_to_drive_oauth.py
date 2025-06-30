import os
import pickle
import base64
import tempfile
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']

load_dotenv()

# Ruta al token generado localmente
TOKEN_FILE = os.getenv("GOOGLE_OAUTH_TOKEN_FILE", "token_drive_oauth.pkl")
base64_secret = os.getenv("GOOGLE_OAUTH_CREDENTIALS_BASE64")

if not base64_secret:
    raise Exception("❌ Falta GOOGLE_OAUTH_CREDENTIALS_BASE64 en .env")

# Crear archivo temporal de credenciales
decoded_bytes = base64.b64decode(base64_secret)
temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
temp_file.write(decoded_bytes)
temp_file.close()
CREDENTIALS_FILE = temp_file.name

def get_authenticated_service():
    if not os.path.exists(TOKEN_FILE):
        raise Exception("❌ El archivo de token no existe. Debes generarlo localmente y subirlo al servidor.")

    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)

    return build('drive', 'v3', credentials=creds)

def subir_pdf_a_drive_oauth(ruta_local, nombre_visible, folder_id=None):
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
