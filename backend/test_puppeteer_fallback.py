#!/usr/bin/env python3
"""
Script de prueba para verificar el fallback de Puppeteer cuando requests falla con 403
"""

import sys
from dotenv import load_dotenv
from descargar_bsl import descargar_imagen_wix_con_puppeteer, descargar_imagen_wix_a_do_spaces

# Cargar variables de entorno
load_dotenv(override=True)

def test_puppeteer_direct():
    """Prueba descargar imagen directamente con Puppeteer"""
    print("=" * 60)
    print("TEST 1: Descarga directa con Puppeteer")
    print("=" * 60)

    # URL de prueba (imagen de un certificado existente)
    wix_image_url = "https://static.wixstatic.com/media/f82308_200000448a0d43c4a7050b981150a428~mv2.jpg"

    print(f"\n📷 URL de imagen Wix: {wix_image_url}\n")

    # Descargar con Puppeteer
    image_bytes, content_type = descargar_imagen_wix_con_puppeteer(wix_image_url)

    if image_bytes:
        print(f"\n✅ Descarga con Puppeteer exitosa!")
        print(f"   Tamaño: {len(image_bytes)} bytes")
        print(f"   Content-Type: {content_type}")
        return True
    else:
        print(f"\n❌ Error en descarga con Puppeteer")
        return False

def test_full_flow_with_fallback():
    """Prueba el flujo completo con fallback automático a Puppeteer"""
    print("\n" + "=" * 60)
    print("TEST 2: Flujo completo (requests → Puppeteer → DO Spaces)")
    print("=" * 60)

    # URL de prueba
    wix_image_url = "https://static.wixstatic.com/media/f82308_200000448a0d43c4a7050b981150a428~mv2.jpg"

    print(f"\n📷 URL de imagen Wix: {wix_image_url}\n")

    # Ejecutar flujo completo
    do_spaces_url = descargar_imagen_wix_a_do_spaces(wix_image_url)

    if do_spaces_url:
        print(f"\n✅ Proceso completado exitosamente!")
        print(f"🔗 URL en DO Spaces: {do_spaces_url}")
        print(f"\n💡 La imagen fue cacheada exitosamente")
        return True
    else:
        print(f"\n❌ Error en el proceso completo")
        return False

if __name__ == '__main__':
    print("\n🧪 Iniciando pruebas de fallback de Puppeteer\n")

    # Test 1: Puppeteer directo
    test1_ok = test_puppeteer_direct()

    # Test 2: Flujo completo
    test2_ok = test_full_flow_with_fallback()

    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Test 1 (Puppeteer directo): {'✅ PASS' if test1_ok else '❌ FAIL'}")
    print(f"Test 2 (Flujo completo): {'✅ PASS' if test2_ok else '❌ FAIL'}")
    print()

    sys.exit(0 if (test1_ok and test2_ok) else 1)
