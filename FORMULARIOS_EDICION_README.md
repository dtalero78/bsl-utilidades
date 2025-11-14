# Sistema de Edición de Formularios - Documentación

## Descripción General

Se ha implementado un sistema completo para ver y editar formularios almacenados en PostgreSQL, con sincronización automática hacia Wix.

## Endpoints Implementados

### 1. GET `/api/formularios`

**Descripción:** Obtiene todos los formularios de la base de datos PostgreSQL.

**Request:**
- Método: `GET`
- Headers: Ninguno requerido
- Query params: Ninguno (soporte para filtros puede agregarse en el futuro)

**Response exitosa (200):**
```json
{
  "success": true,
  "total": 167,
  "data": [
    {
      "id": 167,
      "wix_id": "abc123...",
      "primer_nombre": "Juan",
      "segundo_nombre": "Carlos",
      "primer_apellido": "Pérez",
      "segundo_apellido": "Gómez",
      "numero_id": "1234567890",
      "celular": "3001234567",
      "email": "juan@example.com",
      "cargo": "Ingeniero",
      "empresa": "Acme Corp",
      "cod_empresa": "ACM001",
      "genero": "MASCULINO",
      "edad": 30,
      "fecha_nacimiento": "20/08/1995",
      "ciudad_residencia": "Bogotá",
      "foto": "data:image/jpeg;base64,...",
      "fecha_registro": "2025-11-14T12:00:00.000Z",
      ...
    }
  ]
}
```

**Response error (500):**
```json
{
  "success": false,
  "error": "mensaje de error"
}
```

**CORS:** Permitido desde cualquier origen (`*`)

---

### 2. POST `/api/actualizar-formulario`

**Descripción:** Actualiza un formulario en PostgreSQL y lo sincroniza con Wix si existe `wix_id`.

**Request:**
- Método: `POST`
- Headers: `Content-Type: application/json`
- Body:

```json
{
  "id": 167,
  "wix_id": "abc123...",
  "primer_nombre": "Juan Actualizado",
  "celular": "3009876543",
  "email": "nuevo@email.com",
  "cargo": "Gerente",
  "empresa": "Nueva Empresa",
  ...
}
```

**Campos actualizables:**
- Información personal: `primer_nombre`, `segundo_nombre`, `primer_apellido`, `segundo_apellido`, `numero_id`, `celular`, `email`
- Información laboral: `cargo`, `empresa`, `cod_empresa`
- Información adicional: `genero`, `edad`, `fecha_nacimiento`, `lugar_nacimiento`, `ciudad_residencia`, `hijos`, `profesion_oficio`, `estado_civil`, `nivel_educativo`
- Datos de salud: `estatura`, `peso`, `ejercicio`, `fuma`, etc. (40+ campos de salud)

**Response exitosa (200):**
```json
{
  "success": true,
  "message": "Formulario actualizado correctamente",
  "postgres_updated": true,
  "wix_updated": true,
  "wix_error": null
}
```

**Response con error parcial (200):**
```json
{
  "success": true,
  "message": "Formulario actualizado correctamente",
  "postgres_updated": true,
  "wix_updated": false,
  "wix_error": "HTTP 404"
}
```

**Response error (400/500):**
```json
{
  "success": false,
  "error": "mensaje de error"
}
```

**Flujo de sincronización:**
1. Se actualiza PostgreSQL con los campos recibidos
2. Si existe `wix_id`, se intenta sincronizar con Wix:
   - URL: `https://bsl-formulario-f5qx3.ondigitalocean.app/actualizarFormulario`
   - Los campos se mapean de PostgreSQL a Wix (snake_case → camelCase)
   - Si Wix falla, PostgreSQL ya está actualizado y se retorna el error en `wix_error`

**Mapeo de campos PostgreSQL → Wix:**
```
primer_nombre → primerNombre
segundo_nombre → segundoNombre
primer_apellido → primerApellido
segundo_apellido → segundoApellido
numero_id → numeroId
celular → celular
cargo → cargo
empresa → empresa
cod_empresa → codEmpresa
genero → genero
edad → edad
fecha_nacimiento → fechaNacimiento
lugar_nacimiento → lugarNacimiento
ciudad_residencia → ciudadResidencia
hijos → hijos
profesion_oficio → profesionOficio
empresa1 → empresa1
empresa2 → empresa2
estado_civil → estadoCivil
nivel_educativo → nivelEducativo
email → email
```

**CORS:** Permitido desde cualquier origen (`*`)

---

### 3. GET `/ver-formularios.html`

**Descripción:** Sirve la interfaz web para visualizar y editar formularios.

**Request:**
- Método: `GET`
- Headers: Ninguno requerido

