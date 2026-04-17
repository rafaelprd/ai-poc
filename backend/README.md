# Ingestion Backend

FastAPI backend for `SPEC1_Ingestion`.

## Run

### 1) Install deps
```bash
pip install -r backend/requirements.txt
```

### 2) Start app
```bash
uvicorn backend.app:app --reload
```

### 3) Default storage
- DB: `backend/financeiro.db` if `DATABASE_URL` not set
- Uploads: `backend/uploads/`

## Env

- `DATABASE_URL` — Postgres or SQLite URL
- `UPLOAD_DIR` — optional upload root if you change file storage

## Notes

- Accepts `multipart/form-data`
- File field: `files`
- Optional form field: `account_id`
- Max files per request: `20`
- Max file size: `10 MB`
- Only `CSV` and `PDF`
- Hash dedup: same transaction hash skipped

## Endpoints

- `POST /api/v1/ingestion/upload`
- `GET /api/v1/ingestion/batches/{batch_id}`
- `GET /api/v1/ingestion/batches/{batch_id}/errors`
- `GET /api/v1/ingestion/batches`

## Status flow

- Batch: `processing` → `completed | partial_failure | failed`
- File: `queued` → `processing` → `completed | failed`

## Dev caveat

PDF parse needs `pdfplumber`.
CSV parse needs plain text file with header row.