-- ============================================================================
-- AGREGAR COLUMNAS PARA SISTEMA DE CHAT DE AGENTES
-- ============================================================================
--
-- Este script agrega las columnas necesarias para el sistema de asignación
-- de conversaciones WhatsApp a agentes SIN modificar las columnas existentes
-- que usa el bot de WhatsApp.
--
-- Columnas agregadas:
-- - agente_asignado: Username del agente (agente1, agente2, etc.)
-- - fecha_asignacion: Fecha de primera asignación
-- - notas: Notas adicionales sobre la conversación
--
-- IMPORTANTE: NO modifica ni elimina ninguna columna existente
--
-- Autor: BSL
-- Fecha: 2026-01-07
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
