# SPEC1 — Data Ingestion

> Technical Specification for PRD 1 — Data Ingestion

**Status:** Draft
**Last Updated:** 2025-07-10
**Related PRDs:** PRD1_Ingestion, PRD6_Import (deduplication referenced)

---

## 1. Overview

The Data Ingestion module allows users to upload financial documents (CSV and PDF), parse them into structured transaction records, normalize the data, and persist it to PostgreSQL. The pipeline is **batch-oriented** and **idempotent** — re-uploading the same file must not create duplicate transactions.

### Scope

| In Scope | Out of Scope |
|---|---|
| File upload (CSV, PDF) | OFX/QIF formats (future) |
| CSV parsing & column mapping | Manual transaction entry |
| PDF table extraction | OCR for scanned/image PDFs |
| Data normalization | Categorization (see SPEC2) |
| Validation & error reporting | Recurring import scheduling (see SPEC6) |
| Import audit logging | |

---

## 2. API Endpoints

All endpoints are prefixed with `/api/v1`. Backend uses **snake_case** for all field names.

### 2.1 Upload Files

```
POST /api/v1/ingestion/upload
```

**Description:** Accepts one or more files, validates format, creates an `import_batch` record, and enqueues parsing.

**Request:**
- Content-Type: `multipart/form-data`
- Field: `files` — one or more files (repeated field)
- Field: `account_id` (optional, UUID) — associate uploads with a specific account

| Parameter | Type | Required | Description |
|---|---|---|---|
| `files` | File[] | Yes | One or more PDF/CSV files |
| `account_id` | UUID | No | Target account for imported transactions |

**Response — 202 Accepted:**

```json
{
  "batch_id": "uuid",
  "status": "processing",
  "files": [
    {
      "file_id": "uuid",
      "original_filename": "extrato_junho.csv",
      "mime_type": "text/csv",
      "size_bytes": 10240,
      "status": "queued"
    }
  ]
}
```

**Error Responses:**

| Status | Code | Description |
|---|---|---|
| 400 | `INVALID_FILE_FORMAT` | File is not CSV or PDF |
| 400 | `FILE_TOO_LARGE` | File exceeds 10 MB limit |
| 400 | `NO_FILES_PROVIDED` | Request contains no files |
| 400 | `TOO_MANY_FILES` | More than 20 files in a single request |
| 422 | `EMPTY_FILE` | File has zero bytes |

---

### 2.2 Get Batch Status

```
GET /api/v1/ingestion/batches/{batch_id}
```

**Description:** Returns the current processing status of an import batch and its files.

**Response — 200 OK:**

```json
{
  "batch_id": "uuid",
  "status": "completed | processing | partial_failure | failed",
  "created_at": "2025-07-10T14:30:00Z",
  "files": [
    {
      "file_id": "uuid",
      "original_filename": "extrato.csv",
      "status": "completed | processing | failed",
      "rows_extracted": 142,
      "rows_failed": 3,
      "error_message": null
    }
  ],
  "total_transactions_created": 139,
  "duplicates_skipped": 12
}
```

| Status | Code | Description |
|---|---|---|
| 404 | `BATCH_NOT_FOUND` | No batch with this ID exists |

---

### 2.3 Get Batch Parse Errors

```
GET /api/v1/ingestion/batches/{batch_id}/errors
```

**Description:** Returns detailed row-level parsing errors for a batch.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `page_size` | int | 50 | Items per page (max 100) |

**Response — 200 OK:**

```json
{
  "batch_id": "uuid",
  "errors": [
    {
      "file_id": "uuid",
      "original_filename": "extrato.csv",
      "row_number": 47,
      "raw_data": "15/13/2025;COMPRA XYZ;abc",
      "error_type": "INVALID_DATE",
      "error_message": "Could not parse date '15/13/2025': month 13 out of range"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 50
}
```

---

### 2.4 List Batches

```
GET /api/v1/ingestion/batches
```

**Description:** Returns a paginated list of all import batches.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (max 100) |
| `status` | string | — | Filter: `completed`, `processing`, `failed`, `partial_failure` |

**Response — 200 OK:**

