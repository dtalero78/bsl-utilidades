#!/usr/bin/env python3
"""
Script de prueba para verificar la integración con Digital Ocean Spaces
"""

import os
from dotenv import load_dotenv
from do_spaces_uploader import get_do_spaces_uploader, subir_imagen_a_do_spaces

# Cargar variables de entorno
load_dotenv(override=True)

def test_upload():
    """Prueba subir una imagen de prueba"""
    print("🧪 Probando integración con Digital Ocean Spaces...")

    # Verificar credenciales
    print(f"\n📋 Configuración:")
    print(f"   Access Key: {os.getenv('DO_SPACES_ACCESS_KEY')[:10]}...")
    print(f"   Bucket: {os.getenv('DO_SPACES_BUCKET_NAME')}")
    print(f"   Region: {os.getenv('DO_SPACES_REGION')}")

    # Crear una imagen de prueba simple (1x1 pixel PNG)
    test_image_bytes = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
        0x00, 0x03, 0x01, 0x01, 0x00, 0x18, 0xDD, 0x8D,
        0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
        0x44, 0xAE, 0x42, 0x60, 0x82
    ])

    print(f"\n📤 Subiendo imagen de prueba ({len(test_image_bytes)} bytes)...")

    # Subir imagen
    url = subir_imagen_a_do_spaces(
        test_image_bytes,
        'test-image-001.png',
        content_type='image/png'
    )

    if url:
        print(f"✅ Imagen subida exitosamente!")
        print(f"🔗 URL: {url}")
        return True
    else:
        print(f"❌ Error subiendo imagen")
        return False

if __name__ == '__main__':
    success = test_upload()
    exit(0 if success else 1)
