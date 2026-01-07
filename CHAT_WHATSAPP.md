# Sistema de Chat WhatsApp con Asignación de Agentes

## Descripción General

Sistema de chat WhatsApp integrado con Flask que permite a dos agentes gestionar conversaciones de manera simultánea con asignación automática round-robin. Cada agente solo ve las conversaciones que le fueron asignadas.

## Características Principales

- ✅ **Autenticación simple** con usuario/contraseña
- ✅ **Asignación automática round-robin** de conversaciones nuevas
- ✅ **Filtrado por agente** - cada agente solo ve sus conversaciones
- ✅ **Integración con Whapi** (línea 3008021701)
- ✅ **WebSockets en tiempo real** con Socket.IO
- ✅ **Interfaz WhatsApp-style** responsive
- ✅ **Persistencia en PostgreSQL**

## Arquitectura

### Separación de Código

El chat está completamente separado del código de certificados médicos usando Flask Blueprints:

```
bsl-utilidades/
├── chat_whatsapp.py              # Módulo independiente del chat (1223 líneas)
├── descargar_bsl.py              # Aplicación principal (registra el Blueprint)
├── sql/
│   └── init_conversaciones_whatsapp.sql  # Schema de base de datos
├── templates/twilio/
│   ├── login.html                # Página de login
│   └── chat.html                 # Interfaz principal del chat
└── static/twilio/
    ├── css/chat.css              # Estilos
    └── js/chat.js                # Lógica del frontend
```

### Tecnologías

- **Backend**: Flask + Flask-SocketIO
- **Base de datos**: PostgreSQL
- **API WhatsApp**: Whapi.cloud
- **Frontend**: HTML5 + CSS3 + JavaScript vanilla
- **WebSockets**: Socket.IO 4.7.2

## Base de Datos

### Tabla `conversaciones_whatsapp`

```sql
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
```

**Índices:**
- `idx_numero_telefono`: Búsqueda rápida por número
- `idx_agente_asignado`: Filtrado eficiente por agente
- `idx_estado`: Filtrado por estado de conversación

### Tabla `sistema_asignacion`

```sql
CREATE TABLE IF NOT EXISTS sistema_asignacion (
    id SERIAL PRIMARY KEY,
    clave VARCHAR(50) UNIQUE NOT NULL,
    valor INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Registro inicial:**
```sql
INSERT INTO sistema_asignacion (clave, valor)
VALUES ('contador_round_robin', 0)
ON CONFLICT (clave) DO NOTHING;
```

## Configuración

### Variables de Entorno

```bash
# Autenticación Flask
FLASK_SECRET_KEY=<token-seguro-64-chars>

# Credenciales de agentes
PASSWORD_AGENTE1=<password-segura>
PASSWORD_AGENTE2=<password-segura>

# PostgreSQL
POSTGRES_HOST=<host>
POSTGRES_PORT=25060
POSTGRES_USER=<usuario>
POSTGRES_PASSWORD=<password>
POSTGRES_DB=<database>

# Whapi API
WHAPI_TOKEN=<token-whapi>

# Twilio (opcional - solo si se usa Twilio)
TWILIO_ACCOUNT_SID=<sid>
TWILIO_AUTH_TOKEN=<token>
TWILIO_WHATSAPP_NUMBER=whatsapp:+573153369631
```

### Agentes Configurados

```python
AGENTES = {
    'agente1': {
        'password': os.getenv('PASSWORD_AGENTE1', 'password1'),
        'nombre': 'Agente 1',
        'activo': True
    },
    'agente2': {
        'password': os.getenv('PASSWORD_AGENTE2', 'password2'),
        'nombre': 'Agente 2',
        'activo': True
    }
}
```

## Flujo de Asignación Round-Robin

### 1. Mensaje Entrante Nuevo

```python
# webhook recibe mensaje de número no asignado
numero_telefono = '+573001234567'

# Verificar si ya tiene agente asignado
agente = obtener_agente_asignado(numero_telefono)

if not agente:
    # Primera vez - Asignar con round-robin
    agente = asignar_conversacion_round_robin(numero_telefono)
    # Resultado: agente1 (si contador = 0)
