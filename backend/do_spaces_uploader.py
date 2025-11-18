#!/usr/bin/env python3
"""
Digital Ocean Spaces Uploader
Módulo para subir imágenes a Digital Ocean Spaces (compatible con S3)
"""

import os
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

class DOSpacesUploader:
    def __init__(self):
        """Inicializa el cliente de Digital Ocean Spaces"""
        self.access_key = os.getenv('DO_SPACES_ACCESS_KEY')
        self.secret_key = os.getenv('DO_SPACES_SECRET_KEY')
        self.bucket_name = os.getenv('DO_SPACES_BUCKET_NAME')
        self.region = os.getenv('DO_SPACES_REGION', 'sfo3')
        self.endpoint_url = f'https://{self.region}.digitaloceanspaces.com'

        if not all([self.access_key, self.secret_key, self.bucket_name]):
            logger.warning("⚠️  Credenciales de DO Spaces no configuradas. Usando modo fallback.")
            self.client = None
            return

        try:
            self.client = boto3.client(
                's3',
                region_name=self.region,
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key
            )
            logger.info(f"✅ Cliente DO Spaces inicializado: {self.bucket_name} ({self.region})")
        except Exception as e:
            logger.error(f"❌ Error inicializando DO Spaces: {e}")
            self.client = None

    def upload_file(self, file_path, object_name=None, content_type=None, make_public=True):
        """
        Sube un archivo a DO Spaces

        Args:
            file_path: Ruta local del archivo
            object_name: Nombre del objeto en el bucket (opcional, usa el nombre del archivo)
            content_type: MIME type del archivo (opcional, se detecta automáticamente)
            make_public: Si True, hace el archivo público

        Returns:
            URL pública del archivo o None si falla
        """
        if not self.client:
            logger.error("❌ Cliente DO Spaces no disponible")
            return None

        if object_name is None:
            object_name = os.path.basename(file_path)

        # Detectar content type si no se especifica
        if content_type is None:
            ext = os.path.splitext(file_path)[1].lower()
            content_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp',
                '.pdf': 'application/pdf'
            }
            content_type = content_types.get(ext, 'application/octet-stream')

        try:
            extra_args = {'ContentType': content_type}
            if make_public:
                extra_args['ACL'] = 'public-read'

            self.client.upload_file(
                file_path,
                self.bucket_name,
                object_name,
                ExtraArgs=extra_args
            )

            # Construir URL pública
            public_url = f"https://{self.bucket_name}.{self.region}.digitaloceanspaces.com/{object_name}"
            logger.info(f"✅ Archivo subido: {public_url}")
            return public_url

        except ClientError as e:
            logger.error(f"❌ Error subiendo archivo a DO Spaces: {e}")
            return None

    def upload_bytes(self, file_bytes, object_name, content_type='image/jpeg', make_public=True):
        """
        Sube bytes directamente a DO Spaces (sin archivo temporal)

        Args:
            file_bytes: Bytes del archivo
            object_name: Nombre del objeto en el bucket
            content_type: MIME type del archivo
            make_public: Si True, hace el archivo público

        Returns:
            URL pública del archivo o None si falla
        """
        if not self.client:
            logger.error("❌ Cliente DO Spaces no disponible")
            return None

        try:
            extra_args = {'ContentType': content_type}
            if make_public:
                extra_args['ACL'] = 'public-read'

            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_name,
                Body=file_bytes,
                **extra_args
            )

            # Construir URL pública
            public_url = f"https://{self.bucket_name}.{self.region}.digitaloceanspaces.com/{object_name}"
            logger.info(f"✅ Bytes subidos: {public_url}")
            return public_url

        except ClientError as e:
            logger.error(f"❌ Error subiendo bytes a DO Spaces: {e}")
            return None

    def delete_file(self, object_name):
        """
        Elimina un archivo de DO Spaces

        Args:
            object_name: Nombre del objeto en el bucket

        Returns:
            True si se eliminó correctamente, False si falló
        """
        if not self.client:
            logger.error("❌ Cliente DO Spaces no disponible")
            return False

        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=object_name
            )
            logger.info(f"✅ Archivo eliminado: {object_name}")
            return True

        except ClientError as e:
            logger.error(f"❌ Error eliminando archivo de DO Spaces: {e}")
            return False

    def file_exists(self, object_name):
        """
        Verifica si un archivo existe en DO Spaces

        Args:
            object_name: Nombre del objeto en el bucket

        Returns:
            True si existe, False si no existe o hay error
        """
        if not self.client:
            return False

        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError:
            return False


# Instancia global
_do_spaces_uploader = None

def get_do_spaces_uploader():
    """Obtiene la instancia singleton del uploader"""
    global _do_spaces_uploader
    if _do_spaces_uploader is None:
        _do_spaces_uploader = DOSpacesUploader()
    return _do_spaces_uploader


def subir_imagen_a_do_spaces(file_bytes, filename, content_type='image/jpeg'):
    """
    Función helper para subir una imagen a DO Spaces

    Args:
        file_bytes: Bytes de la imagen
        filename: Nombre del archivo
        content_type: MIME type de la imagen

    Returns:
        URL pública de la imagen o None si falla
    """
    uploader = get_do_spaces_uploader()
    if not uploader.client:
        return None

    # Crear nombre único para el archivo
    object_name = f"wix-images/{filename}"
    return uploader.upload_bytes(file_bytes, object_name, content_type=content_type)
