#!/usr/bin/env python3
"""
Script de prueba para descargar imagen de Wix con Puppeteer y subirla a DO Spaces
"""

import sys
from dotenv import load_dotenv
from descargar_bsl import descargar_imagen_wix_a_do_spaces

# Cargar variables de entorno
load_dotenv(override=True)

def test_wix_image_to_do_spaces():
    """Prueba descargar una imagen de Wix y subirla a DO Spaces"""

    # URL de prueba (imagen de un certificado existente)
    wix_image_url = "https://static.wixstatic.com/media/f82308_200000448a0d43c4a7050b981150a428~mv2.jpg"

    print(f"🧪 Probando descarga de Wix y subida a DO Spaces...")
    print(f"📷 URL de imagen Wix: {wix_image_url}")

    # Descargar y subir
    do_spaces_url = descargar_imagen_wix_a_do_spaces(wix_image_url)

    if do_spaces_url:
        print(f"\n✅ Proceso completado exitosamente!")
        print(f"🔗 URL en DO Spaces: {do_spaces_url}")
        print(f"\n💡 Ahora Puppeteer puede usar esta URL en lugar de la de Wix")
        return True
    else:
        print(f"\n❌ Error en el proceso")
        return False

if __name__ == '__main__':
    success = test_wix_image_to_do_spaces()
    sys.exit(0 if success else 1)
