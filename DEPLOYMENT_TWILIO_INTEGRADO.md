# Deployment Twilio-BSL Integrado

## ✅ Código Ya Desplegado

El código de integración ya está en el repositorio y se desplegará automáticamente en Digital Ocean.

## 🔧 Configurar Variables de Entorno en Digital Ocean

1. **Ve a tu app en Digital Ocean**
   - https://cloud.digitalocean.com/apps
   - Selecciona: `bsl-utilidades`

2. **Ir a Settings → App-Level Environment Variables**

3. **Agregar estas variables:**

```
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+573153369631
WIX_BASE_URL=https://www.bsl.com.co/_functions
```

4. **Guardar y esperar redeploy automático** (2-3 minutos)

## 📍 Acceder al Chat

Una vez desplegado, accede en:

```
https://bsl-utilidades-yp78a.ondigitalocean.app/twilio-chat
```

## 🔍 Verificar que Funciona

### 1. Health Check
```bash
curl https://bsl-utilidades-yp78a.ondigitalocean.app/twilio-chat/health
```

Respuesta esperada:
```json
{
  "status": "healthy",
  "service": "twilio-bsl",
  "timestamp": "2025-11-12T15:30:00.000Z",
  "twilio_configured": true
}
```

### 2. Abrir en Navegador
```
https://bsl-utilidades-yp78a.ondigitalocean.app/twilio-chat
```

Deberías ver la interfaz de chat WhatsApp.

## 🔗 Configurar Webhook en Twilio

1. **Ir a Twilio Console**
   - https://console.twilio.com/

2. **Navigate to: Messaging → WhatsApp → Senders**

3. **Seleccionar tu número: +57 315 336 9631**

4. **Configurar Webhook:**
   - **When a message comes in**:
     ```
     https://bsl-utilidades-yp78a.ondigitalocean.app/twilio-chat/webhook/twilio
     ```
   - **Method**: POST

5. **Save**

## 📊 Endpoints Disponibles

Ahora tu aplicación tiene:

### Endpoints Existentes (No cambiaron)
- `/` - Frontend principal
- `/generar-pdf` - Generación de PDFs
- `/generar-certificado-medico` - Certificados médicos
- `/procesar-csv` - Procesamiento CSV
- Todos los demás endpoints existentes

### Nuevos Endpoints Twilio ⭐
- `/twilio-chat` - Interfaz de chat WhatsApp
- `/twilio-chat/health` - Health check
- `/twilio-chat/api/conversaciones` - API conversaciones
- `/twilio-chat/api/conversacion/<numero>` - API conversación específica
- `/twilio-chat/api/enviar-mensaje` - API enviar mensaje
- `/twilio-chat/webhook/twilio` - Webhook Twilio
- `/twilio-chat/static/*` - Archivos estáticos (CSS, JS)

## 🎯 Características

✅ **Mismo dominio** - Todo bajo `bsl-utilidades-yp78a.ondigitalocean.app`
✅ **No requiere nueva app** - Se ejecuta en la aplicación existente
✅ **Auto-deploy** - Se actualiza automáticamente con git push
✅ **Mismas variables de entorno** - Comparte las vars existentes
✅ **Sin conflictos** - Rutas independientes bajo `/twilio-chat`

## 🚨 Solución de Problemas

### Error 404 en /twilio-chat
**Causa**: Variables de entorno no configuradas
**Solución**: Agregar las variables en Digital Ocean (ver paso 2)

### Error "Twilio no configurado"
**Causa**: Credenciales incorrectas o faltantes
**Solución**: Verificar que las variables estén correctas en Digital Ocean

### No aparecen conversaciones
**Causa**:
1. Twilio no tiene mensajes aún
2. Número de teléfono incorrecto

**Solución**:
1. Enviar un mensaje de prueba al número +57 315 336 9631
2. Verificar que el número sea el correcto

### Webhook no recibe mensajes
**Causa**: Webhook no configurado en Twilio
**Solución**: Configurar webhook (ver paso "Configurar Webhook en Twilio")

## 📝 Logs

Para ver logs en Digital Ocean:
1. Ve a tu app
2. Click en "Runtime Logs"
3. Busca mensajes de Twilio:
   - "Cliente Twilio inicializado correctamente"
   - "Mensaje enviado. SID: ..."
   - "Mensaje entrante de ..."

## 🎉 Todo Listo

Una vez configuradas las variables de entorno, tu chat WhatsApp estará funcionando en:

**🔗 https://bsl-utilidades-yp78a.ondigitalocean.app/twilio-chat**

---

**Última actualización**: 2025-11-12
