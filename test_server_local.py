#!/usr/bin/env python3
"""
Servidor de prueba local simplificado para testing de recomendaciones IA en PDF
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from jinja2 import Environment, FileSystemLoader
import os
import tempfile
import base64
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Configurar Jinja2
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
env = Environment(loader=FileSystemLoader(template_dir))

@app.route('/api/generar-pdf-informe', methods=['POST'])
def generar_pdf_informe():
    """Endpoint simplificado para generar PDF con recomendaciones IA"""

    try:
        data = request.get_json()
        cod_empresa = data.get('codEmpresa', 'TEST')
        fecha_inicio = data.get('fechaInicio', '2025-01-01')
        fecha_fin = data.get('fechaFin', '2025-01-31')
        recomendaciones_ia = data.get('recomendacionesIA', {})

        print("=" * 80)
        print(f"📄 Generando PDF para {cod_empresa} ({fecha_inicio} - {fecha_fin})")
        print(f"📝 Recomendaciones IA recibidas: {len(recomendaciones_ia)}")

        if recomendaciones_ia:
            print(f"📝 Tipos de recomendaciones:")
            for key, value in recomendaciones_ia.items():
                print(f"   - {key}: {len(value)} caracteres")
        else:
            print("⚠️ No se recibieron recomendaciones de IA")

        # Cargar el template
        template = env.get_template('informe_pdf.html')

        # Datos mínimos para el template
        datos_template = {
            'empresa_nombre': cod_empresa,
            'empresa_nit': '',
            'fecha_inicio_formato': fecha_inicio,
            'fecha_fin_formato': fecha_fin,
            'fecha_elaboracion': datetime.now().strftime('%d de %B de %Y'),
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
                'Primera conclusión automática de prueba.',
                'Segunda conclusión automática de prueba.',
                'Tercera conclusión automática de prueba.'
            ],
            'medico_firmante': {
                'nombre': 'JUAN JOSE REATIGA',
                'registro': 'C.C.: 7.472.676 - REGISTRO MEDICO NO 14791',
                'licencia': 'LICENCIA SALUD OCUPACIONAL 460'
            },
            'firma_medico_base64': '',
            'recomendaciones_ia': recomendaciones_ia  # ESTO ES LO IMPORTANTE
        }

        print(f"🎨 Renderizando template...")
        print(f"   - recomendaciones_ia type: {type(recomendaciones_ia)}")
        print(f"   - recomendaciones_ia length: {len(recomendaciones_ia)}")
        print(f"   - recomendaciones_ia keys: {list(recomendaciones_ia.keys())}")

        # Renderizar el template
        html_rendered = template.render(**datos_template)

        # Guardar HTML para inspección
        debug_html_path = 'debug_informe_local.html'
        with open(debug_html_path, 'w', encoding='utf-8') as f:
            f.write(html_rendered)

        print(f"✅ Template renderizado exitosamente")
        print(f"📄 HTML guardado en: {debug_html_path}")

        # Verificar si las recomendaciones aparecen
        if 'Recomendaciones Específicas por Área' in html_rendered:
            print("✅ ÉXITO: Sección de recomendaciones IA encontrada en HTML")
            print(f"   - Título contiene: '({len(recomendaciones_ia)} recomendaciones)'")
        elif 'No se generaron recomendaciones de IA' in html_rendered:
            print("⚠️ Mensaje de 'No hay recomendaciones' encontrado")
            print("   - Esto indica que la condición {% if %} no se cumplió")
        else:
            print("❌ No se encontró ninguna sección de recomendaciones")

        # Intentar generar PDF con WeasyPrint
        try:
            from weasyprint import HTML

            pdf_path = 'test_informe_local.pdf'
            HTML(string=html_rendered).write_pdf(pdf_path)

            print(f"✅ PDF generado exitosamente: {pdf_path}")
            print("=" * 80)

            return send_file(pdf_path, as_attachment=True, download_name=f'Informe_{cod_empresa}.pdf')

        except ImportError:
            print("⚠️ WeasyPrint no disponible, devolviendo HTML")
            print("=" * 80)

            # Devolver el HTML directamente para que puedas verlo en el navegador
            return html_rendered, 200, {'Content-Type': 'text/html; charset=utf-8'}

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)

        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/')
def index():
    """Página de prueba simple"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Recomendaciones IA</title>
        <style>
            body { font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; }
            button { padding: 15px 30px; font-size: 16px; cursor: pointer; margin: 10px; }
            .success { background: #28a745; color: white; border: none; border-radius: 5px; }
            pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }
            #output { margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>🧪 Test de Recomendaciones IA en PDF</h1>

        <h2>Test 1: Sin recomendaciones</h2>
        <button class="success" onclick="testSinRecomendaciones()">Generar PDF sin recomendaciones</button>

        <h2>Test 2: Con 2 recomendaciones</h2>
        <button class="success" onclick="testConRecomendaciones()">Generar PDF con 2 recomendaciones (género y edad)</button>

        <h2>Test 3: Con todas las recomendaciones</h2>
        <button class="success" onclick="testTodasRecomendaciones()">Generar PDF con todas las recomendaciones</button>

        <div id="output"></div>

        <script>
            async function testSinRecomendaciones() {
                const output = document.getElementById('output');
                output.innerHTML = '<p>Generando PDF sin recomendaciones...</p>';

                const response = await fetch('/api/generar-pdf-informe', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        codEmpresa: 'TEST',
                        fechaInicio: '2025-01-01',
                        fechaFin: '2025-01-31',
                        recomendacionesIA: {}
                    })
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'test_sin_recomendaciones.pdf';
                    a.click();
                    output.innerHTML = '<p style="color: green;">✅ PDF descargado! Revisa que muestre el mensaje de debug amarillo.</p>';
                } else {
                    output.innerHTML = '<p style="color: red;">❌ Error al generar PDF</p>';
                }
            }

            async function testConRecomendaciones() {
                const output = document.getElementById('output');
                output.innerHTML = '<p>Generando PDF con 2 recomendaciones...</p>';

                const response = await fetch('/api/generar-pdf-informe', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        codEmpresa: 'TEST',
                        fechaInicio: '2025-01-01',
                        fechaFin: '2025-01-31',
                        recomendacionesIA: {
                            genero: 'Para hombres: Implementar programas de salud específicos.\\n\\nPara mujeres: Establecer políticas de apoyo.',
                            edad: '15-20 años: Programas de concienciación.\\n\\n21-30 años: Talleres de manejo del estrés.'
                        }
                    })
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'test_con_recomendaciones.pdf';
                    a.click();
                    output.innerHTML = '<p style="color: green;">✅ PDF descargado! Revisa que muestre las recomendaciones de género y edad con borde verde.</p>';
                } else {
                    output.innerHTML = '<p style="color: red;">❌ Error al generar PDF</p>';
                }
            }

            async function testTodasRecomendaciones() {
                const output = document.getElementById('output');
                output.innerHTML = '<p>Generando PDF con todas las recomendaciones...</p>';

                const response = await fetch('/api/generar-pdf-informe', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        codEmpresa: 'TEST',
                        fechaInicio: '2025-01-01',
                        fechaFin: '2025-01-31',
                        recomendacionesIA: {
                            genero: 'Recomendación de género',
                            edad: 'Recomendación de edad',
                            estadoCivil: 'Recomendación de estado civil',
                            nivelEducativo: 'Recomendación de nivel educativo',
                            hijos: 'Recomendación de hijos',
                            ciudad: 'Recomendación de ciudad',
                            profesion: 'Recomendación de profesión',
                            diagnosticos: 'Recomendación de diagnósticos'
                        }
                    })
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'test_todas_recomendaciones.pdf';
                    a.click();
                    output.innerHTML = '<p style="color: green;">✅ PDF descargado! Revisa que muestre las 8 recomendaciones.</p>';
                } else {
                    output.innerHTML = '<p style="color: red;">❌ Error al generar PDF</p>';
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("=" * 80)
    print("🚀 Servidor de prueba local iniciado")
    print("=" * 80)
    print("📍 Abre en tu navegador: http://127.0.0.1:3000")
    print("=" * 80)
    app.run(debug=True, host='0.0.0.0', port=3000)