**Response (200):**
- Content-Type: `text/html; charset=utf-8`
- Página HTML completa con:
  - Grid responsivo de tarjetas de formularios
  - Botón de edición en cada tarjeta
  - Modal de edición con formulario
  - Sincronización automática en tiempo real

**Características de la interfaz:**

1. **Vista de formularios:**
   - Grid responsivo (400px mínimo por tarjeta)
   - Muestra foto del paciente si existe
   - Información organizada por secciones:
     - 👤 Información Personal
     - 💼 Información Laboral
     - 📅 Otros Datos
   - Badges para ID de PostgreSQL y Wix ID
   - Botón "Editar" en cada tarjeta

2. **Modal de edición:**
   - Formulario con campos organizados por secciones
   - Validación de formulario HTML5
   - Mensajes de éxito/error en tiempo real
   - Botones de "Guardar" y "Cancelar"
   - Recarga automática después de guardar exitosamente

3. **Estilo:**
   - Fuente: Figtree (Google Fonts)
   - Colores:
     - Primario: `#00B8E6` (azul BSL)
     - Éxito: `#10B981` (verde)
     - Fondo: `#F9FAFB` (gris claro)
   - Animaciones suaves en hover
   - Diseño responsivo

**CORS:** Permitido desde cualquier origen (`*`)

---

## Base de Datos

### Tabla: `formularios`

**Conexión PostgreSQL:**
- Host: `bslpostgres-do-user-19197755-0.k.db.ondigitalocean.com`
- Port: `25060`
- Database: `defaultdb`
- User: `doadmin`
- Password: Variable de entorno `POSTGRES_PASSWORD` (requerida)
- SSL Mode: `require`

**Esquema de campos principales:**
```sql
CREATE TABLE formularios (
    id SERIAL PRIMARY KEY,
    wix_id VARCHAR(255),
    primer_nombre VARCHAR(100),
    segundo_nombre VARCHAR(100),
    primer_apellido VARCHAR(100),
    segundo_apellido VARCHAR(100),
    numero_id VARCHAR(50),
    celular VARCHAR(20),
    email VARCHAR(100),
    cargo VARCHAR(100),
    empresa VARCHAR(100),
    cod_empresa VARCHAR(50),
    genero VARCHAR(20),
    edad INTEGER,
    fecha_nacimiento VARCHAR(20),
    lugar_nacimiento VARCHAR(100),
    ciudad_residencia VARCHAR(100),
    hijos INTEGER,
    profesion_oficio VARCHAR(100),
    empresa1 VARCHAR(100),
    empresa2 VARCHAR(100),
    estado_civil VARCHAR(50),
    nivel_educativo VARCHAR(100),
    estatura VARCHAR(10),
    peso DECIMAL(5,2),
    ejercicio VARCHAR(50),
    foto TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- + 30 campos adicionales de salud
);
```

---

## Sincronización con Wix

### Endpoint de Wix

**URL:** `https://bsl-formulario-f5qx3.ondigitalocean.app/actualizarFormulario`

**Función Backend (funcionesWix/http.js):**
```javascript
export async function post_actualizarFormulario(request) {
    const body = await request.body.json();
    const { _id, ...datos } = body;

    if (!_id) {
        return badRequest({ error: "El parámetro '_id' es requerido" });
    }

    const resultado = await actualizarFormulario(_id, datos);
    return resultado.success ? ok(resultado) : serverError(resultado);
}
```

**Función de Datos (funcionesWix/expose.js):**
```javascript
export async function actualizarFormulario(_id, datos) {
    const existingItem = await wixData.get("FORMULARIO", _id);

    Object.keys(datos).forEach(key => {
        if (key !== '_id') {
            existingItem[key] = datos[key];
        }
    });

    const updated = await wixData.update("FORMULARIO", existingItem);
    return { success: true, item: updated };
}
```

### Flujo de sincronización

1. Usuario edita formulario en `/ver-formularios.html`
2. Frontend envía POST a `/api/actualizar-formulario` con:
   - `id`: ID de PostgreSQL (requerido)
   - `wix_id`: ID de Wix (opcional)
   - Campos a actualizar
3. Backend actualiza PostgreSQL primero
4. Si existe `wix_id`, se llama a Wix:
   - Mapea campos de snake_case a camelCase
   - POST a `https://bsl-formulario-f5qx3.ondigitalocean.app/actualizarFormulario`
   - Maneja errores de Wix sin afectar PostgreSQL
5. Retorna resultado con estado de ambas operaciones

---

## Casos de Uso

### 1. Ver todos los formularios
```bash
curl -X GET https://bsl-formulario-f5qx3.ondigitalocean.app/api/formularios
```

