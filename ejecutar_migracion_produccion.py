#!/usr/bin/env python3
"""
Script para ejecutar la migración del chat de agentes EN PRODUCCIÓN.
Este script debe ejecutarse en el servidor de DigitalOcean donde están las variables de entorno.

USO:
    python3 ejecutar_migracion_produccion.py
"""

import os
import sys

# Verificar que estamos en producción (que las variables existen)
if not os.environ.get('POSTGRES_HOST'):
    print("❌ ERROR: Variables de entorno no encontradas")
    print("   Este script debe ejecutarse en el servidor de producción")
    print("   o con las variables de entorno cargadas.")
    print("\n💡 Alternativa: Ejecuta el SQL manualmente:")
    print("   psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -f sql/add_chat_columns.sql")
    sys.exit(1)

import psycopg2

def ejecutar_migracion():
    """Ejecuta el script SQL de migración."""

    # SQL a ejecutar
    sql_script = """
-- ============================================================================
-- AGREGAR COLUMNAS PARA SISTEMA DE CHAT DE AGENTES
-- ============================================================================

-- Agregar columnas necesarias para el chat de agentes
ALTER TABLE conversaciones_whatsapp
ADD COLUMN IF NOT EXISTS agente_asignado VARCHAR(50),
ADD COLUMN IF NOT EXISTS fecha_asignacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS notas TEXT;

-- Crear índice para mejorar rendimiento de búsquedas por agente
CREATE INDEX IF NOT EXISTS idx_agente_asignado ON conversaciones_whatsapp(agente_asignado);

-- Crear tabla para el contador round-robin (si no existe)
CREATE TABLE IF NOT EXISTS sistema_asignacion (
    id SERIAL PRIMARY KEY,
    clave VARCHAR(50) UNIQUE NOT NULL,
    valor INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insertar contador inicial para round-robin
INSERT INTO sistema_asignacion (clave, valor)
VALUES ('contador_round_robin', 0)
ON CONFLICT (clave) DO NOTHING;

-- Comentarios en las nuevas columnas
COMMENT ON COLUMN conversaciones_whatsapp.agente_asignado IS 'Username del agente asignado (agente1, agente2, etc.)';
COMMENT ON COLUMN conversaciones_whatsapp.fecha_asignacion IS 'Fecha y hora de la primera asignación al agente';
COMMENT ON COLUMN conversaciones_whatsapp.notas IS 'Notas adicionales del agente sobre la conversación';
"""

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
            print(f"✅ Contador round-robin encontrado: valor = {sistema[2]}")
        else:
            print("❌ No se encontró el contador")

        cur.close()
        conn.close()

        print("\n" + "=" * 60)
        print("✨ ¡Migración completada exitosamente!")
        print("=" * 60)
        print("\n🎉 El chat de agentes ahora debería funcionar correctamente.")
        print("   Puedes probar en: https://bsl-utilidades-yp78a.ondigitalocean.app/twilio-chat")

        return True

    except Exception as e:
        print(f"❌ Error ejecutando migración: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False

if __name__ == '__main__':
    success = ejecutar_migracion()
    sys.exit(0 if success else 1)
