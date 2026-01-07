#!/usr/bin/env python3
"""
Script para ejecutar la migración del chat de agentes.
Agrega las columnas necesarias a la tabla conversaciones_whatsapp.
"""

import os
import psycopg2

def ejecutar_migracion():
    """Ejecuta el script SQL de migración."""

    # Obtener credenciales de la base de datos
    conn_params = {
        'host': os.environ.get('POSTGRES_HOST'),
        'port': int(os.environ.get('POSTGRES_PORT', 25060)),
        'user': os.environ.get('POSTGRES_USER'),
        'password': os.environ.get('POSTGRES_PASSWORD'),
        'database': os.environ.get('POSTGRES_DB'),
        'sslmode': 'require'
    }

    print("🔌 Conectando a PostgreSQL...")
    print(f"   Host: {conn_params['host']}")
    print(f"   Database: {conn_params['database']}")
    print(f"   User: {conn_params['user']}")

    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        print("✅ Conexión exitosa\n")

        # Leer el script SQL
        with open('sql/add_chat_columns.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()

        print("📝 Ejecutando migración SQL...")
        print("=" * 60)

        # Ejecutar el script completo
        cur.execute(sql_script)
        conn.commit()

        print("✅ Migración ejecutada exitosamente\n")

        # Verificar que las columnas se agregaron
        print("🔍 Verificando columnas agregadas...")
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'conversaciones_whatsapp'
            AND column_name IN ('agente_asignado', 'fecha_asignacion', 'notas')
            ORDER BY column_name;
        """)

        columnas = cur.fetchall()
        if columnas:
            print("✅ Columnas encontradas:")
            for col in columnas:
                print(f"   - {col[0]} ({col[1]})")
        else:
            print("❌ No se encontraron las columnas")

        # Verificar la tabla sistema_asignacion
        print("\n🔍 Verificando tabla sistema_asignacion...")
        cur.execute("SELECT * FROM sistema_asignacion WHERE clave = 'contador_round_robin';")
        sistema = cur.fetchone()

        if sistema:
            print(f"✅ Contador round-robin encontrado: {sistema}")
        else:
            print("❌ No se encontró el contador")

        cur.close()
        conn.close()

        print("\n" + "=" * 60)
        print("✨ ¡Migración completada exitosamente!")
        print("=" * 60)
        print("\n🎉 El chat de agentes ahora debería funcionar correctamente.")
        print("   Puedes probar en: https://bsl-utilidades-yp78a.ondigitalocean.app/twilio-chat")

    except Exception as e:
        print(f"❌ Error ejecutando migración: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise

if __name__ == '__main__':
    ejecutar_migracion()