```json
{
  "batches": [
    {
      "batch_id": "uuid",
      "status": "completed",
      "file_count": 2,
      "total_transactions_created": 284,
      "created_at": "2025-07-10T14:30:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

---

## 3. Data Models

### 3.1 `import_batch`

Tracks each upload session. One batch = one upload action (may contain multiple files).

```sql
CREATE TABLE import_batch (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID REFERENCES account(id) ON DELETE SET NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'processing'
                        CHECK (status IN ('processing','completed','partial_failure','failed')),
    file_count      INTEGER NOT NULL DEFAULT 0,
    total_created   INTEGER NOT NULL DEFAULT 0,
    total_skipped   INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_import_batch_status ON import_batch(status);
CREATE INDEX idx_import_batch_created ON import_batch(created_at DESC);
```

### 3.2 `import_file`

Tracks each individual file within a batch.

```sql
CREATE TABLE import_file (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id            UUID NOT NULL REFERENCES import_batch(id) ON DELETE CASCADE,
    original_filename   VARCHAR(255) NOT NULL,
    stored_path         VARCHAR(512) NOT NULL,
    mime_type           VARCHAR(50) NOT NULL
                            CHECK (mime_type IN ('text/csv','application/pdf')),
    size_bytes          INTEGER NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'queued'
                            CHECK (status IN ('queued','processing','completed','failed')),
    rows_extracted      INTEGER NOT NULL DEFAULT 0,
    rows_failed         INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_import_file_batch ON import_file(batch_id);
```

### 3.3 `import_error`

Stores row-level parsing failures for debugging and user feedback.

```sql
CREATE TABLE import_error (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id         UUID NOT NULL REFERENCES import_file(id) ON DELETE CASCADE,
    row_number      INTEGER,
    raw_data        TEXT,
    error_type      VARCHAR(50) NOT NULL,
    error_message   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_import_error_file ON import_error(file_id);
```

### 3.4 `transaction` (ingestion-relevant columns)

This is the core entity. Full definition owned by SPEC3; the subset relevant to ingestion is shown here.

```sql
CREATE TABLE transaction (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_file_id  UUID REFERENCES import_file(id) ON DELETE SET NULL,
    account_id      UUID REFERENCES account(id) ON DELETE SET NULL,
    date            DATE NOT NULL,
    description     VARCHAR(500) NOT NULL,
    amount          NUMERIC(14,2) NOT NULL,
    type            VARCHAR(10) NOT NULL CHECK (type IN ('credit','debit')),
    category_id     UUID REFERENCES category(id) ON DELETE SET NULL,
    hash            VARCHAR(64) NOT NULL UNIQUE,
    raw_data        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transaction_date ON transaction(date);
CREATE INDEX idx_transaction_hash ON transaction(hash);
CREATE INDEX idx_transaction_import ON transaction(import_file_id);
```

**Hash formula (for idempotent dedup):**

```
hash = SHA-256( date_iso + "|" + normalized_description + "|" + amount_str )
```

- `date_iso`: `YYYY-MM-DD`
- `normalized_description`: lowercased, whitespace-collapsed, stripped of accents
- `amount_str`: absolute value as string with 2 decimal places, e.g. `"1234.56"`

---

## 4. Business Logic

### 4.1 Processing Pipeline

The pipeline executes in sequential steps per file. Each step is wrapped in a try/except so partial progress is captured.

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 1.Upload │───>│ 2.Detect │───>│ 3.Parse  │───>│4.Normalize│──>│ 5.Persist│
│ & Store  │    │  Format  │    │  File    │    │ & Validate│   │  to DB   │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

#### Step 1 — Upload & Store

1. Validate MIME type by reading file magic bytes (do **not** trust the extension or `Content-Type` header).
2. Validate file size ≤ 10 MB.
3. Save raw file to disk at `uploads/{batch_id}/{file_id}.{ext}`.
4. Create `import_batch` and `import_file` records with status `queued`.
5. Return `202 Accepted` immediately.

#### Step 2 — Detect Format

1. Read magic bytes: `%PDF` → PDF, otherwise attempt CSV detection.
2. For CSV: detect delimiter (`;`, `,`, `\t`) by frequency analysis on first 5 lines.
3. Detect encoding (`utf-8`, `latin-1`, `cp1252`) using `chardet` or similar library.
4. Set `import_file.status = 'processing'`.

#### Step 3 — Parse File

**CSV Parsing:**

1. Read file with detected encoding and delimiter.
2. Auto-detect column roles using header heuristics:
   - Date column: headers matching `data`, `date`, `dt`, `fecha` (case-insensitive).
   - Description column: headers matching `descri`, `description`, `histórico`, `historico`, `memo`, `detail`.
   - Amount column: headers matching `valor`, `value`, `amount`, `quantia`, `montante`.
   - Optional credit/debit split: `crédito`/`débito`, `credit`/`debit`, `entrada`/`saída`.
3. If auto-detection fails for any required column, set status `failed` with error `COLUMN_MAPPING_FAILED`.
4. Parse each row, collecting successful rows and logging failures to `import_error`.

**PDF Parsing:**

1. **Primary strategy:** Use `pdfplumber` to extract tables.
2. **Fallback strategy:** Use `pdfplumber` text extraction with regex-based line parsing.
3. Expected line pattern (configurable regex):
   ```
   (?P<date>\d{2}[/\-\.]\d{2}[/\-\.]\d{2,4})\s+(?P<description>.+?)\s+(?P<amount>-?[\d.,]+)\s*$
   ```
4. Target: ≥ 90% row extraction rate. If below 70%, mark file as `failed`.
5. Log every unparseable row/line to `import_error` with `raw_data` and reason.

#### Step 4 — Normalize & Validate

Apply to every parsed row regardless of source format:

| Rule | Logic |
|---|---|
| **Normalize date** | Try formats in order: `DD/MM/YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`, `DD/MM/YY`, `MM/DD/YYYY`. Store as `DATE` (ISO). Reject if none match. |
| **Normalize amount** | Strip currency symbols (`R$`, `$`, `€`). Handle Brazilian format: `1.234,56` → `1234.56`. Parse to `NUMERIC(14,2)`. |
| **Determine type** | Negative amount → `debit`, positive → `credit`. Store `amount` as absolute value. |
| **Normalize description** | Trim whitespace, collapse multiple spaces, limit to 500 chars. |
| **Validate required fields** | `date`, `description`, `amount` must be non-null after parsing. Reject row if any is missing. |
| **Compute hash** | SHA-256 of canonical `date|description|amount` (see §3.4). |

#### Step 5 — Persist to DB

1. Within a single **database transaction** per file:
   a. Bulk `INSERT ... ON CONFLICT (hash) DO NOTHING` for all valid rows.
   b. Count inserted rows (`total_created`) vs. skipped (`total_skipped`).
   c. Bulk insert any `import_error` records.
   d. Update `import_file` with `rows_extracted`, `rows_failed`, `status`, `completed_at`.
2. After all files in the batch complete, update `import_batch.status`:
   - All files `completed` → `completed`
   - All files `failed` → `failed`
   - Mixed → `partial_failure`
3. Update `import_batch.total_created` and `import_batch.total_skipped`.

### 4.2 Idempotency Guarantee

- The `hash` column on `transaction` has a `UNIQUE` constraint.
- `INSERT ... ON CONFLICT (hash) DO NOTHING` ensures re-uploading the same file never creates duplicates.
- The batch status endpoint allows the frontend to poll and recover from interrupted uploads.

---

## 5. Error Handling

### 5.1 Error Codes

| Code | HTTP Status | User Message | Internal Action |
|---|---|---|---|
| `INVALID_FILE_FORMAT` | 400 | "Only CSV and PDF files are accepted." | Reject file pre-processing |
| `FILE_TOO_LARGE` | 400 | "File exceeds the 10 MB size limit." | Reject file pre-processing |
| `NO_FILES_PROVIDED` | 400 | "No files were included in the upload." | Reject request |
| `TOO_MANY_FILES` | 400 | "Maximum 20 files per upload." | Reject request |
| `EMPTY_FILE` | 422 | "The file is empty." | Reject file pre-processing |
| `COLUMN_MAPPING_FAILED` | — | Logged in batch errors | File status → `failed` |
| `INVALID_DATE` | — | Logged per-row | Row added to `import_error` |
| `INVALID_AMOUNT` | — | Logged per-row | Row added to `import_error` |
| `MISSING_REQUIRED_FIELD` | — | Logged per-row | Row added to `import_error` |
| `PDF_EXTRACTION_FAILED` | — | Logged in batch errors | File status → `failed` |
| `ENCODING_DETECTION_FAILED` | — | Logged in batch errors | File status → `failed` |
| `BATCH_NOT_FOUND` | 404 | "Import batch not found." | — |

### 5.2 Logging Strategy

- **Logger name:** `financeiro.ingestion`
- **Structured logging** (JSON format) with fields: `batch_id`, `file_id`, `step`, `level`, `message`, `timestamp`.
- **Log levels:**
  - `INFO` — File received, parsing started, parsing completed, batch completed.
  - `WARNING` — Individual row parse failure, extraction rate below 90%.
  - `ERROR` — File-level failure (encoding error, column mapping failure, PDF unreadable).
  - `CRITICAL` — Database write failure, disk I/O failure.
- Row-level parse failures are **also** persisted to `import_error` for user-facing display.

---

## 6. Frontend Components

All component names use **camelCase** per project convention.

### 6.1 Component Tree

```
fileUploadPage
├── fileDropZone
├── uploadFileList
│   └── uploadFileItem
├── uploadProgressBar
└── importBatchDetail
    ├── batchStatusBadge
    ├── batchFileSummary
    └── parseErrorTable
```

### 6.2 Component Details

| Component | Responsibility | Key Behavior |
|---|---|---|
| `fileUploadPage` | Page-level container. Orchestrates upload flow, holds batch state. | Route: `/import/upload`. Calls `POST /ingestion/upload`, then polls `GET /batches/{id}` every 2s until terminal status. |
| `fileDropZone` | Drag-and-drop area + click-to-browse. Validates file types client-side. | Accepts `.csv`, `.pdf` only. Shows inline error for rejected files. Max 20 files. Visual feedback on drag-over. |
| `uploadFileList` | Renders the list of selected files before/during upload. | Shows filename, size, remove button pre-upload. Shows per-file status post-upload. |
| `uploadFileItem` | Single file row in the list. | Displays: filename, size (human-readable), status icon (queued/processing/done/error), row counts on completion. |
| `uploadProgressBar` | Global progress indicator for the batch. | Indeterminate while `processing`. Green on `completed`. Yellow on `partial_failure`. Red on `failed`. |
| `importBatchDetail` | Expanded view of a completed/failed batch. | Shows summary stats. Links to error details if failures > 0. |
| `batchStatusBadge` | Small colored badge displaying batch status. | Color mapping: processing → blue, completed → green, partial_failure → amber, failed → red. |
| `batchFileSummary` | Table of files in the batch with per-file stats. | Columns: filename, status, rows extracted, rows failed. |
| `parseErrorTable` | Paginated table of row-level parsing errors. | Columns: filename, row #, raw data (truncated), error type, error message. Client-side pagination with 50 rows/page. |

### 6.3 Client-Side Validation

Performed in `fileDropZone` **before** upload:

1. File extension must be `.csv` or `.pdf` (case-insensitive).
2. File size must be ≤ 10 MB.
3. Total file count must be ≤ 20.
4. Display toast notification for each rejected file with reason.

### 6.4 State Management

- Use a composable `useIngestion()` that exposes:
  - `uploadFiles(files: File[], accountId?: string): Promise<BatchResponse>`
  - `pollBatchStatus(batchId: string): void` — starts polling interval
  - `stopPolling(): void`
  - `fetchBatchErrors(batchId: string, page: number): Promise<ErrorResponse>`
  - Reactive refs: `currentBatch`, `isUploading`, `isProcessing`, `uploadProgress`

---

## 7. Non-Functional Requirements

### 7.1 File Constraints

| Constraint | Value |
|---|---|
| Max file size | 10 MB per file |
| Max files per upload | 20 |
| Supported MIME types | `text/csv`, `application/pdf` |
| Supported CSV encodings | UTF-8, Latin-1 (ISO-8859-1), CP1252 |
| Supported CSV delimiters | `,` `;` `\t` |

### 7.2 Performance Targets

| Metric | Target |
|---|---|
| Upload response time (202) | < 500 ms |
| CSV parsing throughput | ≥ 10,000 rows/sec |
| PDF parsing throughput | ≥ 2 pages/sec |
| PDF extraction accuracy | ≥ 90% of rows correctly extracted |
| Batch status polling | 2-second interval, stops after terminal status |
| Max concurrent batch processing | 4 (configurable via env `INGESTION_WORKERS`) |

### 7.3 Storage

- Raw uploaded files stored at: `{UPLOAD_DIR}/{batch_id}/{file_id}.{ext}`
- Default `UPLOAD_DIR`: `./data/uploads`
- Files retained for 90 days, then eligible for cleanup (future cron job).

### 7.4 Security

- Validate MIME type by **magic bytes**, not by file extension or `Content-Type` header.
- Sanitize filenames: strip path traversal characters (`..`, `/`, `\`), limit to alphanumeric + `_-.` characters.
- Uploaded files must not be directly web-accessible (stored outside static file root).

---

## 8. Dependencies

### 8.1 Backend (Python)

| Library | Purpose | Version |
|---|---|---|
| `fastapi` | Web framework | ≥ 0.110 |
| `uvicorn` | ASGI server | ≥ 0.29 |
| `python-multipart` | Multipart form data parsing (file uploads) | ≥ 0.0.9 |
| `pdfplumber` | PDF table and text extraction | ≥ 0.11 |
| `chardet` | CSV encoding detection | ≥ 5.0 |
| `sqlalchemy` | ORM / database access | ≥ 2.0 |
| `asyncpg` | Async PostgreSQL driver | ≥ 0.29 |
| `alembic` | Database migrations | ≥ 1.13 |
| `python-magic` | MIME type detection via magic bytes | ≥ 0.4.27 |
| `pydantic` | Request/response schema validation | ≥ 2.0 |

### 8.2 Frontend (JavaScript)

| Library | Purpose |
|---|---|
| `vue` (3.x) | UI framework |
| `vite` | Build tool |
| `axios` | HTTP client for API calls |

### 8.3 Infrastructure

| Component | Purpose |
|---|---|
| PostgreSQL ≥ 15 | Primary database |
| File system | Local file storage for uploads |

---

## Appendix A — CSV Column Mapping Heuristics

The auto-mapper checks headers (case-insensitive, accent-insensitive) against these keyword lists:

| Role | Keywords |
|---|---|
| Date | `data`, `date`, `dt`, `fecha`, `vencimento`, `lancamento`, `lançamento` |
| Description | `descricao`, `descrição`, `description`, `historico`, `histórico`, `memo`, `detalhe`, `detail` |
| Amount (single) | `valor`, `value`, `amount`, `quantia`, `montante`, `total` |
| Credit | `credito`, `crédito`, `credit`, `entrada`, `deposito`, `depósito` |
| Debit | `debito`, `débito`, `debit`, `saida`, `saída`, `retirada` |

When both credit and debit columns are detected (instead of a single amount column), the normalizer combines them:
- If credit has a value → `type = 'credit'`, `amount = credit_value`
- If debit has a value → `type = 'debit'`, `amount = debit_value`
- If both have values in the same row → use the non-zero one; if ambiguous, log a warning and prefer debit.

---

## Appendix B — Date Parsing Order

Dates are attempted in the following order. The **first successful parse** wins:

1. `DD/MM/YYYY` — e.g. `25/12/2025` (Brazilian standard)
2. `DD-MM-YYYY` — e.g. `25-12-2025`
3. `DD.MM.YYYY` — e.g. `25.12.2025`
4. `YYYY-MM-DD` — e.g. `2025-12-25` (ISO 8601)
5. `DD/MM/YY` — e.g. `25/12/25` (two-digit year: 00-49 → 2000s, 50-99 → 1900s)
6. `MM/DD/YYYY` — e.g. `12/25/2025` (US format, last resort)

**Ambiguity rule:** If a date like `05/06/2025` is encountered and could be either `DD/MM` or `MM/DD`, the parser defaults to `DD/MM/YYYY` (format #1) since the system targets Brazilian financial data.

---

## Appendix C — Amount Parsing Examples

| Raw Input | Normalized | Type |
|---|---|---|
| `1.234,56` | `1234.56` | `credit` |
| `-1.234,56` | `1234.56` | `debit` |
| `R$ 1.234,56` | `1234.56` | `credit` |
| `1,234.56` | `1234.56` | `credit` |
| `(1234.56)` | `1234.56` | `debit` (parentheses = negative in accounting) |
| `1234` | `1234.00` | `credit` |
| `-50,00` | `50.00` | `debit` |

**Brazilian vs. US format detection:** If the value contains both `.` and `,`, the **last** separator determines the decimal marker. E.g., `1.234,56` → decimal is `,` (Brazilian). `1,234.56` → decimal is `.` (US).