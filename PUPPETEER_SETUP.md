# Puppeteer Setup para Digital Ocean

## 📋 Archivos de Configuración

Este proyecto incluye soporte para generar PDFs usando Puppeteer como alternativa a iLovePDF.

### Archivos Necesarios

1. **`package.json`** - Define dependencias de Node.js (Puppeteer)
2. **`package-lock.json`** - Lockfile de dependencias (requerido por Digital Ocean)
3. **`build.sh`** - Script de build que instala Python + Node.js dependencies
4. **`Aptfile`** - Define dependencias del sistema (librerías de Chromium)
5. **`.puppeteerrc.cjs`** - Configuración de Puppeteer
6. **`.do/app.yaml`** - Configuración de Digital Ocean App Platform

## 🚀 Deployment en Digital Ocean

### Configuración Automática

Digital Ocean App Platform detectará automáticamente:
- **Python** como runtime principal
- **Node.js** para Puppeteer (via `package.json`)
- **Build script** (`build.sh`) para instalar ambos
- **Dependencias del sistema** (via `Aptfile`) para Chromium

### Configuración Manual (si es necesario)

Si el auto-deploy falla, configura manualmente en Digital Ocean:

1. **Build Command:**
   ```bash
   ./build.sh
   ```

2. **Run Command:**
   ```bash
   python descargar_bsl.py
   ```

3. **Environment Variables** (ya deberían estar configuradas):
   ```
   PORT=8080
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_WHATSAPP_NUMBER=whatsapp:+573153369631
   WIX_BASE_URL=https://www.bsl.com.co/_functions
   ```

## 🔧 Dependencias del Sistema

Las dependencias de Chromium se instalan automáticamente via `Aptfile`:
- libnss3, libatk1.0-0, libatk-bridge2.0-0
- libcups2, libdrm2, libxkbcommon0
- libxcomposite1, libxdamage1, libxfixes3
- libxrandr2, libgbm1, libasound2
- libpango-1.0-0, libcairo2, libatspi2.0-0
- ca-certificates, fonts-liberation, libxshmfence1

Digital Ocean lee automáticamente el archivo `Aptfile` y ejecuta `apt-get install` antes del build.

## 📍 Endpoints con Puppeteer

### 1. Endpoint Principal con Motor Seleccionable
```bash
GET /api/generar-certificado-pdf/<wix_id>?engine=puppeteer&guardar_drive=true
```

**Parámetros:**
- `engine`: `ilovepdf` (default) o `puppeteer`
- `guardar_drive`: `true` o `false`

### 2. Endpoint Directo Puppeteer
```bash
POST /generar-certificado-medico-puppeteer
Content-Type: application/json

{
  "nombres_apellidos": "Juan Pérez",
  "documento_identidad": "123456789",
  "empresa": "ACME Corp",
  "cargo": "Desarrollador",
  "tipo_examen": "Ingreso",
  "guardar_drive": true,
  ...
}
```

### 3. Endpoint desde Wix (Puppeteer)
```bash
GET /generar-certificado-desde-wix-puppeteer/<wix_id>?guardar_drive=true
```

## 🧪 Testing

### Test Local
```bash
# Verificar que Node.js está instalado
node --version

# Verificar que Puppeteer está instalado
npm list puppeteer

# Test rápido
node -e "const puppeteer = require('puppeteer'); console.log('✅ Puppeteer OK');"
```

### Test en Producción
```bash
# Health check
curl https://bsl-utilidades-yp78a.ondigitalocean.app/health

# Test PDF con Puppeteer
curl -X POST https://bsl-utilidades-yp78a.ondigitalocean.app/api/generar-certificado-pdf/YOUR_WIX_ID?engine=puppeteer
```

## 🐛 Troubleshooting

### Error: "No such file or directory: 'node'"
**Causa**: Node.js no está instalado en el servidor

**Solución**:
1. Verificar que `package.json` existe en la raíz
2. Verificar que `build.sh` está ejecutándose
3. Revisar logs de build en Digital Ocean
4. Agregar Node.js manualmente en la configuración de la app

### Error: "Could not find Chromium"
**Causa**: Puppeteer no pudo descargar Chromium

**Solución**:
1. Verificar variable de entorno: `PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false`
2. Ejecutar: `npm install puppeteer --force`
3. Verificar cache: `ls -la .cache/puppeteer`

### Error: "Failed to launch the browser"
**Causa**: Dependencias del sistema faltantes

**Solución**:
1. Revisar logs del build para ver qué dependencias fallaron
2. Contactar Digital Ocean Support para instalar paquetes del sistema
3. Alternativa: usar `--no-sandbox` flag (menos seguro):
   ```javascript
   puppeteer.launch({ args: ['--no-sandbox', '--disable-setuid-sandbox'] })
   ```

### Error: "Timeout"
**Causa**: El servidor es muy lento o tiene poca memoria

**Solución**:
1. Aumentar timeout en el código Python:
   ```python
   result = subprocess.run(..., timeout=60)  # Incrementar de 30 a 60 segundos
   ```
2. Aumentar el tamaño de instancia en Digital Ocean (de basic-xxs a basic-xs)

## 📊 Comparación: iLovePDF vs Puppeteer

| Característica | iLovePDF | Puppeteer |
|---------------|----------|-----------|
| **Costo** | API de pago | Gratis (self-hosted) |
| **Velocidad** | Rápido (~2-3s) | Medio (~5-7s) |
| **Calidad** | Excelente | Excelente |
| **Dependencias** | Solo API key | Node.js + Chromium |
| **Confiabilidad** | Alta (servicio externo) | Media (depende del servidor) |
| **Offline** | ❌ Requiere internet | ✅ Funciona offline |

## 🎯 Recomendación

- **iLovePDF**: Para producción con alto volumen
- **Puppeteer**: Para desarrollo, testing, o si no quieres depender de servicios externos

---

**Última actualización**: 2025-11-12
