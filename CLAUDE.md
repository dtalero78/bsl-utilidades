# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based PDF generation and management service with three main capabilities:
1. **Multi-tenant PDF generation** - Converts company-specific web pages to PDFs (BSL, LGS)
2. **Medical certificate generation** - Creates and manages occupational health certificates with QR validation
3. **CSV processing** - Bulk processes patient scheduling data with intelligent assignment logic

The application uses API2PDF and iLovePDF for PDF generation, with flexible cloud storage (Google Drive, Google Cloud Storage).

## Architecture

The application is built around a multi-tenant architecture supporting different companies with distinct configurations:

- **Company Detection**: Uses HTTP headers (Origin, Referer) and request parameters to determine which company configuration to use
- **PDF Generation**: Converts company-specific web pages to PDFs using API2PDF service with tailored selectors and formatting options
- **Storage Flexibility**: Supports three storage backends - Google Drive (service account), Google Drive (OAuth), and Google Cloud Storage
- **CORS Configuration**: Handles cross-origin requests for specific company domains

### Core Components

- `descargar_bsl.py` - Main Flask application with all endpoints (~2500 lines)
- `drive_uploader.py` - Google Drive service account integration
- `upload_to_drive_oauth.py` - Google Drive OAuth integration
- `gcs_uploader.py` - Google Cloud Storage integration
- `templates/certificado_medico.html` - Jinja2 template for medical certificates
- `templates/certificado_loader.html` - Loading page for certificate generation
- `static/index.html` - Frontend for direct PDF download
- `static/procesar-csv.html` - CSV processing interface
- `test_generar_certificado.py` - Test script for certificate generation

### Company Configuration Structure

Each company has specific settings in `EMPRESA_CONFIG`:
- Domain and URL path structure
- PDF generation selectors (for LGS only)
- Google Drive folder IDs
- CORS allowed origins

## Development Commands

### Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python descargar_bsl.py

# Run on specific port (production uses 8080)
python descargar_bsl.py --port 8080
```

### Environment Setup

Required environment variables in `.env`:

**PDF Generation:**
- `API2PDF_KEY` - API2PDF service key for web page to PDF conversion
- `ILOVEPDF_PUBLIC_KEY` - iLovePDF public key for medical certificate HTML to PDF conversion
- `ILOVEPDF_SECRET_KEY` - iLovePDF secret key (optional, not actively used)

**Google Drive/Cloud Storage:**
- `GOOGLE_CREDENTIALS_BASE64` - Base64 encoded Google service account JSON
- `GOOGLE_DRIVE_FOLDER_ID_BSL` - BSL company folder ID
- `GOOGLE_DRIVE_FOLDER_ID_LGS` - LGS company folder ID
- `GOOGLE_DRIVE_FOLDER_ID_TTEC` - TTEC company folder ID
- `STORAGE_DESTINATION` - Storage backend: "drive", "drive-oauth", or "gcs"

**Special Company Folders:**
- `GOOGLE_DRIVE_FOLDER_ID_RIPPLING_INGRESO` - RIPPLING intake exams
- `GOOGLE_DRIVE_FOLDER_ID_RIPPLING_PERIODICO` - RIPPLING periodic exams

**OAuth Mode (optional):**
- `GOOGLE_OAUTH_CREDENTIALS_BASE64`
- `GOOGLE_OAUTH_TOKEN_B64`
- `GOOGLE_OAUTH_TOKEN_FILE`

**Development Mode:**
- Set `GOOGLE_CREDENTIALS_BASE64=dummy-credentials` to run without real Google credentials

### Deployment

The application is configured for Heroku deployment:
- `Procfile` specifies the web process
- Uses port 8080 by default
- Environment variables must be set in hosting platform

### Testing

```bash
# Test medical certificate generation
python test_generar_certificado.py

# Manual endpoint testing with curl
curl -X POST http://localhost:8080/generar-certificado-medico \
  -H "Content-Type: application/json" \
  -d @test_data.json

# Test CSV processing
# Use the web interface at http://localhost:8080/static/procesar-csv.html
```

### Quick Commands

```bash
# Commit and deploy
git add .
git commit -m "description of changes"
git push

