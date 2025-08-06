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

- `POST /generar-pdf` - Generate PDF and upload to storage
- `POST /subir-pdf-directo` - Upload existing PDF URL to storage  
- `GET|POST /descargar-pdf-empresas` - Generate and directly download PDF
- `GET /descargar-pdf-drive/<documento>` - Download PDF from Google Drive
- `GET /` - Serve frontend interface

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