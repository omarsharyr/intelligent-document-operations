# Intelligent Document Operations & RAG Agent

Phase 1: local PDF ingestion and text extraction only. Python 3.11+.

## Run in Windows PowerShell

From the repository root:

```powershell
Set-Location F:\projects\intelligent-document-operations
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

Open Swagger: http://127.0.0.1:8000/docs
Health: http://127.0.0.1:8000/health

No virtual environment activation is needed. Run from the root so `.env` and relative storage paths resolve consistently. `MAX_UPLOAD_SIZE_MB` uses MiB (1024 squared bytes). The default limit is 20 MiB.

## Manual test

1. In Swagger, expand `POST /api/v1/documents/upload`, select **Try it out**, choose a PDF and execute.
2. Expect HTTP 201. Copy `document_id` from the metadata response.
3. Expand `POST /api/v1/documents/{document_id}/process`, select **Try it out**, paste that UUID and execute.
4. Expect page count, normalized character count and `processed`. An image-only or textless PDF returns `OCR_REQUIRED`; OCR is deferred. No extracted text is returned.
5. Try a text file, an empty PDF upload and a corrupted PDF to inspect errors. PDF validity and password protection are checked during processing; upload validates name, extension, declared MIME and size.

Alternatively, in another PowerShell window:

```powershell
$upload = curl.exe -s -F "file=@C:/path/to/policy.pdf;type=application/pdf" http://127.0.0.1:8000/api/v1/documents/upload | ConvertFrom-Json
$upload
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/documents/$($upload.document_id)/process"
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini -q
```

Tests generate PDFs in memory and use pytest temporary directories; they do not write into project document storage.

## Architecture

`app.main` builds the application and injects configuration and services. Routes only invoke the document service. Upload validation and processing orchestration live in `services/documents.py`. The `DocumentStorage` protocol exposes save/read, with an atomic local filesystem implementation. A future storage provider can be injected through `create_app(storage=...)` without changing routes or parsing logic. The PDF service extracts numbered pages into Pydantic models and conservatively normalizes whitespace. Character count is the sum of normalized page text lengths, without adding page separators. No alphanumeric text on any page means `OCR_REQUIRED`; this is a heuristic, not OCR or per-page scan classification. Mixed PDFs currently report `processed` if any page has text.

Expected errors have stable codes and safe messages. Unexpected errors return a generic HTTP 500. The application never logs document contents. Process results are computed on demand and are not persisted; documents remain readable after restart because storage keys are UUID filenames.

Storage is a trusted, application-controlled directory. Upload reads are bounded, but the multipart parser may spool requests before service validation; public deployment will need a request-size limit at its ingress and authentication in a later phase. Processing runs in FastAPI's thread pool. Phase 1 does not include OCR, databases, retrieval, authentication, automation or agents.

## Docker

```powershell
docker compose up --build
```

The backend runs as a non-root user and stores PDFs in a named volume. No n8n or dashboard runtime is included. Docker files are provided; container execution requires Docker Desktop.

## Repository hygiene

`.env`, virtual environments, PDF files, caches, temporary runtime files and storage contents are ignored. `.env.example` and empty storage directory markers are tracked. Never place credentials in source files. The n8n, dashboard, sample-data and index directories are reserved directory markers only; future-phase Python packages are intentionally absent.