# Create deployment package
zip -r bot_bsl.zip . -x "node_modules/*" "__pycache__/*" ".git/*" "*.pyc" "*.log"
```

## API Endpoints

### PDF Generation Endpoints (Multi-tenant)
- `POST /generar-pdf` - Generate PDF from company URL and upload to storage
  - Detects company from Origin/Referer headers or JSON body
  - Uses API2PDF for HTML to PDF conversion
  - Returns Drive link and file metadata
- `POST /subir-pdf-directo` - Upload existing PDF URL to storage
- `GET|POST /descargar-pdf-empresas` - Generate and directly download PDF
- `GET /descargar-pdf-drive/<documento>` - Download PDF from Google Drive
- `GET /` - Serve frontend interface

### Medical Certificate Endpoints
- `POST /generar-certificado-medico` - Generate occupational health certificate
  - Accepts patient data, exam results, medical concept
  - Renders HTML template with Jinja2 (`templates/certificado_medico.html`)
  - Converts to PDF using iLovePDF API
  - Generates unique security code and QR validation
  - Conditionally hides medical results for unpaid companies (see `EMPRESAS_SIN_SOPORTE`)
  - Optionally uploads to Google Drive
  - Returns: `{success, pdf_url, codigo_seguridad, drive_web_link}`
- `GET /generar-certificado-desde-wix/<wix_id>` - Show loader page while generating
  - Serves `certificado_loader.html` with animated BSL logo
  - Polls `/api/generar-certificado-pdf/<wix_id>` for completion
- `GET /api/generar-certificado-pdf/<wix_id>` - Backend PDF generation for Wix
  - Fetches patient data from Wix API
  - Generates certificate and returns PDF URL
- `GET /preview-certificado-html/<wix_id>` - Preview certificate HTML (debugging)
- `GET /images/<filename>` - Serve public images (logos, signatures, QR codes)

### CSV Processing Endpoint
- `POST /procesar-csv` - Process CSV files with person data
  - Separates full names into components (first name, second name, first surname, second surname)
  - Extracts fields: numeroId, cargo, celular, ciudad, tipoExamen
  - Assigns scheduling data: fechaAtencion (date), horaAtencion (time), medico (doctor)
  - Returns JSON with processed data
  - Web interface available at `/static/procesar-csv.html`

All endpoints support CORS for company-specific domains and include proper error handling with detailed logging.

## Company-Specific Behavior

### BSL Company
- Captures full web page as PDF
- Uses domain: `https://www.bsl.com.co`
- Path pattern: `/descarga-whp/{documento}`

### LGS Company  
- Uses CSS selector `#text1` to capture specific PDF embed element
- Uses domain: `https://www.lgsplataforma.com`
- Path pattern: `/contrato-imprimir/{documento}?forReview=`
- Includes specific PDF formatting options (scale, margins, delays)

### RIPPLING Company (Special Case)
- Dynamically routes to different folders based on `tipoExamen` parameter
- Supports "ingreso" and "periódico" exam types
- Different Google Drive folders for each exam type

### TTEC Company
- Has dedicated Google Drive folder (`GOOGLE_DRIVE_FOLDER_ID_TTEC`)

## Medical Certificate Feature

### Overview
The medical certificate system generates PDF certificates for occupational health exams with the following features:
- **QR Code Validation**: Each certificate includes a QR code linking to validation URL
- **Conditional Content Display**: Companies without payment support see limited information
- **Professional Layout**: Three-column header with logo, company info, and QR code
- **Digital Signatures**: Embedded signature images for medical professionals

### Payment Support Logic

The system conditionally displays medical results based on company payment status:

**Companies Without Support** (`EMPRESAS_SIN_SOPORTE`):
- List includes: CAYENA, SITEL, KM2, TTEC, CP360, SALVATECH, PARTICULAR, STORI, OMEGA, EVERTEC, ZIMMER, HUNTY, FDN, SIIGO, RIPPLING, RESSOLVE, CENTRAL, EVERTECBOGOTA, ATR, AVANTO, RICOH, HEALTHATOM, TAMESIS
- Also includes any 6+ digit numeric company codes
- Shows red warning: "Este certificado se emite sin soporte de pago"
- Hides: Medical concept, detailed results, and signature sections

