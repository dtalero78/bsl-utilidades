# Guía de Implementación: Generación de PDF con Puppeteer

Esta guía documenta el proceso completo de generación de certificados médicos en PDF usando Puppeteer (Node.js) en una aplicación Flask.

## Tabla de Contenidos

1. [Arquitectura General](#arquitectura-general)
2. [Requisitos e Instalación](#requisitos-e-instalación)
3. [Funciones Principales de Puppeteer](#funciones-principales-de-puppeteer)
4. [Flujo de Generación de PDF](#flujo-de-generación-de-pdf)
5. [Template HTML del Certificado](#template-html-del-certificado)
6. [Variables del Template](#variables-del-template)
7. [Endpoints de la API](#endpoints-de-la-api)
8. [Manejo de Imágenes](#manejo-de-imágenes)
9. [Configuración de Producción](#configuración-de-producción)

---

## Arquitectura General

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTE                                   │
│  (Navegador / API Request)                                       │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FLASK APP                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. Recibir solicitud (wix_id o datos JSON)             │    │
│  │  2. Consultar datos (PostgreSQL / Wix API)              │    │
│  │  3. Renderizar template HTML con Jinja2                 │    │
│  │  4. Guardar HTML temporal o servir via URL              │    │
│  └─────────────────────┬───────────────────────────────────┘    │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PUPPETEER (Node.js)                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  1. Lanzar Chrome Headless                              │    │
│  │  2. Cargar HTML (file:// o URL pública)                 │    │
│  │  3. Esperar carga de imágenes                           │    │
│  │  4. Generar PDF con page.pdf()                          │    │
│  │  5. Retornar bytes del PDF                              │    │
│  └─────────────────────┬───────────────────────────────────┘    │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     RESPUESTA                                    │
│  - PDF binario directo                                           │
│  - O subir a Google Drive y retornar URL                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Requisitos e Instalación

### Dependencias de Node.js

```bash
# Inicializar proyecto Node.js (si no existe)
npm init -y

# Instalar Puppeteer
npm install puppeteer
```

### Dependencias de Python

```bash
pip install flask jinja2
```

### Estructura de Archivos

```
proyecto/
├── app.py                          # Aplicación Flask principal
├── node_modules/                   # Módulos de Node.js
│   └── puppeteer/
├── package.json
├── templates/
│   └── certificado_medico.html     # Template Jinja2 del certificado
└── static/
    ├── logo-bsl.png                # Logo de la empresa
    ├── FIRMA-JUAN134.jpeg          # Firmas de médicos
    ├── FIRMA-SIXTA.png
    └── ...
```

---

## Funciones Principales de Puppeteer

### Método 1: Desde URL Pública

Esta función carga una URL pública y la convierte a PDF. Útil cuando el HTML ya está servido por Flask.

```python
import subprocess
import tempfile
import os

def puppeteer_html_to_pdf_from_url(html_url, output_filename="certificado"):
    """
    Convierte HTML a PDF usando Puppeteer desde una URL pública.

    Args:
        html_url: URL pública del HTML a convertir
        output_filename: Nombre del archivo de salida (sin extensión)

    Returns:
        bytes: Contenido del PDF generado
    """
    try:
        print("🎭 Iniciando conversión HTML→PDF con Puppeteer...")

        # Crear archivo temporal para el PDF
        temp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        temp_pdf_path = temp_pdf.name
        temp_pdf.close()

        # Obtener directorio del proyecto para referenciar node_modules
        project_dir = os.path.dirname(os.path.abspath(__file__))

        # Script de Puppeteer
        puppeteer_script = f"""
const puppeteer = require('{project_dir}/node_modules/puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process'
        ]
    }});

    const page = await browser.newPage();

    // Configurar User-Agent para evitar bloqueos
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

    // Configurar headers
    await page.setExtraHTTPHeaders({{
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
        'Referer': '{html_url}'
    }});

    // Cargar la URL
    await page.goto('{html_url}', {{
        waitUntil: ['load', 'networkidle0'],
        timeout: 45000
    }});

    // Esperar a que las imágenes se carguen
    await page.evaluate(() => {{
        return Promise.all(
            Array.from(document.images).map(img => {{
                return new Promise((resolve) => {{
                    if (img.complete) {{
                        resolve();
                        return;
                    }}
                    img.addEventListener('load', resolve);
                    img.addEventListener('error', resolve);
                    setTimeout(resolve, 10000);
                }});
            }})
        );
    }});

    // Esperar renderizado completo
    await new Promise(resolve => setTimeout(resolve, 3000));

    // Generar PDF
    await page.pdf({{
        path: '{temp_pdf_path}',
        format: 'Letter',
        printBackground: true,
        margin: {{
            top: '0.5cm',
            right: '0.5cm',
            bottom: '0.5cm',
            left: '0.5cm'
        }}
    }});

    await browser.close();
    console.log('✅ PDF generado exitosamente');
}})();
"""

        # Guardar script temporal
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as temp_script:
            temp_script.write(puppeteer_script)
            temp_script_path = temp_script.name

        # Configurar NODE_PATH
        env = os.environ.copy()
        env['NODE_PATH'] = os.path.join(project_dir, 'node_modules')

        # Ejecutar Puppeteer
        result = subprocess.run(
            ['node', temp_script_path],
            capture_output=True,
            text=True,
            timeout=90,
            env=env
        )

        if result.returncode != 0:
            raise Exception(f"Puppeteer falló: {result.stderr}")

        # Leer el PDF generado
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_content = pdf_file.read()

        # Limpiar archivos temporales
        os.unlink(temp_pdf_path)
        os.unlink(temp_script_path)

        return pdf_content

    except subprocess.TimeoutExpired:
        raise Exception("Timeout en la conversión con Puppeteer")
    except Exception as e:
        raise
```

### Método 2: Desde HTML Local (file://)

Esta función es más simple y rápida, ideal cuando no necesitas servir el HTML públicamente.

```python
def generar_pdf_con_puppeteer_local(html_content, output_filename="certificado"):
    """
    Genera un PDF usando Puppeteer desde HTML guardado localmente.

    Args:
        html_content: String con el HTML renderizado
        output_filename: Nombre base del archivo PDF

    Returns:
        bytes: Contenido del PDF generado
    """
    try:
        # Guardar HTML en archivo temporal
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as html_file:
            html_file.write(html_content)
            html_path = html_file.name

        pdf_path = html_path.replace('.html', '.pdf')
        project_dir = os.path.dirname(os.path.abspath(__file__))

        # Script de Puppeteer (versión simple)
        puppeteer_script = f"""
const puppeteer = require('{project_dir}/node_modules/puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: 'new',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ]
    }});

    const page = await browser.newPage();

    // Cargar HTML desde archivo local
    await page.goto('file://{html_path}', {{
        waitUntil: 'networkidle0',
        timeout: 30000
    }});

    // Generar PDF
    await page.pdf({{
        path: '{pdf_path}',
        format: 'Letter',
        printBackground: true,
        margin: {{
            top: '0.5cm',
            right: '0.5cm',
            bottom: '0.5cm',
            left: '0.5cm'
        }}
    }});

    await browser.close();
    console.log('✅ PDF generado exitosamente');
}})();
"""

        # Guardar y ejecutar script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as js_file:
            js_file.write(puppeteer_script)
            js_path = js_file.name

        result = subprocess.run(
            ['node', js_path],
            capture_output=True,
            text=True,
            timeout=35,
            cwd=project_dir
        )

        if result.returncode == 0 and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as pdf_file:
                pdf_bytes = pdf_file.read()

            # Limpiar archivos temporales
            os.unlink(html_path)
            os.unlink(js_path)
            os.unlink(pdf_path)

            return pdf_bytes
        else:
            raise Exception(f"Error: {result.stderr}")

    except Exception as e:
        raise
```

---

## Flujo de Generación de PDF

### Paso 1: Recibir Solicitud

```python
@app.route("/api/generar-certificado-pdf/<wix_id>", methods=["GET"])
def api_generar_certificado_pdf(wix_id):
    """Genera el PDF del certificado médico."""

    # 1. Consultar datos del paciente
    datos_paciente = obtener_datos_paciente(wix_id)

    # 2. Preparar datos para el template
    datos_certificado = preparar_datos_certificado(datos_paciente)

    # 3. Generar PDF usando el preview HTML
    preview_url = f"https://tu-dominio.com/preview-certificado-html/{wix_id}"
    pdf_content = puppeteer_html_to_pdf_from_url(preview_url)

    # 4. Retornar PDF
    return Response(
        pdf_content,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'inline; filename=certificado_{wix_id}.pdf'
        }
    )
```

### Paso 2: Endpoint de Preview HTML

```python
@app.route("/preview-certificado-html/<wix_id>", methods=["GET"])
def preview_certificado_html(wix_id):
    """Genera el HTML del certificado para preview o para Puppeteer."""

    # 1. Obtener datos
    datos = obtener_datos_completos(wix_id)

    # 2. Renderizar template
    html = render_template(
        'certificado_medico.html',
        **datos
    )

    return html
```

---

## Template HTML del Certificado

### Estructura General

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Certificado Médico Ocupacional</title>
    <style>
        /* Estilos CSS embebidos para garantizar renderizado correcto */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: Arial, sans-serif;
            background: #f0f0f0;
            padding: 20px;
        }

        .certificate-container {
            max-width: 8.5in;  /* Tamaño carta */
            margin: 0 auto;
            background: white;
            padding: 40px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }

        /* Header con 3 columnas: Logo | Título | QR */
        .header {
            display: grid;
            grid-template-columns: 200px 1fr 150px;
            gap: 20px;
            align-items: start;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #00a651;
        }

        /* Estilos para secciones */
        .section {
            margin-bottom: 25px;
        }

        .section-title {
            background: linear-gradient(90deg, #0066cc 0%, #00a651 100%);
            color: white;
            padding: 8px 15px;
            font-size: 13px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 15px;
            text-transform: uppercase;
        }

        /* Tabla de datos */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 10px;
        }

        .data-table td {
            padding: 6px 10px;
            border: 1px solid #ddd;
        }

        .data-table td.label {
            background: #f5f5f5;
            font-weight: bold;
            color: #0066cc;
            width: 18%;
        }

        /* Control de saltos de página para impresión */
        @media print {
            .section {
                page-break-inside: avoid;
            }
            .header {
                page-break-inside: avoid;
                page-break-after: avoid;
            }
            .signatures-section {
                page-break-inside: avoid;
            }
        }
    </style>
</head>
<body>
    <div class="certificate-container">
        <!-- HEADER -->
        <div class="header">
            <div class="logo-section">
                <img src="{{ logo_url }}" alt="Logo">
                <div class="company-info">
                    Nit. 900.844.030-8<br>
                    Licencia No. 64 del 10-01-2017
                </div>
            </div>
            <div class="title-section">
                <h1>Certificado Médico Ocupacional</h1>
                <div class="security-code">Código: {{ codigo_seguridad }}</div>
                <div class="exam-type">Tipo: {{ tipo_examen }}</div>
            </div>
            <div class="qr-section">
                <img src="{{ qr_code_url }}" alt="QR Code">
            </div>
        </div>

        <!-- DATOS PERSONALES -->
        <div class="section">
            <div class="section-title">Datos Personales</div>
            <div style="display: flex; gap: 15px;">
                {% if foto_paciente %}
                <img src="{{ foto_paciente }}" class="patient-photo">
                {% endif %}
                <table class="data-table">
                    <tr>
                        <td class="label">Nombres y apellidos</td>
                        <td class="value" colspan="5">{{ nombres_apellidos }}</td>
                    </tr>
                    <tr>
                        <td class="label">Documento</td>
                        <td class="value">{{ documento_identidad }}</td>
                        <td class="label">Empresa</td>
                        <td class="value">{{ empresa }}</td>
                        <td class="label">Cargo</td>
                        <td class="value">{{ cargo }}</td>
                    </tr>
                    <!-- Más filas según necesidad -->
                </table>
            </div>
        </div>

        <!-- EXÁMENES REALIZADOS -->
        <div class="section">
            <div class="section-title">Exámenes Realizados</div>
            <div class="exams-container">
                {% for examen in examenes_realizados %}
                <div class="exam-box">
                    <h3>{{ examen.nombre }}</h3>
                    <div class="exam-date">{{ examen.fecha }}</div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- CONCEPTO MÉDICO -->
        {% if concepto_medico %}
        <div class="section">
            <div class="section-title">Concepto de Evaluación Médica</div>
            <div class="medical-concept">
                <div class="result">{{ concepto_medico }}</div>
            </div>
        </div>
        {% endif %}

        <!-- FIRMAS -->
        <div class="signatures-section">
            <div class="section-title">Firmas</div>
            <div class="signatures-container">
                <div class="signature-box">
                    <div class="signature-header">Firma Médico</div>
                    {% if firma_medico_url %}
                    <img src="{{ firma_medico_url }}" class="signature-img">
                    {% endif %}
                    <div class="signature-name">{{ medico_nombre }}</div>
                    <div class="signature-details">
                        {{ medico_registro }}<br>
                        {{ medico_licencia }}
                    </div>
                </div>
                <div class="signature-box">
                    <div class="signature-header">Firma Paciente</div>
                    {% if firma_paciente_url %}
                    <img src="{{ firma_paciente_url }}" class="signature-img">
                    {% endif %}
                    <div class="signature-name">{{ nombres_apellidos }}</div>
                </div>
            </div>
        </div>

        <!-- FOOTER -->
        <div class="footer">
            EMPRESA SAS - Dirección - www.empresa.com
        </div>
    </div>
</body>
</html>
```

---

## Variables del Template

### Variables Obligatorias

| Variable | Tipo | Descripción | Ejemplo |
|----------|------|-------------|---------|
| `logo_url` | string | URL del logo de la empresa | `https://dominio.com/static/logo.png` |
| `codigo_seguridad` | string | Código único del certificado | `a1b2c3d4-e5f6-7890` |
| `tipo_examen` | string | Tipo de examen ocupacional | `Ingreso`, `Periódico`, `Retiro` |
| `nombres_apellidos` | string | Nombre completo del paciente | `JUAN CARLOS PÉREZ GÓMEZ` |
| `documento_identidad` | string | Número de identificación | `1234567890` |
| `empresa` | string | Nombre de la empresa | `ACME CORP` |
| `cargo` | string | Cargo del empleado | `Ingeniero de Sistemas` |
| `fecha_atencion` | string | Fecha del examen | `15 de Diciembre de 2025` |

### Variables Opcionales

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `foto_paciente` | string | URL de la foto del paciente |
| `concepto_medico` | string | Concepto médico final (APTO, NO APTO, etc.) |
| `examenes_realizados` | list | Lista de exámenes `[{nombre, fecha}]` |
| `resultados_generales` | list | Resultados `[{examen, descripcion}]` |
| `firma_medico_url` | string | URL de la imagen de firma del médico |
| `firma_paciente_url` | string | URL de la firma del paciente |
| `medico_nombre` | string | Nombre del médico |
| `medico_registro` | string | Registro médico |
| `medico_licencia` | string | Licencia de salud ocupacional |
| `datos_visual` | dict | Datos de optometría |
| `datos_audiometria` | dict | Datos de audiometría |
| `recomendaciones_medicas` | string | Recomendaciones adicionales |

### Estructura de Datos Complejos

#### examenes_realizados

```python
examenes_realizados = [
    {"nombre": "Examen Médico Ocupacional", "fecha": "15 de Diciembre de 2025"},
    {"nombre": "Audiometría", "fecha": "15 de Diciembre de 2025"},
    {"nombre": "Optometría", "fecha": "15 de Diciembre de 2025"}
]
```

#### datos_visual (Optometría)

```python
datos_visual = {
    "resultadoNumerico": "Esfera: -1.5, Cilindro: -1.25...",
    "miopia": "si",
    "astigmatismo": "si"
}
```

#### datos_audiometria

```python
datos_audiometria = {
    "datosParaTabla": [
        {"frecuencia": 250, "oidoDerecho": 10, "oidoIzquierdo": 15},
        {"frecuencia": 500, "oidoDerecho": 10, "oidoIzquierdo": 10},
        # ... más frecuencias
    ],
    "diagnostico": "Audición dentro de parámetros normales"
}
```

---

## Endpoints de la API

### GET /preview-certificado-html/{wix_id}

Genera y devuelve el HTML del certificado para preview o conversión.

**Respuesta:** HTML renderizado

### GET /api/generar-certificado-pdf/{wix_id}

Genera el PDF del certificado.

**Respuesta:** PDF binario

### GET /generar-certificado-desde-wix/{wix_id}

Muestra página de carga mientras genera el PDF.

**Respuesta:** HTML con loader animado que hace polling al endpoint de generación

### POST /generar-certificado-medico

Genera certificado desde datos JSON directos.

**Body:**
```json
{
    "nombres_apellidos": "JUAN PÉREZ",
    "documento_identidad": "1234567890",
    "empresa": "ACME CORP",
    "cargo": "Ingeniero",
    "tipo_examen": "Ingreso",
    "examenes": ["Examen Médico", "Audiometría"],
    "concepto_medico": "APTO",
    "guardar_drive": true
}
```

**Respuesta:**
```json
{
    "success": true,
    "pdf_url": "https://...",
    "codigo_seguridad": "abc123",
    "drive_web_link": "https://drive.google.com/..."
}
```

---

## Manejo de Imágenes

### Fuentes de Imágenes

1. **Imágenes estáticas** (logos, firmas): Servidas desde `/static/`
2. **Fotos de pacientes**: URLs públicas (Digital Ocean Spaces, Wix CDN)
3. **Firmas de pacientes**: Data URIs base64 o URLs públicas

### Estrategia de Carga

```python
# Prioridad para fotos de pacientes:
# 1. URL pública de Digital Ocean Spaces (foto_url)
# 2. Data URI base64 (foto)
# 3. URL de Wix CDN (fallback)

if foto_url and foto_url.startswith("http"):
    datos['foto_paciente'] = foto_url  # URL pública
elif foto and foto.startswith("data:image/"):
    datos['foto_paciente'] = foto  # Base64 embebido
```

### Cacheo de Imágenes de Wix

Wix CDN puede bloquear requests directos (403). Solución:

```python
def descargar_imagen_wix_a_do_spaces(wix_url):
    """
    Descarga imagen de Wix y la sube a Digital Ocean Spaces.
    Fallback: usar Puppeteer si requests falla.
    """
    try:
        # Intento 1: requests con headers de navegador
        headers = {
            'User-Agent': 'Mozilla/5.0 ...',
            'Accept': 'image/*',
            'Referer': 'https://www.wix.com/'
        }
        response = requests.get(wix_url, headers=headers, timeout=10)
        response.raise_for_status()
        image_bytes = response.content

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            # Intento 2: Puppeteer
            image_bytes, content_type = descargar_imagen_con_puppeteer(wix_url)
            if not image_bytes:
                return None  # Usar URL original

    # Subir a DO Spaces
    return subir_imagen_a_do_spaces(image_bytes, filename, content_type)
```

---

## Configuración de Producción

### Variables de Entorno

```bash
# Node.js
NODE_PATH=/app/node_modules

# Puppeteer
PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false
PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser  # En algunos servidores
```

### Dockerfile (ejemplo)

```dockerfile
FROM python:3.11-slim

# Instalar Node.js y dependencias de Chrome
RUN apt-get update && apt-get install -y \
    nodejs npm \
    chromium \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Node
COPY package*.json ./
RUN npm install

# Instalar dependencias de Python
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

# Variables de entorno para Puppeteer
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

CMD ["python", "app.py"]
```

### Heroku (Procfile + buildpacks)

```
# Procfile
web: python app.py

# Buildpacks necesarios:
# 1. heroku/nodejs
# 2. heroku/python
# 3. https://github.com/jontewks/puppeteer-heroku-buildpack
```

### Timeouts Recomendados

| Operación | Timeout |
|-----------|---------|
| Carga de página | 45 segundos |
| Carga de imágenes | 10 segundos por imagen |
| Espera post-carga | 3-5 segundos |
| Generación de PDF | 90 segundos total |
| Subprocess Node.js | 90 segundos |

---

## Solución de Problemas Comunes

### Imágenes no aparecen en el PDF

1. Verificar que las URLs son públicamente accesibles
2. Usar `waitUntil: 'networkidle0'` en Puppeteer
3. Agregar espera explícita para carga de imágenes
4. Verificar headers CORS si es necesario

### Error: Chrome not found

```bash
# En producción, instalar Chromium del sistema
apt-get install chromium

# Configurar variable de entorno
export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
```

### Timeout en generación

1. Aumentar timeout de subprocess
2. Reducir tamaño/cantidad de imágenes
3. Usar imágenes desde CDN cercano
4. Considerar método `file://` si las imágenes son locales

### PDF cortado o mal formateado

1. Usar `@media print` en CSS para control de saltos de página
2. Agregar `page-break-inside: avoid` a secciones importantes
3. Verificar que `max-width` del contenedor sea menor a 8.5in

---

## Ejemplo Completo de Uso

```python
from flask import Flask, render_template, Response
import uuid

app = Flask(__name__)

@app.route("/generar-certificado/<paciente_id>")
def generar_certificado(paciente_id):
    # 1. Obtener datos del paciente
    paciente = obtener_paciente(paciente_id)

    # 2. Preparar datos del certificado
    datos = {
        "logo_url": "https://mi-app.com/static/logo.png",
        "codigo_seguridad": str(uuid.uuid4()),
        "tipo_examen": paciente.tipo_examen,
        "nombres_apellidos": f"{paciente.nombre} {paciente.apellido}",
        "documento_identidad": paciente.cedula,
        "empresa": paciente.empresa,
        "cargo": paciente.cargo,
        "fecha_atencion": formatear_fecha(paciente.fecha),
        "examenes_realizados": [
            {"nombre": e.nombre, "fecha": formatear_fecha(e.fecha)}
            for e in paciente.examenes
        ],
        "concepto_medico": paciente.concepto,
        "firma_medico_url": f"https://mi-app.com/static/firmas/{paciente.medico}.jpeg",
        "medico_nombre": paciente.medico_nombre,
        "medico_registro": paciente.medico_registro
    }

    # 3. Generar HTML
    html = render_template("certificado_medico.html", **datos)

    # 4. Convertir a PDF
    pdf_bytes = generar_pdf_con_puppeteer_local(html)

    # 5. Retornar PDF
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename=certificado_{paciente_id}.pdf'
        }
    )

if __name__ == "__main__":
    app.run(port=8080)
```

---

## Obtención de Datos - Fuentes y Prioridad

### Arquitectura de Datos

El sistema obtiene datos de **3 fuentes principales** con la siguiente prioridad:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRIORIDAD DE DATOS                           │
├─────────────────────────────────────────────────────────────────┤
│  1. PostgreSQL (MÁXIMA PRIORIDAD)                               │
│     └── Sobrescribe TODOS los datos de Wix                      │
│                                                                  │
│  2. Wix HTTP Functions (Fallback)                               │
│     └── Se usa si PostgreSQL no tiene el dato                   │
│                                                                  │
│  3. Valores por defecto                                         │
│     └── Si ninguna fuente tiene el dato                         │
└─────────────────────────────────────────────────────────────────┘
```

### Tablas en PostgreSQL

#### Tabla: HistoriaClinica (Datos principales del paciente)

```sql
SELECT
    _id,                              -- ID único (orden_xxx)
    "numeroId",                       -- Cédula del paciente
    "primerNombre", "segundoNombre",  -- Nombres
    "primerApellido", "segundoApellido", -- Apellidos
    celular, email,
    "codEmpresa", empresa, cargo,
    "tipoExamen",                     -- Ingreso, Periódico, Retiro, etc.
    examenes,                         -- String separado por comas
    "mdAntecedentes",                 -- Antecedentes médicos
    "mdObservacionesCertificado",     -- Observaciones del certificado
    "mdRecomendacionesMedicasAdicionales",
    "mdConceptoFinal",                -- APTO, APTO CON RESTRICCIONES, NO APTO
    "mdDx1", "mdDx2",                 -- Diagnósticos CIE-10
    talla, peso,
    "fechaAtencion", "fechaConsulta",
    atendido, "pvEstado",
    medico,                           -- JUAN 134, SIXTA, CESAR, MARY, NUBIA, PRESENCIAL
    ciudad,
    pagado, fecha_pago
FROM "HistoriaClinica"
WHERE _id = 'orden_xxx';
```

#### Tabla: formularios (Datos demográficos y foto)

```sql
SELECT
    foto,                   -- Data URI base64 de la foto
    foto_url,               -- URL pública en DO Spaces (PRIORIDAD)
    edad,
    genero,
    estado_civil,
    hijos,
    email,
    profesion_oficio,
    ciudad_residencia,
    fecha_nacimiento,
    primer_nombre, primer_apellido,
    firma,                  -- Firma del paciente (Data URI base64)
    eps, arl, pensiones,
    nivel_educativo
FROM formularios
WHERE wix_id = 'orden_xxx';
```

### Endpoints de Wix HTTP Functions

```python
# Historia Clínica principal
wix_url = "https://www.bsl.com.co/_functions/historiaClinicaPorId?_id={wix_id}"

# Datos de Optometría/Visiometría
visual_url = "https://www.bsl.com.co/_functions/visualPorIdGeneral?idGeneral={wix_id}"

# Datos de Audiometría
audio_url = "https://www.bsl.com.co/_functions/audiometriaPorIdGeneral?idGeneral={wix_id}"
```

### Código de Obtención de Datos

```python
def obtener_datos_completos(wix_id):
    """Obtiene todos los datos del paciente con prioridad PostgreSQL > Wix"""

    datos = {}

    # 1. Intentar obtener de Wix primero
    try:
        wix_url = f"https://www.bsl.com.co/_functions/historiaClinicaPorId?_id={wix_id}"
        response = requests.get(wix_url, timeout=10)
        if response.status_code == 200:
            datos = response.json().get("data", {})
    except Exception as e:
        print(f"Error Wix: {e}")

    # 2. PostgreSQL tiene PRIORIDAD - sobrescribe todo
    datos_postgres = obtener_datos_historia_clinica_postgres(wix_id)
    if datos_postgres:
        for key, value in datos_postgres.items():
            if value is not None:
                datos[key] = value  # PostgreSQL sobrescribe Wix

    # 3. Obtener datos demográficos del formulario
    datos_formulario = obtener_datos_formulario_postgres(wix_id)
    if datos_formulario:
        # Foto - priorizar foto_url sobre foto base64
        if datos_formulario.get('foto_url'):
            datos['foto_paciente'] = datos_formulario['foto_url']
        elif datos_formulario.get('foto'):
            datos['foto_paciente'] = datos_formulario['foto']

        # Otros campos demográficos
        datos['edad'] = datos_formulario.get('edad')
        datos['genero'] = datos_formulario.get('genero')
        datos['estado_civil'] = datos_formulario.get('estadoCivil')
        datos['eps'] = datos_formulario.get('eps')
        datos['arl'] = datos_formulario.get('arl')
        # ... más campos

    return datos
```

---

## Formato Gráfico del Certificado - Sección por Sección

### Vista General del Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌──────────┐    CERTIFICADO MÉDICO        ┌──────────┐        │
│  │   LOGO   │      OCUPACIONAL             │    QR    │        │
│  │   BSL    │   Código: abc-123            │   CODE   │        │
│  └──────────┘   Tipo: Ingreso              └──────────┘        │
├─────────────────────────────────────────────────────────────────┤
│                    DATOS PERSONALES                             │
│  ┌──────┐  ┌────────────────────────────────────────────────┐  │
│  │ FOTO │  │ Fecha Atención | Ciudad    | Vigencia          │  │
│  │  DEL │  │ IPS/SEDE                                       │  │
│  │PACIEN│  │ Nombres y apellidos                            │  │
│  │  TE  │  │ Documento | Empresa | Cargo                    │  │
│  └──────┘  │ Género | Edad | Fecha nacimiento               │  │
│            │ Estado civil | Hijos | Profesión               │  │
│            │ Email | Tipo de examen                         │  │
│            │ EPS | ARL | Pensiones                          │  │
│            │ Nivel Educativo                                │  │
│            └────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                   EXÁMENES REALIZADOS                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ Examen Méd. │ │ Audiometría │ │ Optometría  │               │
│  │ 15 Dic 2025 │ │ 15 Dic 2025 │ │ 15 Dic 2025 │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
├─────────────────────────────────────────────────────────────────┤
│              CONCEPTO DE EVALUACIÓN MÉDICA                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    APTO SIN RESTRICCIONES               │   │
│  │  De acuerdo al examen ocupacional realizado a...        │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                   RESULTADOS GENERALES                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR                 │   │
│  │ Resultados dentro de parámetros normales...             │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│                         FIRMAS                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │    FIRMA MÉDICO     │    │  FIRMA PACIENTE     │            │
│  │    [Imagen firma]   │    │   [Imagen firma]    │            │
│  │   Dr. Juan Reatiga  │    │   Nombre Paciente   │            │
│  │   RM 14791          │    │   CC 123456789      │            │
│  └─────────────────────┘    └─────────────────────┘            │
├─────────────────────────────────────────────────────────────────┤
│               RESULTADOS DE OPTOMETRÍA                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Resultados Numéricos:                                   │   │
│  │ Esfera: -1.5 | Cilindro: -1.25 | Eje: 132°             │   │
│  │ Miopía: Sí | Astigmatismo: Sí                          │   │
│  │ Firma Optómetra: [imagen]                               │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│               RESULTADOS DE AUDIOMETRÍA                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              AUDIOGRAMA (SVG)                           │   │
│  │   Hz:  250  500  1000  2000  3000  4000  6000  8000    │   │
│  │   OD:   10   10    10    10    10    70    10    10    │   │
│  │   OI:   10   10    10    10    10    10    10    10    │   │
│  │                                                         │   │
│  │ Diagnóstico: Audición normal bilateral                  │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  FOOTER: BSL SAS - Calle 134 #7-83 - www.bsl.com.co            │
└─────────────────────────────────────────────────────────────────┘
```

### Sección 1: HEADER (Encabezado)

```html
<!-- Layout: 3 columnas con CSS Grid -->
<div class="header">
    <!-- Columna 1: Logo (200px) -->
    <div class="logo-section">
        <img src="{{ logo_url }}" alt="Logo">
        <div class="company-info">
            Nit. 900.844.030-8<br>
            Licencia No. 64 del 10-01-2017<br>
            Calle 134 # 7-83 cons 233, Bogotá D.C.
        </div>
    </div>

    <!-- Columna 2: Título (flex) -->
    <div class="title-section">
        <h1>Certificado Médico Ocupacional</h1>
        <div class="security-code">Código: {{ codigo_seguridad }}</div>
        <div class="exam-type">Tipo: {{ tipo_examen }}</div>
    </div>

    <!-- Columna 3: QR (150px) -->
    <div class="qr-section">
        <img src="{{ qr_code_url }}" alt="QR">
        <div class="qr-verify-notice">Verifica validez</div>
    </div>
</div>
```

**Variables:**
| Variable | Fuente | Ejemplo |
|----------|--------|---------|
| `logo_url` | Estático | `https://dominio.com/static/logo-bsl.png` |
| `codigo_seguridad` | Generado (UUID4) | `a1b2c3d4-e5f6-7890` |
| `tipo_examen` | PostgreSQL `tipoExamen` | `Ingreso`, `Periódico`, `Retiro` |
| `qr_code_url` | Estático o generado | URL de imagen QR |

**CSS:**
```css
.header {
    display: grid;
    grid-template-columns: 200px 1fr 150px;
    gap: 20px;
    border-bottom: 3px solid #00a651;
    padding-bottom: 20px;
}

.title-section h1 {
    color: #0066cc;
    font-size: 20px;
    text-transform: uppercase;
}
```

### Sección 2: DATOS PERSONALES

```html
<div class="section">
    <div class="section-title">Datos Personales</div>

    <div style="display: flex; gap: 15px;">
        <!-- Foto del paciente (opcional) -->
        {% if foto_paciente %}
        <img src="{{ foto_paciente }}" class="patient-photo">
        {% endif %}

        <!-- Tabla de datos -->
        <table class="data-table">
            <tr>
                <td class="label">Fecha de Atención</td>
                <td class="value">{{ fecha_atencion }}</td>
                <td class="label">Ciudad</td>
                <td class="value">{{ ciudad }}</td>
                <td class="label">Vigencia</td>
                <td class="value">{{ vigencia }}</td>
            </tr>
            <!-- Más filas... -->
        </table>
    </div>
</div>
```

**Variables y sus fuentes:**

| Variable | Tabla PostgreSQL | Campo | Formato |
|----------|------------------|-------|---------|
| `foto_paciente` | formularios | `foto_url` o `foto` | URL o Data URI base64 |
| `fecha_atencion` | HistoriaClinica | `fechaConsulta` | "15 de Diciembre de 2025" |
| `ciudad` | HistoriaClinica | `ciudad` | "BOGOTA" |
| `vigencia` | Calculado | - | "Tres años" |
| `ips_sede` | Constante | - | "Sede norte DHSS0244914" |
| `nombres_apellidos` | HistoriaClinica | `primerNombre` + `segundoNombre` + `primerApellido` + `segundoApellido` | "JUAN CARLOS PÉREZ GÓMEZ" |
| `documento_identidad` | HistoriaClinica | `numeroId` | "1234567890" |
| `empresa` | HistoriaClinica | `empresa` | "ACME CORP" |
| `cargo` | HistoriaClinica | `cargo` | "Ingeniero de Sistemas" |
| `genero` | formularios | `genero` | "Masculino" |
| `edad` | formularios | `edad` | "35" |
| `fecha_nacimiento` | formularios | `fecha_nacimiento` | "15 de Marzo de 1990" |
| `estado_civil` | formularios | `estado_civil` | "Casado" |
| `hijos` | formularios | `hijos` | "2" |
| `profesion` | formularios | `profesion_oficio` | "Ingeniero" |
| `email` | formularios | `email` | "juan@email.com" |
| `eps` | formularios | `eps` | "SURA" |
| `arl` | formularios | `arl` | "SURA" |
| `pensiones` | formularios | `pensiones` | "PORVENIR" |
| `nivel_educativo` | formularios | `nivel_educativo` | "Profesional" |

**CSS:**
```css
.patient-photo {
    width: 90px;
    height: 110px;
    object-fit: cover;
    border: 2px solid #0066cc;
    border-radius: 5px;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
}

.data-table td.label {
    background: #f5f5f5;
    font-weight: bold;
    color: #0066cc;
    width: 18%;
}
```

### Sección 3: EXÁMENES REALIZADOS

```html
<div class="section">
    <div class="section-title">Exámenes Realizados</div>
    <div class="exams-container">
        {% for examen in examenes_realizados %}
        <div class="exam-box">
            <h3>{{ examen.nombre }}</h3>
            <div class="exam-date">{{ examen.fecha }}</div>
        </div>
        {% endfor %}
    </div>
</div>
```

**Variable `examenes_realizados`:**
```python
# Fuente: PostgreSQL HistoriaClinica.examenes (string separado por comas)
# Ejemplo en BD: "Examen Médico Ocupacional Osteomuscular, Audiometría, Optometría"

# Transformación:
examenes_raw = datos_postgres.get('examenes', '')
examenes_lista = [e.strip() for e in examenes_raw.split(',')]

examenes_realizados = [
    {"nombre": "Examen Médico Ocupacional Osteomuscular", "fecha": "15 de Diciembre de 2025"},
    {"nombre": "Audiometría", "fecha": "15 de Diciembre de 2025"},
    {"nombre": "Optometría", "fecha": "15 de Diciembre de 2025"}
]
```

**Mapeo de Exámenes (Normalización):**
```python
MAPEO_EXAMENES = {
    "Audiometría": "AUDIOMETRÍA",
    "AUDIOMETRÍA": "AUDIOMETRÍA",
    "Optometría": "OPTOMETRÍA",
    "Visiometría": "VISIOMETRÍA",
    "SCL-90": "SCL-90",
    "Perfil Psicológico ADC": "PERFIL PSICOLÓGICO ADC",
    "Examen Médico Ocupacional Osteomuscular": "EXAMEN MÉDICO OCUPACIONAL OSTEOMUSCULAR",
    # ... más mapeos
}
```

**CSS:**
```css
.exams-container {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 15px;
}

.exam-box {
    background: #e8e8e8;
    padding: 12px;
    text-align: center;
    border-radius: 4px;
}

.exam-box h3 {
    font-size: 11px;
    color: #0066cc;
}
```

### Sección 4: CONCEPTO MÉDICO

```html
{% if concepto_medico %}
<div class="section">
    <div class="section-title">Concepto de Evaluación Médica</div>
    <div class="medical-concept">
        <div class="result">{{ concepto_medico }}</div>
        <div class="description">
            De acuerdo al examen ocupacional realizado a {{ nombres_apellidos }}
            con documento de identificación No {{ documento_identidad }}
            se considera que es {{ concepto_medico }} para desempeñar
            la ocupación del cargo descrito
        </div>
    </div>
</div>
{% endif %}
```

**Variable:**
| Variable | Fuente | Valores posibles |
|----------|--------|------------------|
| `concepto_medico` | PostgreSQL `mdConceptoFinal` | `APTO`, `APTO CON RESTRICCIONES`, `NO APTO`, `APLAZADO` |

**CSS:**
```css
.medical-concept {
    background: #f0f8ff;
    border: 2px solid #0066cc;
    padding: 20px;
    text-align: center;
}

.medical-concept .result {
    color: #00a651;
    font-size: 15px;
    font-weight: bold;
    text-transform: uppercase;
}
```

### Sección 5: AVISO SIN SOPORTE (Condicional)

Si la empresa no ha pagado, se muestra este aviso en lugar del concepto:

```html
{% if mostrar_sin_soporte %}
<div class="sin-soporte">
    <div class="warning-text">
        {{ texto_sin_soporte }}
    </div>
</div>
{% endif %}
```

**Lógica:**
```python
# Empresas sin soporte (muestran aviso rojo)
EMPRESAS_SIN_SOPORTE = [
    "SITEL", "KM2", "TTEC", "CP360", "SALVATECH", "PARTICULAR",
    "STORI", "OMEGA", "EVERTEC", "ZIMMER", "HUNTY", "FDN",
    "SIIGO", "RIPPLING", "RESSOLVE", "CENTRAL", "EVERTECBOGOTA",
    "ATR", "AVANTO", "HEALTHATOM"
]

# Tipos de examen que NUNCA muestran aviso
TIPOS_EXAMEN_SIN_AVISO = ["PostIncapacidad", "Post Incapacidad", "Periódico"]

def mostrar_aviso_sin_soporte(cod_empresa, tipo_examen):
    if tipo_examen in TIPOS_EXAMEN_SIN_AVISO:
        return False
    return cod_empresa in EMPRESAS_SIN_SOPORTE
```

**CSS:**
```css
.sin-soporte {
    background: #ffe6e6;
    border: 4px solid #dc3545;
    padding: 30px;
    text-align: center;
}

.sin-soporte .warning-text {
    color: #c82333;
    font-size: 18px;
    font-weight: bold;
    text-transform: uppercase;
}
```

### Sección 6: FIRMAS

```html
<div class="signatures-section">
    <div class="section-title">Firmas</div>
    <div class="signatures-container">
        <!-- Firma Médico -->
        <div class="signature-box">
            <div class="signature-header">Firma Médico</div>
            <div class="signature-line">
                {% if firma_medico_url %}
                <img src="{{ firma_medico_url }}" class="signature-img">
                {% endif %}
            </div>
            <div class="signature-name">{{ medico_nombre }}</div>
            <div class="signature-details">
                {{ medico_registro }}<br>
                {{ medico_licencia }}<br>
                {{ medico_fecha }}
            </div>
        </div>

        <!-- Firma Paciente -->
        <div class="signature-box">
            <div class="signature-header">Firma Paciente</div>
            <div class="signature-line">
                {% if firma_paciente_url %}
                <img src="{{ firma_paciente_url }}" class="signature-img">
                {% endif %}
            </div>
            <div class="signature-name">{{ nombres_apellidos }}</div>
            <div class="signature-details">{{ documento_identidad }}</div>
        </div>
    </div>
</div>
```

**Mapeo de Médicos y Firmas:**
```python
# Mapeo de médico a archivo de firma
firma_medico_map = {
    "SIXTA": "FIRMA-SIXTA.png",
    "JUAN 134": "FIRMA-JUAN134.jpeg",
    "CESAR": "FIRMA-CESAR.jpeg",
    "MARY": "FIRMA-MARY.jpeg",
    "NUBIA": "FIRMA-JUAN134.jpeg",      # Usa misma firma que JUAN 134
    "PRESENCIAL": "FIRMA-PRESENCIAL.jpeg"
}

# Datos de cada médico
medico_datos_map = {
    "SIXTA": {
        "nombre": "SIXTA VIVERO CARRASCAL",
        "registro": "REGISTRO MÉDICO NO 55300504",
        "licencia": "LICENCIA SALUD OCUPACIONAL 583",
        "fecha": "16 DE FEBRERO DE 2021"
    },
    "JUAN 134": {
        "nombre": "JUAN JOSE REATIGA",
        "registro": "CC. 7472.676 - REGISTRO MEDICO NO 14791",
        "licencia": "LICENCIA SALUD OCUPACIONAL 460",
        "fecha": "6 DE JULIO DE 2020"
    },
    "CESAR": {
        "nombre": "CÉSAR ADOLFO ZAMBRANO MARTÍNEZ",
        "registro": "REGISTRO MEDICO NO 1192803570",
        "licencia": "LICENCIA SALUD OCUPACIONAL # 3241",
        "fecha": "13 DE JULIO DE 2021"
    },
    "NUBIA": {
        "nombre": "JUAN JOSE REATIGA",
        "registro": "CC. 7472.676 - REGISTRO MEDICO NO 14791",
        "licencia": "LICENCIA SALUD OCUPACIONAL 460",
        "fecha": "6 DE JULIO DE 2020"
    },
    "PRESENCIAL": {
        "nombre": "",  # Ya está en la imagen
        "registro": "",
        "licencia": "",
        "fecha": ""
    }
}
```

**Fuente de Firma del Paciente:**
```python
# PostgreSQL: formularios.firma (Data URI base64)
firma_paciente = datos_formulario.get('firma')
# Ejemplo: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
```

### Sección 7: RESULTADOS DE OPTOMETRÍA

Solo se muestra si el paciente tiene examen de Optometría o Visiometría.

```html
{% if 'Optometría' in examenes or 'Visiometría' in examenes %}
<div class="section">
    <div class="section-title">Resultados de Optometría</div>

    {% if datos_visual %}
    <div class="result-item">
        <h3>Resultados Numéricos</h3>
        <p style="font-family: 'Courier New', monospace;">
            {{ datos_visual.resultadoNumerico }}
        </p>
    </div>

    {% if datos_visual.miopia %}
    <div class="result-item">
        <h3>Miopía</h3>
        <p>{{ datos_visual.miopia }}</p>
    </div>
    {% endif %}

    {% if datos_visual.astigmatismo %}
    <div class="result-item">
        <h3>Astigmatismo</h3>
        <p>{{ datos_visual.astigmatismo }}</p>
    </div>
    {% endif %}

    <!-- Firma del Optómetra -->
    <img src="{{ firma_optometra_url }}" class="signature-img">
    {% endif %}
</div>
{% endif %}
```

**Obtención de datos visuales:**
```python
# Endpoint Wix
visual_url = f"https://www.bsl.com.co/_functions/visualPorIdGeneral?idGeneral={wix_id}"
response = requests.get(visual_url)
datos_visual = response.json()['data'][0]

# Estructura de datos_visual:
{
    "resultadoNumerico": """
        Esfera (ESF): -1.5 dioptrías
        Cilindro (CIL): -1.25 dioptrías
        Eje (EJE): 132 grados
        Distancia Pupilar (DP): 0.40 cm
        Agudeza visual sin corrección (OD): 0.60
        Agudeza visual sin corrección (OI): 0.60
    """,
    "miopia": "si",
    "astigmatismo": "si",
    "agudezaVisual": 4,
    "snelle": 6,
    "colores": 6,
    "concepto": "Excelente"
}
```

### Sección 8: RESULTADOS DE AUDIOMETRÍA

Solo se muestra si el paciente tiene examen de Audiometría.

```html
{% if 'Audiometría' in examenes %}
<div class="section">
    <div class="section-title">Resultados de Audiometría</div>

    {% if datos_audiometria %}
    <!-- Audiograma SVG -->
    <svg width="100%" height="400" viewBox="0 0 700 400">
        <!-- Grid y ejes -->
        <!-- Puntos oído derecho (rojo) -->
        {% for dato in datos_audiometria.datosParaTabla %}
        <circle cx="{{ calcular_x(dato.frecuencia) }}"
                cy="{{ calcular_y(dato.oidoDerecho) }}"
                r="4" fill="#e74c3c"/>
        {% endfor %}
        <!-- Puntos oído izquierdo (azul) -->
        {% for dato in datos_audiometria.datosParaTabla %}
        <circle cx="{{ calcular_x(dato.frecuencia) }}"
                cy="{{ calcular_y(dato.oidoIzquierdo) }}"
                r="4" fill="#3498db"/>
        {% endfor %}
    </svg>

    <!-- Tabla de valores -->
    <table class="audio-table">
        <tr>
            <th>Hz</th>
            {% for dato in datos_audiometria.datosParaTabla %}
            <th>{{ dato.frecuencia }}</th>
            {% endfor %}
        </tr>
        <tr>
            <td>OD</td>
            {% for dato in datos_audiometria.datosParaTabla %}
            <td>{{ dato.oidoDerecho }}</td>
            {% endfor %}
        </tr>
        <tr>
            <td>OI</td>
            {% for dato in datos_audiometria.datosParaTabla %}
            <td>{{ dato.oidoIzquierdo }}</td>
            {% endfor %}
        </tr>
    </table>

    <!-- Diagnóstico -->
    <div class="result-item">
        <h3>Diagnóstico</h3>
        <p>{{ datos_audiometria.diagnostico }}</p>
    </div>
    {% endif %}
</div>
{% endif %}
```

**Obtención y transformación de datos de audiometría:**
```python
# Endpoint Wix
audio_url = f"https://www.bsl.com.co/_functions/audiometriaPorIdGeneral?idGeneral={wix_id}"
response = requests.get(audio_url)
datos_raw = response.json()['data'][0]

# Datos crudos de Wix:
# {
#     "auDer250": 10, "auIzq250": 10,
#     "auDer500": 10, "auIzq500": 10,
#     "auDer1000": 10, "auIzq1000": 10,
#     "auDer2000": 10, "auIzq2000": 10,
#     "auDer3000": 10, "auIzq3000": 10,
#     "auDer4000": 70, "auIzq4000": 10,  # Pérdida en 4000Hz OD
#     "auDer6000": 10, "auIzq6000": 10,
#     "auDer8000": 10, "auIzq8000": 10
# }

# Transformación a formato de tabla:
frecuencias = [250, 500, 1000, 2000, 3000, 4000, 6000, 8000]
datosParaTabla = []

for freq in frecuencias:
    datosParaTabla.append({
        "frecuencia": freq,
        "oidoDerecho": datos_raw.get(f"auDer{freq}", 0),
        "oidoIzquierdo": datos_raw.get(f"auIzq{freq}", 0)
    })

# Calcular diagnóstico automático
def calcular_diagnostico(datos):
    # Promedio de frecuencias conversacionales (500, 1000, 2000 Hz)
    valores_der = [d['oidoDerecho'] for d in datos if d['frecuencia'] in [500, 1000, 2000]]
    valores_izq = [d['oidoIzquierdo'] for d in datos if d['frecuencia'] in [500, 1000, 2000]]

    prom_der = sum(valores_der) / len(valores_der)
    prom_izq = sum(valores_izq) / len(valores_izq)

    if prom_der <= 25 and prom_izq <= 25:
        return "Audición dentro de parámetros normales bilateralmente"
    elif prom_der > 25 and prom_izq <= 25:
        return "Hipoacusia oído derecho"
    # ... más clasificaciones

datos_audiometria = {
    "datosParaTabla": datosParaTabla,
    "diagnostico": calcular_diagnostico(datosParaTabla)
}
```

---

## Resumen de Campos por Fuente

### Tabla: HistoriaClinica (PostgreSQL)

| Campo BD | Variable Template | Descripción |
|----------|-------------------|-------------|
| `_id` | `wix_id` | Identificador único |
| `numeroId` | `documento_identidad` | Cédula |
| `primerNombre` | parte de `nombres_apellidos` | Primer nombre |
| `segundoNombre` | parte de `nombres_apellidos` | Segundo nombre |
| `primerApellido` | parte de `nombres_apellidos` | Primer apellido |
| `segundoApellido` | parte de `nombres_apellidos` | Segundo apellido |
| `empresa` | `empresa` | Nombre empresa |
| `codEmpresa` | usado para lógica | Código empresa |
| `cargo` | `cargo` | Cargo del empleado |
| `tipoExamen` | `tipo_examen` | Tipo de examen |
| `examenes` | `examenes_realizados` | Lista de exámenes |
| `mdConceptoFinal` | `concepto_medico` | Concepto final |
| `mdObservacionesCertificado` | `observaciones` | Observaciones |
| `mdRecomendacionesMedicasAdicionales` | `recomendaciones_medicas` | Recomendaciones |
| `fechaConsulta` | `fecha_atencion` | Fecha de atención |
| `medico` | usado para mapear firma | Médico asignado |
| `ciudad` | `ciudad` | Ciudad de atención |

### Tabla: formularios (PostgreSQL)

| Campo BD | Variable Template | Descripción |
|----------|-------------------|-------------|
| `foto_url` | `foto_paciente` | URL foto (prioridad) |
| `foto` | `foto_paciente` | Foto base64 (fallback) |
| `firma` | `firma_paciente_url` | Firma del paciente |
| `edad` | `edad` | Edad |
| `genero` | `genero` | Género |
| `estado_civil` | `estado_civil` | Estado civil |
| `hijos` | `hijos` | Número de hijos |
| `profesion_oficio` | `profesion` | Profesión |
| `fecha_nacimiento` | `fecha_nacimiento` | Fecha nacimiento |
| `eps` | `eps` | EPS |
| `arl` | `arl` | ARL |
| `pensiones` | `pensiones` | Fondo pensiones |
| `nivel_educativo` | `nivel_educativo` | Nivel educativo |

### Wix HTTP Functions

| Endpoint | Variable Template | Descripción |
|----------|-------------------|-------------|
| `visualPorIdGeneral` | `datos_visual` | Resultados optometría |
| `audiometriaPorIdGeneral` | `datos_audiometria` | Resultados audiometría |

---

## Referencias

- [Puppeteer Documentation](https://pptr.dev/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Jinja2 Templates](https://jinja.palletsprojects.com/)
