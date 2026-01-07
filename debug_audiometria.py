#!/usr/bin/env python3
"""
Script para debuggear el registro de audiometría con problema
CC: 1000887289
"""
import os
import psycopg2
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Conectar a PostgreSQL
postgres_password = os.getenv("POSTGRES_PASSWORD")
if not postgres_password:
    print("❌ POSTGRES_PASSWORD no configurada")
    exit(1)

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST", "bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com"),
    port=int(os.getenv("POSTGRES_PORT", "25060")),
    user=os.getenv("POSTGRES_USER", "doadmin"),
    password=postgres_password,
    database=os.getenv("POSTGRES_DB", "defaultdb"),
    sslmode="require"
)

print("✅ Conectado a PostgreSQL")

# Primero buscar el orden_id (wix_id) para esta cédula
cur = conn.cursor()

print("\n🔍 Buscando en HistoriaClinica la cédula 1000887289...")
cur.execute("""
    SELECT _id, "numeroId", "primerNombre", "primerApellido", "mdObservacionesCertificado"
    FROM "HistoriaClinica"
    WHERE "numeroId" = '1000887289'
    LIMIT 1;
""")

historia = cur.fetchone()
if historia:
    orden_id = historia[0]
    print(f"✅ Encontrado en HistoriaClinica:")
    print(f"   orden_id: {orden_id}")
    print(f"   numeroId: {historia[1]}")
    print(f"   nombre: {historia[2]} {historia[3]}")
    print(f"   mdObservacionesCertificado: {historia[4][:100] if historia[4] else 'None'}...")

    # Ahora buscar en audiometrias
    print(f"\n🔍 Buscando en audiometrias con orden_id: {orden_id}")

    # Obtener primero los nombres de las columnas
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'audiometrias'
        ORDER BY ordinal_position;
    """)

    columnas = cur.fetchall()
    print(f"\n📋 Columnas en tabla audiometrias:")
    for col in columnas:
        print(f"   - {col[0]} ({col[1]})")

    # Consultar el registro completo
    cur.execute("""
        SELECT *
        FROM audiometrias
        WHERE orden_id = %s
        LIMIT 1;
    """, (orden_id,))

    row = cur.fetchone()
    if row:
        print(f"\n✅ Registro encontrado en audiometrias:")
        col_names = [desc[0] for desc in cur.description]
        for i, col_name in enumerate(col_names):
            valor = row[i]
            if valor and len(str(valor)) > 100:
                print(f"   {col_name}: {str(valor)[:100]}...")
            else:
                print(f"   {col_name}: {valor}")
    else:
        print(f"❌ No se encontró registro en audiometrias para orden_id: {orden_id}")
else:
    print("❌ No se encontró la cédula 1000887289 en HistoriaClinica")

cur.close()
conn.close()
