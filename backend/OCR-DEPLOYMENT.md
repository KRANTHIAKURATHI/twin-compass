# Clinical document OCR — deployment

Engine: **Tesseract 5.x** (LSTM) through `pytesseract`, `Pillow`, `PyMuPDF`. `pytesseract` is only a wrapper; the
**Tesseract executable (plus `eng` language data) must exist on the host**. Without it `POST /ocr/{id}/extract`
returns 502 "Tesseract OCR engine was not found" and persists nothing.

## Settings (env / `app.core.config`)
`TESSERACT_CMD` (optional path; otherwise `tesseract` on PATH), `OCR_LANGUAGE=eng`, `OCR_MAX_PAGES=20`,
`OCR_MIN_TEXT_CHARS_PER_PAGE=40`, `OCR_PROVIDER=tesseract`.

## Local
* Windows: install Tesseract 5.x (e.g. UB-Mannheim build) and set `TESSERACT_CMD` to `tesseract.exe` if not on PATH.
* Debian/Ubuntu: `apt-get install tesseract-ocr tesseract-ocr-eng`. macOS: `brew install tesseract`.

## Render
Render's native Python runtime has a read-only system image: `apt-get` is **not available** in the build command, so a
pip package cannot provide the binary. Options:
1. **Docker runtime (recommended, only reliable option)**: `backend/Dockerfile` (python:3.12-slim-bookworm) installs
   `tesseract-ocr` + `tesseract-ocr-eng` via apt, then `pip install -r requirements.txt`, and starts
   `uvicorn app.main:app` on `$PORT`. Point the Render service at the `backend` directory with the Docker runtime and
   set `OCR_PROVIDER=tesseract` (also the image default).
2. Native runtime: not supported unless a Tesseract binary is vendored into the build output and `TESSERACT_CMD` points
   to it (also needs `TESSDATA_PREFIX`); not recommended.

## Data handling
Uploaded documents are streamed from private storage into memory only; nothing is written to disk. Raw OCR text is
**not stored** (no safe schema column) — only parsed fields and their Tesseract confidence. Nothing is logged.

## Migration
`supabase/migrations/20261007121000_create_ocr_extractions.sql` must be applied before production OCR testing
(`ocr_extractions` / `ocr_extraction_fields` do not exist in the live database yet).
