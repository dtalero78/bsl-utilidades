-- ============================================================================
-- SCHEMA DE BASE DE DATOS PARA SISTEMA DE ASIGNACIÓN DE CONVERSACIONES
-- ============================================================================
--
-- Este script crea las tablas necesarias para el sistema de asignación
-- automática de conversaciones WhatsApp entre agentes.
--
-- Tablas creadas:
-- - conversaciones_whatsapp: Almacena asignaciones de conversaciones a agentes
-- - sistema_asignacion: Contador para round-robin
--
-- Autor: BSL
-- Fecha: 2026-01-06
-- ============================================================================

-- Tabla de conversaciones WhatsApp con asignación de agentes
CREATE TABLE IF NOT EXISTS conversaciones_whatsapp (
    id SERIAL PRIMARY KEY,
    numero_telefono VARCHAR(20) UNIQUE NOT NULL,
    agente_asignado VARCHAR(50),
    fecha_asignacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_ultima_actividad TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) DEFAULT 'activa',
    notas TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para mejorar rendimiento de búsquedas
CREATE INDEX IF NOT EXISTS idx_numero_telefono ON conversaciones_whatsapp(numero_telefono);
CREATE INDEX IF NOT EXISTS idx_agente_asignado ON conversaciones_whatsapp(agente_asignado);
CREATE INDEX IF NOT EXISTS idx_estado ON conversaciones_whatsapp(estado);

-- Tabla para almacenar el contador round-robin
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

-- Comentarios en las tablas
COMMENT ON TABLE conversaciones_whatsapp IS 'Almacena las asignaciones de conversaciones WhatsApp a agentes';
COMMENT ON COLUMN conversaciones_whatsapp.numero_telefono IS 'Número de teléfono del contacto (con + y código de país)';
COMMENT ON COLUMN conversaciones_whatsapp.agente_asignado IS 'Username del agente asignado (agente1, agente2, etc.)';
COMMENT ON COLUMN conversaciones_whatsapp.fecha_asignacion IS 'Fecha y hora de la primera asignación';
COMMENT ON COLUMN conversaciones_whatsapp.fecha_ultima_actividad IS 'Última vez que se actualizó la conversación';
COMMENT ON COLUMN conversaciones_whatsapp.estado IS 'Estado de la conversación (activa, cerrada, etc.)';

COMMENT ON TABLE sistema_asignacion IS 'Almacena contadores y configuraciones del sistema';
COMMENT ON COLUMN sistema_asignacion.clave IS 'Identificador único de la configuración';
COMMENT ON COLUMN sistema_asignacion.valor IS 'Valor numérico del contador o configuración';
