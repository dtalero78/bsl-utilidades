# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based PDF generation and management service that supports multiple companies (BSL and LGS). The application converts web pages to PDFs using API2PDF and uploads them to various cloud storage destinations (Google Drive, Google Cloud Storage).

## Architecture

The application is built around a multi-tenant architecture supporting different companies with distinct configurations:

- **Company Detection**: Uses HTTP headers (Origin, Referer) and request parameters to determine which company configuration to use
- **PDF Generation**: Converts company-specific web pages to PDFs using API2PDF service with tailored selectors and formatting options
- **Storage Flexibility**: Supports three storage backends - Google Drive (service account), Google Drive (OAuth), and Google Cloud Storage
- **CORS Configuration**: Handles cross-origin requests for specific company domains

### Core Components

- `descargar_bsl.py` - Main Flask application with all endpoints
- `drive_uploader.py` - Google Drive service account integration  
- `upload_to_drive_oauth.py` - Google Drive OAuth integration
- `gcs_uploader.py` - Google Cloud Storage integration
- `static/index.html` - Frontend for direct PDF download

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
- `API2PDF_KEY` - API2PDF service key
- `GOOGLE_CREDENTIALS_BASE64` - Base64 encoded Google service account JSON
- `GOOGLE_DRIVE_FOLDER_ID_BSL` - BSL company folder ID
- `GOOGLE_DRIVE_FOLDER_ID_LGS` - LGS company folder ID  
- `STORAGE_DESTINATION` - Storage backend: "drive", "drive-oauth", or "gcs"

For RIPPLING company (special case):
- `GOOGLE_DRIVE_FOLDER_ID_RIPPLING_INGRESO`
- `GOOGLE_DRIVE_FOLDER_ID_RIPPLING_PERIODICO`

For OAuth mode:
- `GOOGLE_OAUTH_CREDENTIALS_BASE64`
- `GOOGLE_OAUTH_TOKEN_B64`
- `GOOGLE_OAUTH_TOKEN_FILE`

### Deployment

The application is configured for Heroku deployment:
- `Procfile` specifies the web process
- Uses port 8080 by default
- Environment variables must be set in hosting platform

### Quick Commands (from GALLETICAS.txt)

```bash
# Commit changes
git add .
git commit -m "multiempresas desde claude"
git push

# Create deployment package
zip -r bot_bsl.zip . -x "node_modules/*" "__pycache__/*" ".git/*" "*.pyc" "*.log"
```

## API Endpoints

### PDF Generation Endpoints
- `POST /generar-pdf` - Generate PDF and upload to storage
- `POST /subir-pdf-directo` - Upload existing PDF URL to storage
- `GET|POST /descargar-pdf-empresas` - Generate and directly download PDF
- `GET /descargar-pdf-drive/<documento>` - Download PDF from Google Drive
- `GET /` - Serve frontend interface

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