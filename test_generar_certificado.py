#!/usr/bin/env python3
"""
Script para generar certificado médico desde datos de Wix
ID de la persona: e66c40b4-5a25-4696-b296-c43c754946fd
"""

import requests
import json

# URL del servidor Flask
BASE_URL = "http://127.0.0.1:8080"

# Datos de ejemplo (reemplazar con datos reales de Wix)
# TODO: Obtener estos datos desde la base de datos de Wix
datos_certificado = {
    # ========== DATOS PERSONALES ==========
    "nombres_apellidos": "NOMBRE_COMPLETO_DESDE_WIX",
    "documento_identidad": "DOCUMENTO_DESDE_WIX",
    "cargo": "CARGO_DESDE_WIX",
    "empresa": "EMPRESA_DESDE_WIX",
    "genero": "GENERO_DESDE_WIX",
    "edad": "EDAD_DESDE_WIX",
    "fecha_nacimiento": "FECHA_NAC_DESDE_WIX",
    "estado_civil": "ESTADO_CIVIL_DESDE_WIX",
    "hijos": "HIJOS_DESDE_WIX",
    "profesion": "PROFESION_DESDE_WIX",
    "email": "EMAIL_DESDE_WIX",
    "tipo_examen": "TIPO_EXAMEN_DESDE_WIX",

    # ========== INFORMACIÓN DE LA CONSULTA ==========
    "fecha_atencion": "FECHA_CONSULTA_DESDE_WIX",
    "ciudad": "Bogotá",
    "vigencia": "Tres años",
    "ips_sede": "Sede norte DHSS0244914",

    # ========== FOTO DEL PACIENTE (OPCIONAL) ==========
    # "foto_paciente": "URL_FOTO_DESDE_WIX",

    # ========== EXÁMENES REALIZADOS ==========
    "examenes_realizados": [
        {
            "nombre": "Examen Médico Osteomuscular",
            "fecha": "FECHA_DESDE_WIX"
        },
        {
            "nombre": "Audiometría",
            "fecha": "FECHA_DESDE_WIX"
        },
        {
            "nombre": "Optometría",
            "fecha": "FECHA_DESDE_WIX"
        }
    ],

    # ========== CONCEPTO MÉDICO ==========
    "concepto_medico": "CONCEPTO_DESDE_WIX",

    # ========== RESULTADOS DETALLADOS ==========
    "resultados_generales": [
        {
            "examen": "Examen Médico Osteomuscular",
            "descripcion": "Basándonos en los resultados obtenidos de la evaluación osteomuscular, certificamos que el paciente presenta un sistema osteomuscular en condiciones óptimas de salud."
        },
        {
            "examen": "Audiometría",
            "descripcion": "No presenta signos de pérdida auditiva o alteraciones en la audición. Los resultados se encuentran dentro de los rangos normales."
        },
        {
            "examen": "Optometría",
            "descripcion": "Presión intraocular (PIO): 15 mmHg en ambos ojos. Reflejos pupilares: Normal. Campo visual: Normal."
        }
    ],

    # ========== FIRMAS MÉDICAS ==========
    "medico_nombre": "JUAN JOSE REATIGA",
    "medico_registro": "REGISTRO MEDICO NO 14791",
    "medico_licencia": "LICENCIA SALUD OCUPACIONAL 460",
    "optometra_nombre": "Dr. Miguel Garzón Rincón",
    "optometra_registro": "Optómetra Ocupacional Res. 6473 04/07/2017",

    # ========== OPCIONES DE ALMACENAMIENTO ==========
    "guardar_drive": True,
    "nombre_archivo": "certificado_e66c40b4-5a25-4696-b296-c43c754946fd.pdf"
}

def generar_certificado():
    """Genera el certificado médico llamando al endpoint Flask"""

    print("=" * 80)
    print("🏥 GENERANDO CERTIFICADO MÉDICO")
    print("=" * 80)
    print(f"\n📋 ID Wix: e66c40b4-5a25-4696-b296-c43c754946fd")
    print(f"🔗 Endpoint: {BASE_URL}/generar-certificado-medico")
    print("\n" + "=" * 80)

    # Realizar la petición POST
    try:
        response = requests.post(
            f"{BASE_URL}/generar-certificado-medico",
            headers={"Content-Type": "application/json"},
            json=datos_certificado,
            timeout=30
        )

        print(f"\n📡 Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            if result.get("success"):
                print("\n✅ CERTIFICADO GENERADO EXITOSAMENTE")
                print("=" * 80)
                print(f"🔐 Código de seguridad: {result.get('codigo_seguridad')}")
                print(f"📄 PDF URL: {result.get('pdf_url')}")

                if result.get('drive_web_link'):
                    print(f"☁️  Google Drive: {result.get('drive_web_link')}")
                    print(f"📁 File ID: {result.get('drive_file_id')}")

                print("\n" + "=" * 80)

                # Guardar respuesta completa
                with open('certificado_response.json', 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print("💾 Respuesta guardada en: certificado_response.json")

            else:
                print(f"\n❌ ERROR: {result.get('error')}")
        else:
            print(f"\n❌ ERROR HTTP {response.status_code}")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERROR DE CONEXIÓN: {e}")
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")

if __name__ == "__main__":
    print("\n⚠️  NOTA: Este script usa datos de ejemplo.")
    print("⚠️  Debes reemplazar los valores con los datos reales de Wix.\n")

    # Descomentar la siguiente línea cuando tengas los datos reales
    # generar_certificado()

    print("📝 Para ejecutar:")
    print("   1. Reemplaza los datos de ejemplo con los datos reales de Wix")
    print("   2. Descomenta la línea 'generar_certificado()'")
    print("   3. Ejecuta: python test_generar_certificado.py")
