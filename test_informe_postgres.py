#!/usr/bin/env python3
"""
Script de prueba para el endpoint de informes con PostgreSQL
"""

import requests
import json
from datetime import datetime, timedelta

# URL del endpoint local (cambiar si es necesario)
BASE_URL = "http://localhost:8080"

# Parámetros de prueba
cod_empresa = "SIIGO"
fecha_fin = datetime.now().strftime('%Y-%m-%d')
fecha_inicio = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

print(f"🧪 Probando endpoint de informes con PostgreSQL")
print(f"📊 Empresa: {cod_empresa}")
print(f"📅 Período: {fecha_inicio} - {fecha_fin}")
print()

# Hacer la solicitud
url = f"{BASE_URL}/api/informe-condiciones-salud"
params = {
    'codEmpresa': cod_empresa,
    'fechaInicio': fecha_inicio,
    'fechaFin': fecha_fin
}

print(f"🔗 URL: {url}")
print(f"📋 Params: {params}")
print()

try:
    response = requests.get(url, params=params, timeout=60)

    print(f"✅ Status Code: {response.status_code}")
    print()

    if response.status_code == 200:
        data = response.json()

        if data.get('success'):
            print("✅ Respuesta exitosa!")
            print(f"📊 Total Atenciones: {data.get('totalAtenciones', 0)}")
            print(f"📋 Total Formularios: {data.get('totalFormularios', 0)}")
            print()

            # Mostrar estadísticas generales
            stats = data.get('estadisticas', {})

            print("📈 Estadísticas:")
            print(f"  - Género: {stats.get('genero', {})}")
            print(f"  - Edad: {stats.get('edad', {}).get('total', 0)} registros")
            print(f"  - Estado Civil: {stats.get('estadoCivil', {}).get('total', 0)} registros")
            print(f"  - Nivel Educativo: {stats.get('nivelEducativo', {}).get('total', 0)} registros")
            print(f"  - Ciudades: {len(stats.get('ciudadResidencia', {}).get('ciudades', []))} ciudades")
            print(f"  - Profesiones: {len(stats.get('profesionUOficio', {}).get('profesiones', []))} profesiones")
            print(f"  - Encuesta Salud: {len(stats.get('encuestaSalud', {}).get('respuestas', []))} respuestas")
            print(f"  - Diagnósticos: {len(stats.get('diagnosticos', {}).get('diagnosticos', []))} diagnósticos")
            print()

            # Guardar JSON para inspección
            filename = f"informe_{cod_empresa}_{fecha_inicio}_{fecha_fin}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"💾 JSON guardado en: {filename}")
        else:
            print(f"❌ Error en respuesta: {data.get('error', 'Error desconocido')}")
    else:
        print(f"❌ Error HTTP: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
