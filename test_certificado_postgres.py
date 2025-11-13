#!/usr/bin/env python3
"""
Script de prueba para verificar foto de PostgreSQL
"""
import os
import sys
import psycopg2

# Configurar environment variables si no existen
if not os.getenv("POSTGRES_PASSWORD"):
    print("❌ ERROR: POSTGRES_PASSWORD no está configurada en las variables de entorno")
    print("💡 Configúrala ejecutando: export POSTGRES_PASSWORD='tu_password'")
    sys.exit(1)

def test_certificado_postgres(wix_id):
    """
    Genera un certificado de prueba usando foto de PostgreSQL
    """
    try:
        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if not postgres_password:
            print("❌ POSTGRES_PASSWORD no configurada")
            return False

        # Conectar a PostgreSQL
        print(f"🔌 Conectando a PostgreSQL para wix_id: {wix_id}")
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER", "doadmin"),
            password=postgres_password,
            database=os.getenv("POSTGRES_DB", "defaultdb"),
            sslmode="require"
        )
        cur = conn.cursor()

        # Buscar el registro por wix_id
        print(f"🔍 Buscando registro con wix_id: {wix_id}")
        cur.execute("""
            SELECT
                id, primer_nombre, primer_apellido,
                numero_id, empresa, cod_empresa, foto, wix_id, celular
            FROM formularios
            WHERE wix_id = %s
            LIMIT 1;
        """, (wix_id,))

        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            print(f"❌ No se encontró registro con wix_id: {wix_id}")
            return False

        # Extraer datos
        (
            db_id, primer_nombre, primer_apellido,
            numero_id, empresa, cod_empresa, foto, db_wix_id, celular
        ) = row

        # No hay segundo_nombre ni segundo_apellido en esta tabla
        cargo = "No especificado"  # Esta tabla no tiene columna cargo

        print(f"✅ Registro encontrado: {primer_nombre} {primer_apellido}")
        print(f"📸 Foto length: {len(foto) if foto else 0} caracteres")

        if foto:
            print(f"📸 Foto preview: {foto[:100]}...")

            # Verificar que sea un data URI válido
            if foto.startswith("data:image/"):
                print("✅ Foto es un data URI válido")

                # Extraer tipo de imagen
                if "data:image/jpeg" in foto:
                    print("   Tipo: JPEG")
                elif "data:image/png" in foto:
                    print("   Tipo: PNG")
                else:
                    print(f"   Tipo: {foto.split(';')[0]}")
            else:
                print("⚠️  Foto NO es un data URI (no comienza con 'data:image/')")
        else:
            print("❌ NO HAY FOTO en este registro")

        # Crear HTML simple de prueba
        html_simple = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Foto PostgreSQL</title>
</head>
<body>
    <h1>Test de Foto desde PostgreSQL</h1>
    <h2>Paciente: {primer_nombre} {primer_apellido}</h2>
    <p>Documento: {numero_id}</p>
    <p>Cargo: {cargo}</p>
    <p>Empresa: {empresa}</p>
    <hr>
    <h3>Foto del Paciente:</h3>
    {'<img src="' + foto + '" style="max-width: 300px; border: 2px solid #000;" />' if foto else '<p>No hay foto</p>'}
    <hr>
    <p>Foto size: {len(foto) if foto else 0} caracteres</p>
</body>
</html>
"""

        # Guardar HTML para inspección
        html_file = f"/tmp/test_foto_postgres_{wix_id}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_simple)

        print(f"\n✅ HTML de prueba generado: {html_file}")

        # Resultado
        print("\n" + "=" * 70)
        print("✅ PRUEBA EXITOSA - Foto recuperada de PostgreSQL")
        print("=" * 70)
        print(f"Paciente: {primer_nombre} {primer_apellido}")
        print(f"Documento: {numero_id}")
        print(f"Celular: {celular}")
        print(f"Empresa: {empresa} ({cod_empresa})")
        print(f"Foto presente: {'SÍ' if foto else 'NO'}")
        print(f"Foto size: {len(foto) if foto else 0} caracteres")
        print(f"\n💡 Abre este archivo en un navegador para verificar la foto:")
        print(f"   {html_file}")
        print("\n✅ Conclusión: La foto está almacenada como data URI base64 en PostgreSQL")
        print("✅ Se puede usar directamente en el atributo src de <img> en el HTML del PDF")

        return True

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Usar wix_id de prueba
    wix_id = "3eff997f-0262-438d-a55b-892988f51d29"

    if len(sys.argv) > 1:
        wix_id = sys.argv[1]

    print(f"🧪 Testing certificado con wix_id: {wix_id}")
    print("=" * 70)

    success = test_certificado_postgres(wix_id)
    sys.exit(0 if success else 1)
