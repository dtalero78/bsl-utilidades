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

1. **fechaAtencion**: Default is tomorrow (current date + 1 day), format: YYYY-MM-DD
2. **horaAtencion**: Starts at 08:00, increments by 10 minutes per record (08:00, 08:10, 08:20, etc.)
3. **medico**: Round-robin distribution among available doctors:
   - SIXTA
   - JUAN 134
   - CESAR
   - MARY
   - NUBIA

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
      "ciudad": "Bogotá",
      "tipoExamen": "PRE INGRESO",
      "fechaAtencion": "2025-10-19",
      "horaAtencion": "08:00",
      "medico": "SIXTA"
    }
  ]
}
```

### Web Interface Features

The web interface (`/static/procesar-csv.html`) provides:

**Global Controls:**
- Date selector: Change all appointment dates at once
- Time selector: Set initial time (auto-increments 10 min per record)
- Doctor tags: Select which doctors to include in distribution

**Individual Editing:**
- Each record's date, time, and assigned doctor can be edited directly in the table
- Changes are reflected in the downloadable JSON

**Display:**
- Full-screen responsive layout
- Editable table with all fields
- JSON download functionality
- Real-time updates when using global controls

### Use Cases

1. **Medical Examination Scheduling**: Automatically distribute patients among available doctors
2. **Appointment Management**: Batch schedule appointments with automatic time slots
3. **Data Enrichment**: Take basic person data and add scheduling information
4. **Name Normalization**: Standardize full names into separate fields for database storage