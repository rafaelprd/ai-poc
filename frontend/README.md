# Financeiro Frontend

Vue 3 + Vite frontend for `SPEC1` ingestion and `SPEC2` categorization.

## Run

### 1) Install deps

```bash
cd frontend
npm install
```

### 2) Start dev server

```bash
npm run dev
```

Default Vite port: `5173`

## API target

Frontend calls backend through Vite proxy at `/api`.

If backend runs on another origin, set:

```bash
VITE_API_TARGET=http://localhost:8000
```

Example:

```bash
set VITE_API_TARGET=http://localhost:8000
npm run dev
```

Or use:

```bash
VITE_API_BASE=http://localhost:8000/api/v1
```

## Features

### SPEC1 — Ingestion
- Upload CSV and PDF files
- View batch list
- Open batch detail
- Watch processing status
- Inspect row-level parse errors

### SPEC2 — Categorization
- Create, edit, delete categories
- Create, edit, delete rules
- List transactions
- Inline category edit
- Bulk category apply
- Run auto-categorization

## Build

```bash
npm run build
```

## Notes
- Backend must be running
- System category `Uncategorized` is protected
- Manual transaction edits stay manual on full categorization run
- Bulk apply uses `POST /api/v1/transactions/categorize-bulk`
