# Instrucciones para Habilitar el Chat de Agentes WhatsApp

## Problema Identificado

El sistema de chat de agentes no está cargando conversaciones porque **faltan columnas en la base de datos**. La tabla `conversaciones_whatsapp` existe pero solo tiene las columnas del bot de WhatsApp. Necesitamos agregar las columnas para el sistema de asignación de agentes.

## Solución

Ejecutar el script SQL `sql/add_chat_columns.sql` que agrega las columnas necesarias **sin modificar ni eliminar** ninguna columna existente del bot.

## Pasos para Ejecutar en Producción

### Opción 1: Desde psql (Recomendado)

```bash
# 1. Conectarse a la base de datos de producción
psql -h <POSTGRES_HOST> -p 25060 -U <POSTGRES_USER> -d <POSTGRES_DB>

# 2. Ejecutar el script
\i sql/add_chat_columns.sql

# 3. Verificar que las columnas se agregaron
\d conversaciones_whatsapp

# 4. Verificar que el contador existe
SELECT * FROM sistema_asignacion WHERE clave = 'contador_round_robin';
```

### Opción 2: Desde DBeaver / pgAdmin

1. Abrir [sql/add_chat_columns.sql](sql/add_chat_columns.sql)
2. Copiar todo el contenido
3. Conectarse a la base de datos de producción
4. Pegar y ejecutar el script completo
5. Verificar con:
   ```sql
   SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name = 'conversaciones_whatsapp'
   AND column_name IN ('agente_asignado', 'fecha_asignacion', 'notas');
   ```

### Opción 3: Copiar y Pegar Directamente

Si no tienes acceso directo a la base de datos, copia y pega el siguiente script SQL:

```sql
-- Agregar columnas para el chat de agentes
ALTER TABLE conversaciones_whatsapp
ADD COLUMN IF NOT EXISTS agente_asignado VARCHAR(50),
ADD COLUMN IF NOT EXISTS fecha_asignacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS notas TEXT;

-- Crear índice para búsquedas por agente
CREATE INDEX IF NOT EXISTS idx_agente_asignado ON conversaciones_whatsapp(agente_asignado);

-- Crear tabla del contador round-robin
CREATE TABLE IF NOT EXISTS sistema_asignacion (
    id SERIAL PRIMARY KEY,
    clave VARCHAR(50) UNIQUE NOT NULL,
    valor INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insertar contador inicial
INSERT INTO sistema_asignacion (clave, valor)
VALUES ('contador_round_robin', 0)
ON CONFLICT (clave) DO NOTHING;
```

## Verificación Post-Migración

Después de ejecutar el script, verifica que todo funciona:

### 1. Verificar columnas agregadas

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'conversaciones_whatsapp'
ORDER BY ordinal_position;
```

**Deberías ver:**
- ✅ `agente_asignado` - character varying
- ✅ `fecha_asignacion` - timestamp without time zone
- ✅ `notas` - text

### 2. Verificar tabla de sistema

```sql
SELECT * FROM sistema_asignacion;
```

**Deberías ver:**
```
 id |         clave          | valor |         updated_at
----+------------------------+-------+----------------------------
  1 | contador_round_robin   |     0 | 2026-01-07 XX:XX:XX
```

### 3. Verificar el chat en producción

1. Ir a: https://bsl-utilidades-yp78a.ondigitalocean.app/twilio-chat/login
2. Login con: `agente1` / `pipe`
3. Verificar que la página carga correctamente
4. Enviar un mensaje de prueba desde WhatsApp al número **+57 300 802 1701**
5. La conversación debería aparecer automáticamente asignada a `agente1` o `agente2`

## Cambios Realizados en el Código

### Archivo: `chat_whatsapp.py`

Se actualizaron todas las referencias de `numero_telefono` a `celular` para usar la columna existente de la tabla:

- ✅ Función `obtener_agente_asignado()`: Usa `WHERE celular = %s`
- ✅ Función `asignar_conversacion_round_robin()`: Inserta con `celular` y `ON CONFLICT (celular)`
- ✅ Función `actualizar_actividad_conversacion()`: Actualiza con `WHERE celular = %s`
- ✅ Función `obtener_conversaciones_por_agente()`: Selecciona `SELECT celular`

### Archivo: `sql/add_chat_columns.sql` (NUEVO)

Script SQL seguro que:
- ✅ Agrega columnas solo si NO existen (`ADD COLUMN IF NOT EXISTS`)
- ✅ Crea índice solo si NO existe (`CREATE INDEX IF NOT EXISTS`)
- ✅ Crea tabla solo si NO existe (`CREATE TABLE IF NOT EXISTS`)
- ✅ No modifica ni elimina ninguna columna existente

## Rollback (En caso de emergencia)

Si algo sale mal, puedes revertir los cambios:

```sql
-- SOLO si es absolutamente necesario
ALTER TABLE conversaciones_whatsapp
DROP COLUMN IF EXISTS agente_asignado,
DROP COLUMN IF EXISTS fecha_asignacion,
DROP COLUMN IF EXISTS notas;

DROP INDEX IF EXISTS idx_agente_asignado;
DROP TABLE IF EXISTS sistema_asignacion;
```

**⚠️ ADVERTENCIA:** El rollback eliminará todas las asignaciones de agentes. Solo úsalo si el sistema no funciona en absoluto.

## Contacto

Si tienes problemas ejecutando el script, contacta al equipo de desarrollo.

---

**Fecha:** 2026-01-07
**Autor:** Claude Code + Daniel Talero
