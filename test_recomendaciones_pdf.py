#!/usr/bin/env python3
"""
Script de prueba para verificar que las recomendaciones IA aparecen en el template PDF
"""

from jinja2 import Environment, FileSystemLoader
import os

# Configurar Jinja2
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(loader=FileSystemLoader(template_dir))
template = env.get_template('informe_pdf.html')

# Datos de prueba con recomendaciones IA
recomendaciones_ia_test = {
    'genero': 'Para hombres: Implementar programas de salud que aborden factores de riesgo específicos.\n\nPara mujeres: Establecer políticas de apoyo para la salud reproductiva.',
    'edad': '15-20 años: Implementar programas de concienciación sobre hábitos saludables.\n\n21-30 años: Ofrecer talleres sobre manejo del estrés.'
}

# Datos mínimos para el template
datos_test = {
    'empresa_nombre': 'TEST COMPANY',
    'empresa_nit': '',
    'fecha_inicio_formato': '01 de noviembre de 2025',
    'fecha_fin_formato': '25 de enero de 2026',
    'fecha_elaboracion': '25 de enero de 2026',
    'total_atenciones': 100,
    'total_formularios': 100,
    'total_diagnosticos': 5,
    'logo_base64': '',
    'info_teorica': {},
    'stats': {
        'genero': {'masculino': {'cantidad': 79, 'porcentaje': 79}, 'femenino': {'cantidad': 21, 'porcentaje': 21}},
        'edad': {'rangos': {
            '15-20': {'cantidad': 0, 'porcentaje': 0},
            '21-30': {'cantidad': 86, 'porcentaje': 86},
            '31-40': {'cantidad': 12, 'porcentaje': 12},
            '41-50': {'cantidad': 0, 'porcentaje': 0},
            'mayor50': {'cantidad': 2, 'porcentaje': 2}
        }},
        'estadoCivil': {'estados': {
            'soltero': {'cantidad': 0, 'porcentaje': 0},
            'casado': {'cantidad': 0, 'porcentaje': 0},
            'unionLibre': {'cantidad': 0, 'porcentaje': 0},
            'divorciado': {'cantidad': 0, 'porcentaje': 0},
            'viudo': {'cantidad': 0, 'porcentaje': 0}
        }},
        'nivelEducativo': {'niveles': {
            'primaria': {'cantidad': 0, 'porcentaje': 0},
            'bachillerato': {'cantidad': 0, 'porcentaje': 0},
            'tecnico': {'cantidad': 0, 'porcentaje': 0},
            'profesional': {'cantidad': 0, 'porcentaje': 0},
            'postgrado': {'cantidad': 0, 'porcentaje': 0}
        }},
        'hijos': {'grupos': {
            'sinHijos': {'cantidad': 0, 'porcentaje': 0},
            'unHijo': {'cantidad': 0, 'porcentaje': 0},
            'dosHijos': {'cantidad': 0, 'porcentaje': 0},
            'tresOMas': {'cantidad': 0, 'porcentaje': 0}
        }},
        'ciudadResidencia': [],
        'profesionUOficio': [],
        'encuestaSalud': {},
        'diagnosticos': {'diagnosticos': []},
        'sve': {'resumen': {'visual': 0, 'auditivo': 0, 'controlPeso': 0}, 'pacientes': []}
    },
    'graficos': {},
    'conclusiones_finales': [
        'Primera conclusión de prueba.',
        'Segunda conclusión de prueba.'
    ],
    'medico_firmante': {
        'nombre': 'JUAN JOSE REATIGA',
        'registro': 'C.C.: 7.472.676 - REGISTRO MEDICO NO 14791',
        'licencia': 'LICENCIA SALUD OCUPACIONAL 460'
    },
    'firma_medico_base64': '',
    'recomendaciones_ia': recomendaciones_ia_test
}

print("=" * 80)
print("PRUEBA DE RECOMENDACIONES IA EN TEMPLATE PDF")
print("=" * 80)

print(f"\n📝 Recomendaciones IA de prueba:")
print(f"   - Cantidad: {len(recomendaciones_ia_test)}")
for key, value in recomendaciones_ia_test.items():
    print(f"   - {key}: {len(value)} caracteres")

print(f"\n🎨 Renderizando template...")

try:
    html_rendered = template.render(**datos_test)

    # Guardar HTML de prueba
    output_file = 'test_recomendaciones_output.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_rendered)

    print(f"✅ Template renderizado exitosamente")
    print(f"📄 HTML guardado en: {output_file}")

    # Verificar si las recomendaciones aparecen en el HTML
    if 'Recomendaciones Específicas por Área' in html_rendered:
        print("\n✅ ÉXITO: La sección de recomendaciones IA aparece en el HTML")

        # Contar cuántas recomendaciones se renderizaron
        count_genero = html_rendered.count('Distribución por Género')
        count_edad = html_rendered.count('Distribución por Edad')

        print(f"   - Recomendación de género: {'✅ Presente' if count_genero > 0 else '❌ Ausente'}")
        print(f"   - Recomendación de edad: {'✅ Presente' if count_edad > 0 else '❌ Ausente'}")

        # Buscar el texto de debug
        if 'DEBUG: recomendaciones_ia=' in html_rendered:
            print(f"   - Comentario de debug encontrado")

        # Buscar el contador en el título
        if '2 recomendaciones)' in html_rendered:
            print(f"   - ✅ Contador de recomendaciones correcto: 2 recomendaciones")

    else:
        print("\n❌ ERROR: La sección de recomendaciones IA NO aparece en el HTML")

        # Verificar si aparece el mensaje de debug de "no hay recomendaciones"
        if 'No se generaron recomendaciones de IA' in html_rendered:
            print("   - ⚠️ Se muestra el mensaje de 'No se generaron recomendaciones'")
            print("   - Esto indica que la condición {% if recomendaciones_ia %} falló")

    print(f"\n📖 Para revisar el HTML completo, abre: {output_file}")

except Exception as e:
    print(f"\n❌ ERROR al renderizar template: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