else:
    # Conversación existente - Solo actualizar actividad
    actualizar_actividad_conversacion(numero_telefono)
```

### 2. Algoritmo Round-Robin

```python
def asignar_conversacion_round_robin(numero_telefono):
    # 1. Obtener y bloquear contador (evitar race conditions)
    cur.execute("SELECT valor FROM sistema_asignacion
                 WHERE clave = 'contador_round_robin'
                 FOR UPDATE")
    contador = cur.fetchone()[0]  # Ejemplo: 0

    # 2. Seleccionar agente usando módulo
    agentes_activos = ['agente1', 'agente2']
    agente = agentes_activos[contador % 2]  # 0 % 2 = 0 → agente1

    # 3. Incrementar contador
    cur.execute("UPDATE sistema_asignacion
                 SET valor = %s
                 WHERE clave = 'contador_round_robin'", (1,))

    # 4. Guardar asignación
    cur.execute("""
        INSERT INTO conversaciones_whatsapp (numero_telefono, agente_asignado)
        VALUES (%s, %s)
        ON CONFLICT (numero_telefono) DO UPDATE
        SET agente_asignado = EXCLUDED.agente_asignado
    """, (numero_telefono, agente))

    return agente  # 'agente1'
```

### 3. Secuencia de Asignaciones

```
Conversación 1: +573001234567 → contador=0 → agente1 (0 % 2 = 0) → contador=1
Conversación 2: +573007654321 → contador=1 → agente2 (1 % 2 = 1) → contador=2
Conversación 3: +573009876543 → contador=2 → agente1 (2 % 2 = 0) → contador=3
Conversación 4: +573005555555 → contador=3 → agente2 (3 % 2 = 1) → contador=4
```

## Endpoints API

### Autenticación

#### `GET /twilio-chat/login`
Renderiza la página de login.

**Respuesta:** HTML de login.html

---

#### `POST /twilio-chat/api/login`
Autentica un agente.

**Request:**
```json
{
  "username": "agente1",
  "password": "password1"
}
```

**Response exitoso:**
```json
{
  "success": true,
  "username": "agente1",
  "nombre": "Agente 1"
}
```

**Response fallido:**
```json
{
  "success": false,
  "error": "Credenciales inválidas"
}
```

---

#### `POST /twilio-chat/api/logout`
Cierra sesión del agente.

**Response:**
```json
{
  "success": true
}
```

---

#### `GET /twilio-chat/api/session`
Verifica sesión activa.

**Response (autenticado):**
```json
{
  "logged_in": true,
  "username": "agente1",
  "nombre": "Agente 1"
}
```

**Response (no autenticado):**
```json
{
  "logged_in": false
}
```
*Status: 401*

---

### Chat

#### `GET /twilio-chat`
Interfaz principal del chat (requiere autenticación).

**Respuesta:** HTML de chat.html

---

#### `GET /twilio-chat/api/conversaciones`
Obtiene conversaciones asignadas al agente autenticado.

**Query params:**
- `limit` (default: 30): Número de conversaciones por página
- `offset` (default: 0): Offset para paginación

**Response:**
```json
{
  "success": true,
  "conversaciones": {
    "573001234567": {
      "numero": "573001234567",
      "nombre": "Juan Pérez",
      "last_message": "Hola, necesito información",
      "last_message_time": "2026-01-07T10:30:00",
      "source": "whapi",
      "profile_picture": "https://...",
      "message_count": 5
    }
  },
  "total": 10,
  "count": 1,
  "offset": 0,
  "limit": 30,
  "has_more": true,
  "agente": "agente1"
}
```

---

#### `GET /twilio-chat/api/conversacion/<numero>`
Obtiene mensajes de una conversación específica.

**Path params:**
- `numero`: Número de teléfono (sin +)

**Query params:**
- `limit` (default: 50): Mensajes por página
- `offset` (default: 0): Offset para paginación

**Response:**
```json
{
  "success": true,
  "numero": "573001234567",
  "twilio_messages": [
    {
      "id": "msg_abc123",
      "chat_id": "573001234567",
      "from": "573001234567",
      "to": "573008021701",
      "body": "Hola, necesito información",
      "date_sent": "2026-01-07T10:30:00",
      "status": "delivered",
      "direction": "inbound",
      "media_count": 0,
      "source": "whapi"
    }
  ],
  "total": 25,
  "count": 25,
  "offset": 0,
  "limit": 50,
  "has_more": false,
  "source": "whapi"
}
```

---

#### `POST /twilio-chat/api/enviar-mensaje`
Envía un mensaje WhatsApp.

**Request:**
```json
{
  "to": "573001234567",
  "message": "Hola, ¿en qué puedo ayudarte?",
  "media_url": null
}
```

**Response exitoso:**
```json
{
  "success": true,
  "message_id": "msg_xyz789",
  "source": "whapi",
  "timestamp": "2026-01-07T10:35:00"
}
```

**Response sin permisos:**
```json
{
  "success": false,
  "error": "No tienes permiso para enviar mensajes a esta conversación"
}
```
*Status: 403*

---

### Webhooks

#### `POST /twilio-chat/webhook/whapi`
Recibe mensajes entrantes de Whapi y asigna conversaciones automáticamente.

**Request de Whapi:**
```json
{
  "messages": [
    {
      "id": "msg_abc123",
      "chat_id": "573001234567@s.whatsapp.net",
      "from": "573001234567@s.whatsapp.net",
      "type": "text",
      "text": {
        "body": "Hola"
      },
      "timestamp": 1704624000,
      "from_me": false
    }
  ]
}
```

**Lógica:**
1. Extrae número del `chat_id`
2. Verifica si tiene agente asignado
3. Si no tiene: asigna con round-robin
4. Si tiene: actualiza última actividad
5. Emite evento WebSocket a todos los clientes

**Response:**
```json
{
  "success": true
}
```

## WebSocket Events

### Namespace: `/twilio-chat`

#### Cliente → Servidor

**`connect`**
Cliente se conecta al socket.

**Response automático:**
```json
{
  "event": "connection_status",
  "data": {
    "status": "connected",
    "timestamp": "2026-01-07T10:30:00"
  }
}
```

---

**`join_conversation`**
Cliente se une a una conversación específica.

**Payload:**
```json
{
  "numero": "573001234567"
}
```

**Response:**
```json
{
  "event": "joined_conversation",
  "data": {
    "numero": "573001234567",
    "timestamp": "2026-01-07T10:30:00"
  }
}
```

---

#### Servidor → Cliente

**`new_message`**
Notifica un nuevo mensaje (entrante o saliente).

**Payload:**
```json
{
  "numero": "573001234567",
  "from": "573001234567",
  "to": "573008021701",
  "body": "Hola",
  "message_id": "msg_abc123",
  "chat_id": "573001234567@s.whatsapp.net",
  "type": "text",
  "timestamp": "2026-01-07T10:30:00",
  "direction": "inbound",
  "source": "whapi"
}
```

---

**`message_status`**
Actualización de estado de mensaje (entregado, leído, etc).

**Payload:**
```json
{
  "message_id": "msg_abc123",
  "numero": "573001234567",
  "status": "read",
  "status_code": 4,
  "timestamp": "2026-01-07T10:31:00",
  "source": "whapi"
}
```

---

**`conversation_update`**
Actualización general de conversación.

**Payload:**
```json
{
  "numero": "573001234567",
  "last_read_timestamp": "2026-01-07T10:31:00",
  "event_type": "message_read",
  "source": "whapi"
}
```

## Frontend

### Flujo de Autenticación

```javascript
// 1. Página se carga → verificar sesión
const sessionCheck = await verificarSesion();

if (!sessionCheck.logged_in) {
    // Redirigir a login
    window.location.href = '/twilio-chat/login';
    return;
}

// 2. Mostrar nombre del agente en header
mostrarInfoAgente(sessionCheck.nombre);

// 3. Inicializar WebSocket y cargar conversaciones
inicializarSocketIO();
cargarConversaciones();
```

### Componentes Principales

#### Login (login.html)
- Formulario con username/password
- Validación en tiempo real
- Loading state con spinner
- Error messages animados
- Diseño WhatsApp-style con gradiente verde

#### Chat (chat.html)
- **Sidebar**: Lista de conversaciones con búsqueda
- **Chat area**: Mensajes con scroll automático
- **Input area**: Textarea con botón de envío
- **Header**: Info del agente + logout

#### JavaScript (chat.js)

**Funciones clave:**
```javascript
// Verificar sesión
async function verificarSesion()

// Cargar lista de conversaciones
async function cargarConversaciones()

// Cargar mensajes de una conversación
async function cargarConversacion(numero)

// Enviar mensaje
async function enviarMensaje()

// Cerrar sesión
async function cerrarSesion()

// Socket.IO handlers
socket.on('new_message', handleNuevoMensaje)
socket.on('message_status', handleStatusUpdate)
```

## Seguridad

### Autenticación
- Session-based con `flask.session`
- Secret key configurable via env (`FLASK_SECRET_KEY`)
- Passwords hasheadas en variables de entorno
- Decorator `@require_auth` en todos los endpoints protegidos

### Control de Acceso
- Agente solo puede ver conversaciones asignadas a él
- Verificación de permisos antes de:
  - Ver mensajes de conversación
  - Enviar mensajes
  - Acceder a endpoints del chat

### Base de Datos
- Row-level locking en asignaciones (`FOR UPDATE`)
- Prevención de race conditions en round-robin
- Conexiones SSL a PostgreSQL (`sslmode=require`)

### CORS
- Solo acepta requests del dominio configurado
- Webhooks públicos pero con validación de payload

## Mantenimiento

### Agregar un Nuevo Agente

1. **Actualizar configuración en `chat_whatsapp.py`:**
```python
AGENTES = {
    'agente1': {...},
    'agente2': {...},
    'agente3': {  # NUEVO
        'password': os.getenv('PASSWORD_AGENTE3', 'password3'),
        'nombre': 'Agente 3',
        'activo': True
    }
}
```

2. **Agregar variable de entorno:**
```bash
PASSWORD_AGENTE3=<password-segura>
```

3. **El round-robin automáticamente incluirá al nuevo agente**
   - Distribución se ajusta de 2 a 3 agentes automáticamente
   - `contador % 3` en lugar de `contador % 2`

### Desactivar un Agente Temporalmente

```python
AGENTES = {
    'agente1': {
        'password': os.getenv('PASSWORD_AGENTE1'),
        'nombre': 'Agente 1',
        'activo': True
    },
    'agente2': {
        'password': os.getenv('PASSWORD_AGENTE2'),
        'nombre': 'Agente 2',
        'activo': False  # DESACTIVADO
    }
}
```

El agente desactivado:
- No puede hacer login
- No recibe conversaciones nuevas
- Mantiene conversaciones ya asignadas

### Logs

**Eventos importantes logeados:**
- ✅ Login exitoso/fallido
- 📱 Asignación de conversaciones nuevas
- 📝 Actualización de actividad
- 📡 Eventos WebSocket enviados
- ❌ Errores de permisos
- 🔔 Mensajes enviados/recibidos

**Formato de logs:**
```
INFO:chat_whatsapp:✅ Login exitoso: agente1
INFO:chat_whatsapp:🆕 Nueva conversación +573001234567 → agente1
INFO:chat_whatsapp:📝 Conversación existente +573007654321 → agente2
INFO:chat_whatsapp:📡 Evento WebSocket enviado: new_message
WARNING:chat_whatsapp:⚠️ Agente agente1 intentó acceder a conversación de agente2
```

## Monitoreo

### Health Check

```bash
curl https://bsl-utilidades.ondigitalocean.app/twilio-chat/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "twilio-bsl",
  "timestamp": "2026-01-07T10:30:00",
  "twilio_configured": false
}
```

### Métricas Clave

**Base de datos:**
```sql
-- Total de conversaciones activas
SELECT COUNT(*) FROM conversaciones_whatsapp WHERE estado = 'activa';

-- Conversaciones por agente
SELECT agente_asignado, COUNT(*)
FROM conversaciones_whatsapp
WHERE estado = 'activa'
GROUP BY agente_asignado;

-- Valor actual del contador round-robin
SELECT valor FROM sistema_asignacion WHERE clave = 'contador_round_robin';

-- Conversaciones más antiguas sin actividad
SELECT numero_telefono, agente_asignado, fecha_ultima_actividad
FROM conversaciones_whatsapp
WHERE estado = 'activa'
ORDER BY fecha_ultima_actividad ASC
LIMIT 10;
```

## Troubleshooting

### Error: "No tienes permiso para ver esta conversación"

**Causa:** El agente intenta acceder a una conversación asignada a otro agente.

**Solución:**
1. Verificar en BD a quién está asignada:
```sql
SELECT agente_asignado FROM conversaciones_whatsapp
WHERE numero_telefono = '+573001234567';
```
2. Si es incorrecto, reasignar manualmente (opcional):
```sql
UPDATE conversaciones_whatsapp
SET agente_asignado = 'agente1'
WHERE numero_telefono = '+573001234567';
```

---

### Error: "Credenciales inválidas"

**Causa:** Username o password incorrectos.

**Solución:**
1. Verificar variables de entorno:
```bash
echo $PASSWORD_AGENTE1
echo $PASSWORD_AGENTE2
```
2. Verificar nombres de usuario exactos en código:
```python
AGENTES = {
    'agente1': {...},  # Username debe ser exacto
    'agente2': {...}
}
```

---

### Conversaciones no aparecen en el chat

**Causa:** Filtrado está funcionando correctamente pero no hay conversaciones asignadas.

**Diagnóstico:**
1. Verificar asignaciones en BD:
```sql
SELECT * FROM conversaciones_whatsapp WHERE agente_asignado = 'agente1';
```
2. Verificar que Whapi esté enviando webhooks:
```bash
# En logs buscar:
INFO:chat_whatsapp:📨 MENSAJE ENTRANTE DE WHAPI
```

---

### WebSocket no conecta

**Causa:** Socket.IO no se inicializó correctamente.

**Solución:**
1. Verificar logs en inicio:
```
INFO:chat_whatsapp:✅ Instancia de Socket.IO configurada en chat_whatsapp
INFO:chat_whatsapp:📡 Socket.IO handlers registrados para /twilio-chat
```
2. Verificar CDN de Socket.IO en chat.html:
```html
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
```

---

### Round-robin no distribuye equitativamente

**Causa:** Contador puede estar desajustado.

**Solución:**
1. Verificar valor actual:
```sql
SELECT valor FROM sistema_asignacion WHERE clave = 'contador_round_robin';
```
2. Resetear si es necesario (cuidado - solo en mantenimiento):
```sql
UPDATE sistema_asignacion
SET valor = 0
WHERE clave = 'contador_round_robin';
```

## Diagnóstico de Base de Datos

Si las tablas no se están creando en producción, ejecutar el script de diagnóstico:

```bash
python debug_db_init.py
```

Este script verifica:
- ✅ Que el archivo SQL existe
- ✅ Que las variables de entorno de PostgreSQL están configuradas
- ✅ Que la conexión a PostgreSQL funciona
- ✅ Si las tablas existen
- 🔧 Intenta crear las tablas automáticamente si faltan

**Uso en producción:**
```bash
# DigitalOcean App Platform
doctl apps logs <app-id> --type run --follow

# O ejecutar manualmente vía consola/SSH:
python debug_db_init.py
```

Si el script muestra que las tablas no existen pero no puede crearlas, crear manualmente:

```sql
-- Conectarse a PostgreSQL y ejecutar:
\i sql/init_conversaciones_whatsapp.sql

-- O copiar/pegar el contenido del archivo SQL directamente
```

## URLs de Producción

- **Chat**: https://bsl-utilidades.ondigitalocean.app/twilio-chat
- **Login**: https://bsl-utilidades.ondigitalocean.app/twilio-chat/login
- **Webhook Whapi**: https://bsl-utilidades.ondigitalocean.app/twilio-chat/webhook/whapi

## Commits Relevantes

- `8a4c11e` - Feat: Separar chat WhatsApp a módulo independiente con asignación de agentes
- `8931831` - Feat: Agregar interfaz de login y autenticación al chat WhatsApp
- `cf4abe6` - Fix: Actualizar method_whitelist a allowed_methods en urllib3.Retry

## Licencia

Código propietario de BSL - Todos los derechos reservados.

---

**Última actualización:** 2026-01-07
**Versión:** 1.0.0
**Autor:** Claude Code + Daniel Talero
