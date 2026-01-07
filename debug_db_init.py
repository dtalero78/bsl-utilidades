#!/usr/bin/env python3
"""
Script de diagnóstico para verificar inicialización de tablas de conversaciones WhatsApp
"""
import os
import sys

def debug_db_init():
    print("=" * 70)
    print("DIAGNÓSTICO DE INICIALIZACIÓN DE BASE DE DATOS")
    print("=" * 70)

    # 1. Verificar archivo SQL
    print("\n1. Verificando archivo SQL...")
    sql_path = os.path.join(os.path.dirname(__file__), 'sql', 'init_conversaciones_whatsapp.sql')
    print(f"   Ruta SQL: {sql_path}")

    if os.path.exists(sql_path):
        print(f"   ✅ Archivo SQL encontrado")
        with open(sql_path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"   Tamaño: {len(content)} caracteres")
            print(f"   Contiene CREATE TABLE: {'CREATE TABLE' in content}")
    else:
        print(f"   ❌ Archivo SQL NO encontrado")
        return

    # 2. Verificar variables de entorno
    print("\n2. Verificando variables de entorno PostgreSQL...")
    required_vars = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB']

    all_vars_present = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if 'PASSWORD' in var:
                print(f"   ✅ {var}: ***")
            else:
                print(f"   ✅ {var}: {value}")
        else:
            print(f"   ❌ {var}: NO DEFINIDA")
            all_vars_present = False

    if not all_vars_present:
        print("\n   ⚠️  Faltan variables de entorno. No se puede conectar a PostgreSQL.")
        return

    # 3. Intentar conexión
    print("\n3. Intentando conexión a PostgreSQL...")
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=int(os.getenv("POSTGRES_PORT", "25060")),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            database=os.getenv("POSTGRES_DB"),
            sslmode="require"
        )
        print("   ✅ Conexión exitosa a PostgreSQL")

        # 4. Verificar si las tablas existen
        print("\n4. Verificando tablas existentes...")
        cur = conn.cursor()

        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('conversaciones_whatsapp', 'sistema_asignacion')
        """)

        existing_tables = [row[0] for row in cur.fetchall()]
        print(f"   Tablas encontradas: {existing_tables}")

        if 'conversaciones_whatsapp' not in existing_tables:
            print("   ❌ Tabla 'conversaciones_whatsapp' NO existe")
        else:
            print("   ✅ Tabla 'conversaciones_whatsapp' existe")

        if 'sistema_asignacion' not in existing_tables:
            print("   ❌ Tabla 'sistema_asignacion' NO existe")
        else:
            print("   ✅ Tabla 'sistema_asignacion' existe")

        # 5. Intentar crear tablas si no existen
        if len(existing_tables) < 2:
            print("\n5. Intentando crear tablas faltantes...")
            try:
                with open(sql_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                    cur.execute(sql_script)
                conn.commit()
                print("   ✅ Tablas creadas exitosamente")

                # Verificar de nuevo
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('conversaciones_whatsapp', 'sistema_asignacion')
                """)
                existing_tables = [row[0] for row in cur.fetchall()]
                print(f"   Tablas actuales: {existing_tables}")

            except Exception as e:
                print(f"   ❌ Error creando tablas: {e}")
                import traceback
                traceback.print_exc()

        cur.close()
        conn.close()

    except ImportError:
        print("   ❌ Módulo psycopg2 no instalado")
    except Exception as e:
        print(f"   ❌ Error de conexión: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("FIN DEL DIAGNÓSTICO")
    print("=" * 70)

if __name__ == "__main__":
    debug_db_init()