**Exam Types Never Showing Warning**:
- PostIncapacidad / Post Incapacidad
- Periódico

**Implementation**:
- Function `es_empresa_sin_soporte()` checks company code
- Function `determinar_mostrar_sin_soporte()` evaluates payment display logic
- Template `certificado_medico.html` uses `mostrar_sin_soporte` flag

### Certificate Generation Flow
1. Receive patient data via POST to `/generar-certificado-medico`
2. Render Jinja2 template with patient data and exam results
3. Save HTML to temporary file
4. Call iLovePDF API to convert HTML to PDF
5. Generate unique security code (UUID4)
6. Create QR code with validation URL
7. Optionally upload PDF to Google Drive
8. Return PDF URL and security code to client

## CSV Processing Feature

### Overview
The CSV processing endpoint (`/procesar-csv`) provides intelligent parsing and enrichment of person data from CSV files, primarily used for medical examination scheduling.

### Input CSV Format

**Required Columns:**
- `NOMBRES APELLIDOS Y` (or `NOMBRES COMPLETOS` or `NOMBRES Y APELLIDOS`) - Full name to be separated
- `No IDENTIFICACION` - ID number
- `CARGO` - Position/job title
- `TELEFONOS` - Phone number
- `CIUDAD` - City
- `TIPO DE EXAMEN OCUPACIONAL` - Type of occupational exam (optional)

**Note:** Column names are normalized (trimmed of leading/trailing spaces) for flexibility.

### Name Separation Logic

Full names are automatically split into components using the `separar_nombre_completo()` function:

- **1 word**: Treated as first name only
- **2 words**: First name + First surname
- **3 words**: First name + Second name + First surname
- **4+ words**: First name + Second name + First surname + Second surname

Examples:
- `JUAN PEREZ` → primerNombre: "JUAN", primerApellido: "PEREZ"
- `MARIA FERNANDA RODRIGUEZ` → primerNombre: "MARIA", segundoNombre: "FERNANDA", primerApellido: "RODRIGUEZ"
- `JUAN CARLOS PEREZ GOMEZ` → All four fields populated

### Automatic Field Assignment

The endpoint automatically assigns:

1. **ciudad**: All variations of "Bogotá" (Bogotá, bogotá, Bogota, bogota, BOGOTA, etc.) are normalized to "BOGOTA" in uppercase
2. **fechaAtencion**: Default is tomorrow (current date + 1 day), format: YYYY-MM-DD
3. **horaAtencion**:
   - For BOGOTA: Fixed at 07:00
   - For other cities: Starts at 08:00, increments by 10 minutes per record (08:00, 08:10, 08:20, etc.)
4. **medico**:
   - For BOGOTA: Always assigned to PRESENCIAL (excluded from round-robin counter)
   - For other cities: Round-robin distribution among available doctors:
     - SIXTA
     - JUAN 134
     - CESAR
     - MARY
     - NUBIA
     - PRESENCIAL
   - **Important**: The round-robin counter only increments for non-BOGOTA records, ensuring equitable distribution
5. **atendido**: Always initialized to "PENDIENTE"
6. **codEmpresa**: Empty string by default, set via global input field
7. **empresa**: Empty string by default, set via global input field
8. **examen**: Empty array by default, set via global checkbox tags

### Automatic Sorting

Records are automatically sorted with two levels:
1. **Primary**: BOGOTA first, then other cities
2. **Secondary**: By appointment time (horaAtencion) from earliest to latest

This ensures BOGOTA records appear first, ordered by time (07:00), followed by other cities ordered by their appointment times. This happens during CSV processing in the backend.

### Output Format

