#!/usr/bin/env python3
"""
Script de prueba para el endpoint de generación de certificados con Puppeteer
"""

import requests
import json

# URL del endpoint
url = "http://localhost:8080/generar-certificado-medico-puppeteer"

# Datos de prueba
datos_prueba = {
    "nombres_apellidos": "JUAN CARLOS PEREZ GOMEZ",
    "documento_identidad": "1234567890",
    "empresa": "EMPRESA DE PRUEBA",
    "cargo": "Ingeniero de Software",
    "genero": "Masculino",
    "edad": "30",
    "fecha_nacimiento": "15 de enero de 1994",
    "estado_civil": "Soltero",
    "hijos": "0",
    "profesion": "Ingeniero de Sistemas",
    "email": "juan.perez@ejemplo.com",
    "tipo_examen": "Ingreso",
    "concepto_medico": "ELEGIBLE PARA EL CARGO SIN RECOMENDACIONES LABORALES",
    "guardar_drive": False  # No guardar en Drive para prueba
}

print("🧪 Probando endpoint de certificado con Puppeteer...")
print(f"📤 Enviando datos a: {url}")
print(f"📋 Datos: {json.dumps(datos_prueba, indent=2)}")

try:
    response = requests.post(url, json=datos_prueba, timeout=60)

    print(f"\n📊 Status Code: {response.status_code}")

    if response.status_code == 200:
        resultado = response.json()
        print("✅ Certificado generado exitosamente!")
        print(f"📄 PDF URL: {resultado.get('pdf_url')}")
        print(f"🔐 Código de seguridad: {resultado.get('codigo_seguridad')}")
        print(f"💬 Mensaje: {resultado.get('message')}")
    else:
        print(f"❌ Error: {response.text}")

except Exception as e:
    print(f"❌ Error en la prueba: {str(e)}")
