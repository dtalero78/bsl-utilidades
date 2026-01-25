#!/usr/bin/env python3
import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from jinja2 import Template

    # Leer el template de prueba
    with open('test_simple_jinja.html', 'r') as f:
        template_content = f.read()

    template = Template(template_content)

    # Test 1: Con recomendaciones (diccionario vacío)
    print("=" * 80)
    print("TEST 1: recomendaciones_ia = {} (diccionario vacío)")
    print("=" * 80)
    html1 = template.render(recomendaciones_ia={})
    with open('test_output_vacio.html', 'w') as f:
        f.write(html1)

    if 'No hay recomendaciones IA' in html1:
        print("✅ Diccionario vacío detectado correctamente")
    else:
        print("❌ Diccionario vacío NO detectado (esto es un problema)")

    # Test 2: Con recomendaciones reales
    print("\n" + "=" * 80)
    print("TEST 2: recomendaciones_ia con 2 elementos")
    print("=" * 80)
    recomendaciones_test = {
        'genero': 'Recomendación de género',
        'edad': 'Recomendación de edad'
    }
    html2 = template.render(recomendaciones_ia=recomendaciones_test)
    with open('test_output_con_datos.html', 'w') as f:
        f.write(html2)

    if 'ÉXITO: Recomendaciones IA detectadas' in html2:
        print("✅ Recomendaciones detectadas correctamente")
        if 'Recomendación de género' in html2:
            print("✅ Recomendación de género presente")
        if 'Recomendación de edad' in html2:
            print("✅ Recomendación de edad presente")
    else:
        print("❌ Recomendaciones NO detectadas")

    # Test 3: Sin recomendaciones (None)
    print("\n" + "=" * 80)
    print("TEST 3: recomendaciones_ia = None")
    print("=" * 80)
    html3 = template.render(recomendaciones_ia=None)
    with open('test_output_none.html', 'w') as f:
        f.write(html3)

    if 'No hay recomendaciones IA' in html3:
        print("✅ None detectado correctamente")
    else:
        print("❌ None NO detectado")

    print("\n" + "=" * 80)
    print("Archivos generados:")
    print("  - test_output_vacio.html")
    print("  - test_output_con_datos.html")
    print("  - test_output_none.html")
    print("=" * 80)

except ImportError as e:
    print(f"❌ Error: jinja2 no está instalado")
    print(f"   {e}")
    print("\nInstala con: pip install jinja2")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