Returns JSON with:
```json
{
  "success": true,
  "total_registros": 5,
  "message": "CSV procesado exitosamente. 5 registros encontrados.",
  "datos": [
    {
      "fila": 1,
      "nombreCompleto": "JUAN CARLOS PEREZ GOMEZ",
      "primerNombre": "JUAN",
      "segundoNombre": "CARLOS",
      "primerApellido": "PEREZ",
      "segundoApellido": "GOMEZ",
      "numeroId": "1234567890",
      "cargo": "Ingeniero de Sistemas",
      "celular": "3001234567",
      "ciudad": "BOGOTA",
      "tipoExamen": "PRE INGRESO",
      "fechaAtencion": "2025-10-20",
      "horaAtencion": "07:00",
      "medico": "PRESENCIAL",
      "atendido": "PENDIENTE",
      "codEmpresa": "EMP001",
      "empresa": "Acme Corporation",
      "examen": ["Examen Médico Osteomuscular", "Audiometría"]
    }
  ]
}
```

**Note**: Records are sorted with BOGOTA first (by time), then other cities (by time from earliest to latest).

**Example sort order and doctor distribution:**
```
CSV Input: 10 records total (3 BOGOTA, 7 others)

Output after processing:
1. BOGOTA - 07:00 - PRESENCIAL  (not counted in round-robin)
2. BOGOTA - 07:00 - PRESENCIAL  (not counted in round-robin)
3. BOGOTA - 07:00 - PRESENCIAL  (not counted in round-robin)
4. Cali - 08:00 - SIXTA         (round-robin index 0)
5. Medellín - 08:10 - JUAN 134  (round-robin index 1)
6. Barranquilla - 08:20 - CESAR (round-robin index 2)
7. Cúcuta - 08:30 - MARY        (round-robin index 3)
8. Pereira - 08:40 - NUBIA      (round-robin index 4)
9. Cartagena - 08:50 - PRESENCIAL (round-robin index 5)
10. Bucaramanga - 09:00 - SIXTA  (round-robin index 6, wraps around)
```

**Note**: BOGOTA records are excluded from the round-robin counter, ensuring equitable distribution only among non-BOGOTA records.

### Web Interface Features

The web interface (`/static/procesar-csv.html`) provides:

**Global Controls:**
- **Código Empresa** input: Set company code for all records
- **Nombre Empresa** input: Set company name for all records
- **Exámenes** tags: Select which exams apply to all records (Examen Médico Osteomuscular, Audiometría, Optometría, SCL-90)
- **Date selector**: Change all appointment dates at once
- **Time selector**: Set initial time (auto-increments 10 min per record for non-BOGOTA cities)
- **Doctor tags**: Select which doctors to include in distribution (respects BOGOTA = PRESENCIAL rule)

**Individual Editing:**
- Each record's date, time, and assigned doctor can be edited directly in the table
- Changes are reflected in the downloadable JSON
- Manual edits are preserved when changing doctor tags

**Special Rules:**
- BOGOTA records (normalized from any variation: Bogotá, BOGOTÁ, Bogota, BOGOTA, bogota, etc.):
  - Ciudad field is always normalized to "BOGOTA" (uppercase)
  - Always assigned to PRESENCIAL médico
  - Always use 07:00 as horaAtencion
  - These rules apply both on initial load and when redistributing via doctor tags

**Table Display:**
- Full-screen responsive layout
- **Column Headers** (as displayed in the table):
  - primerNombre, segundoNombre, primerApellido, segundoApellido
  - numeroId, cargo, celular, ciudad, tipoExamen
  - Fecha Atención (editable input)
  - Hora Atención (editable input)
  - **fechaAtencion** (MM/DD/YYYY HH:MM format) - auto-updates when fecha or hora changes
  - medico (click-to-edit modal, displays as plain text for Excel copy compatibility)
  - atendido (always "PENDIENTE")
  - codEmpresa (set via global input)
  - empresa (set via global input)
  - examenes (array of selected exams, set via global tags)
- **Records are automatically sorted**: BOGOTA records appear first (ordered by time), followed by other cities (ordered by time from earliest to latest)