### 2. Actualizar formulario (con sincronización Wix)
```bash
curl -X POST https://bsl-formulario-f5qx3.ondigitalocean.app/api/actualizar-formulario \
  -H "Content-Type: application/json" \
  -d '{
    "id": 167,
    "wix_id": "abc123",
    "primer_nombre": "Juan Actualizado",
    "celular": "3009876543"
  }'
```

### 3. Actualizar formulario (solo PostgreSQL)
```bash
curl -X POST https://bsl-formulario-f5qx3.ondigitalocean.app/api/actualizar-formulario \
  -H "Content-Type: application/json" \
  -d '{
    "id": 167,
    "primer_nombre": "Juan Actualizado",
    "celular": "3009876543"
  }'
```

### 4. Acceder a la interfaz web
```
https://bsl-formulario-f5qx3.ondigitalocean.app/ver-formularios.html
```

---

## Manejo de Errores

### PostgreSQL
- **Error de conexión:** Se retorna 500 con mensaje de error
- **Error de sintaxis SQL:** Se retorna 500 con mensaje de error
- **Formulario no encontrado:** UPDATE no afecta ninguna fila (éxito silencioso)

### Wix
- **Error de red:** Se registra en `wix_error`, PostgreSQL ya actualizado
- **Error 404:** Wix ID no existe, se registra en `wix_error`
- **Error 500:** Error interno de Wix, se registra en `wix_error`
- **Timeout:** Después de 10 segundos, se registra en `wix_error`

### Frontend
- **Error de carga:** Mensaje "Error al cargar formularios" en pantalla
- **Error de guardado:** Mensaje de error en modal, no se cierra el modal
- **Éxito con advertencia Wix:** Mensaje verde indica actualización en PostgreSQL + advertencia sobre Wix

---

## Archivos Modificados

### 1. descargar_bsl.py
**Líneas:** 4978-5854

**Cambios:**
- Agregado endpoint `GET /api/formularios` (líneas 4982-5043)
- Agregado endpoint `POST /api/actualizar-formulario` (líneas 5046-5223)
- Agregado endpoint `GET /ver-formularios.html` (líneas 5226-5850)
- Actualizada configuración CORS (líneas 52-54)

### 2. CORS Configuration
**Archivo:** descargar_bsl.py (líneas 41-55)

**Agregado:**
```python
r"/api/formularios": {"origins": "*", "methods": ["GET", "OPTIONS"]},
r"/api/actualizar-formulario": {"origins": "*", "methods": ["POST", "OPTIONS"]},
r"/ver-formularios.html": {"origins": "*", "methods": ["GET", "OPTIONS"]}
```

---

## Testing

### Test local
```bash
# 1. Iniciar servidor
python3 descargar_bsl.py

# 2. Acceder a la interfaz
open http://localhost:8080/ver-formularios.html

# 3. Test API
curl http://localhost:8080/api/formularios | jq .
```

### Test producción
```bash
# 1. Acceder a la interfaz
open https://bsl-formulario-f5qx3.ondigitalocean.app/ver-formularios.html

# 2. Test API
curl https://bsl-formulario-f5qx3.ondigitalocean.app/api/formularios | jq .
```

---

## Seguridad

### Autenticación
- ⚠️ **No implementada**: Los endpoints son públicos
- ✅ **Recomendación**: Agregar autenticación JWT o API Key en el futuro

### CORS
- ✅ Configurado para permitir cualquier origen (`*`)
- ✅ Permite métodos `GET`, `POST`, `OPTIONS`

### Validación
- ✅ Validación de campos requeridos (`id` en actualización)
- ✅ Validación de tipo de datos en PostgreSQL
- ✅ Sanitización de SQL mediante parámetros preparados (`%s`)

### Datos sensibles
- ⚠️ **Fotos en base64**: Las fotos se almacenan como data URIs y se exponen en la API
- ✅ **Password PostgreSQL**: Almacenada en variable de entorno

---

## Próximas Mejoras

1. **Autenticación y autorización**
   - Implementar JWT tokens
   - Restringir acceso por rol (admin, médico, etc.)

2. **Filtros avanzados**
   - Filtro por rango de fechas
   - Filtro por empresa
   - Filtro por número de identificación
   - Búsqueda por nombre

3. **Paginación**
   - Implementar paginación en `/api/formularios`
   - Limit y offset como query params

4. **Historial de cambios**
   - Registrar quién modificó cada campo
   - Timestamp de cada modificación
   - Tabla de auditoría

5. **Validaciones mejoradas**
   - Validar formato de email
   - Validar formato de celular
   - Validar rango de edad

6. **UI/UX**
   - Agregar buscador en tiempo real
   - Agregar filtros visuales
   - Exportar a Excel/CSV
   - Vista de detalles expandida

---

## Contacto y Soporte

Para preguntas o soporte técnico, contactar al equipo de desarrollo de BSL.

**Última actualización:** 2025-11-14