**Excel Copy-Paste Compatibility:**
- **medico** field displays as plain text using a modal selector (no inline dropdown to avoid copy issues)
- **fechaAtencion** field is plain text (copies correctly to Excel as MM/DD/YYYY HH:MM format)
- Click on medico cell to open modal for editing
- All fields copy cleanly to Excel without extra HTML elements

**Display:**
- JSON download functionality
- Real-time updates when using global controls

### Use Cases

1. **Medical Examination Scheduling**: Automatically distribute patients among available doctors
2. **Appointment Management**: Batch schedule appointments with automatic time slots
3. **Data Enrichment**: Take basic person data and add scheduling information
4. **Name Normalization**: Standardize full names into separate fields for database storage

---

## CSV Processing Technical Summary

### Backend Processing (Python - descargar_bsl.py)
1. **City Normalization**: All Bogotá variations → "BOGOTA" (uppercase)
2. **Automatic Sorting**: Two-level sort
   - Primary: BOGOTA first, then other cities
   - Secondary: By horaAtencion (earliest to latest)
3. **Doctor Assignment**:
   - BOGOTA → PRESENCIAL (excluded from round-robin count)
   - Others → round-robin distribution (SIXTA, JUAN 134, CESAR, MARY, NUBIA, PRESENCIAL)
   - **Important**: BOGOTA records don't count in the round-robin distribution
4. **Time Assignment**:
   - BOGOTA → 07:00 (fixed)
   - Others → 08:00 + (10 min increments per non-BOGOTA record)

### Frontend Features (static/procesar-csv.html)
1. **Global Controls**:
   - codEmpresa, empresa (text inputs)
   - examenes (multi-select checkboxes)
   - Date/time selectors
   - Doctor distribution tags
2. **Table Columns**: primerNombre, segundoNombre, primerApellido, segundoApellido, numeroId, cargo, celular, ciudad, tipoExamen, Fecha Atención, Hora Atención, fechaAtencion, medico, atendido, codEmpresa, empresa, examenes
3. **Copy-Paste Optimization**: Modal selector for medico field (avoids inline HTML in clipboard)
4. **Live Updates**: All global controls update all records in real-time

### Data Flow
CSV Upload → Backend Processing → Normalization + Sorting → Frontend Display → User Edits → JSON Download

---

## Key Architecture Patterns

### Multi-Service PDF Generation
The application uses two different PDF generation services based on use case:
- **API2PDF**: For converting live web pages to PDF (company documents)
  - Uses Chrome headless browser
  - Supports CSS selectors for partial page capture
  - Configured per-company with delays, margins, scale
- **iLovePDF**: For converting static HTML templates to PDF (medical certificates)
  - Receives pre-rendered HTML from Flask
  - Better for template-based documents
  - Function: `ilovepdf_html_to_pdf_from_url()`

### Storage Abstraction Layer
Storage destination is determined by `STORAGE_DESTINATION` environment variable:
- `"drive"`: Uses service account (`drive_uploader.py`)
- `"drive-oauth"`: Uses OAuth tokens (`upload_to_drive_oauth.py`)
- `"gcs"`: Uses Google Cloud Storage (`gcs_uploader.py`)

Each storage module exports a `subir_pdf_a_*` function with the same signature, allowing the main application to remain agnostic of the storage backend.

### Company Detection Strategy
The `determinar_empresa()` function uses a priority chain:
1. **JSON body parameter** - Explicit `empresa` field
2. **Origin header** - Domain-based detection
3. **Referer header** - Fallback domain detection
4. **Default** - BSL for backward compatibility

This allows the same endpoint to serve multiple tenants without separate deployments.

### Template Rendering with Conditional Logic
Medical certificates use Jinja2 templates with complex conditional rendering:
- `mostrar_sin_soporte` flag controls content visibility
- Patient photo is optional (shows placeholder if missing)
- QR code is dynamically generated with base64 embedding
- Signature images are conditionally displayed

Key template variables: `nombres_apellidos`, `documento_identidad`, `cargo`, `empresa`, `concepto_medico`, `examenes_realizados`, `resultados_generales`, `medico_nombre`, `codigo_seguridad`, `qr_code_base64`