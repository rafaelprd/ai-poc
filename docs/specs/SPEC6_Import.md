# SPEC 6 — Recurring Import

> Technical specification for **PRD 6 — Recurring Import**
>
> Status: Draft
> Last updated: 2025-01-20

---

## 1. Overview

This specification defines the batch import system that allows users to upload multiple financial files (CSV/PDF) in a single operation, automatically detects and rejects duplicates via content hashing, and maintains a full audit log of every import. It builds on top of the ingestion pipeline defined in **SPEC 1 (Data Ingestion)** — the parsing and normalization stages are reused; this spec adds the orchestration layer, deduplication logic, and import history tracking around them.

### Scope

| In scope                                      | Out of scope                          |
| --------------------------------------------- | ------------------------------------- |
| Multi-file batch upload endpoint              | Scheduled/cron-based automatic import |
| SHA-256 hash-based duplicate detection        | Machine-learning dedup (fuzzy match)  |
| Import session tracking with status lifecycle | Real-time streaming ingestion         |
| Import history API & UI                       | File storage/archival policies        |
| Partial-failure resilience per file           | Cross-account deduplication           |

### Key Principles (from AGENTS.md)

- **Transactions are immutable** except category edits — once imported, raw data never changes.
- **Batch-oriented pipeline** — files are processed as a unit within an import session.
- **Source of truth: database** — all state lives in PostgreSQL.
- **Always normalize before saving** — no raw/unvalidated data persisted.
- **Never trust input formats** — validate everything server-side.
- **Idempotent operations** — re-uploading the same file(s) produces zero new records.

---

## 2. API Endpoints

All endpoints are prefixed with `/api/v1`. Request/response bodies use JSON unless noted. File uploads use `multipart/form-data`.

### 2.1 POST `/api/v1/imports` — Create Batch Import

Uploads one or more files and starts an import session.

#### Request

| Part        | Type                    | Required | Description                                      |
| ----------- | ----------------------- | -------- | ------------------------------------------------ |
| `files`     | `UploadFile[]` (multi)  | Yes      | One or more CSV/PDF files                         |
| `account_id`| `int` (form field)      | Yes      | Target account for all transactions in this batch |

```/dev/null/example-curl.sh#L1-5
curl -X POST /api/v1/imports \
  -F "account_id=1" \
  -F "files=@statement_jan.csv" \
  -F "files=@statement_feb.csv"
```

#### Response `201 Created`

```/dev/null/response-201.json#L1-18
{
  "id": 42,
  "account_id": 1,
  "status": "processing",
  "total_files": 2,
  "created_at": "2025-01-20T14:30:00Z",
  "files": [
    {
      "filename": "statement_jan.csv",
      "status": "pending",
      "transactions_count": null
    },
    {
      "filename": "statement_feb.csv",
      "status": "pending",
      "transactions_count": null
    }
  ]
}
```

#### Error Responses

| Status | Code                    | Condition                                    |
| ------ | ----------------------- | -------------------------------------------- |
| `400`  | `NO_FILES`              | No files attached to the request             |
| `400`  | `INVALID_FILE_TYPE`     | File extension/MIME not CSV or PDF            |
| `400`  | `BATCH_SIZE_EXCEEDED`   | More than 20 files in a single request       |
| `400`  | `FILE_TOO_LARGE`        | Any single file exceeds 10 MB                |
| `404`  | `ACCOUNT_NOT_FOUND`     | `account_id` does not exist                  |
| `422`  | `VALIDATION_ERROR`      | Missing or malformed `account_id`            |

---

### 2.2 GET `/api/v1/imports` — List Import History

Returns a paginated list of past import sessions, most recent first.

#### Query Parameters

| Param        | Type   | Default | Description                        |
| ------------ | ------ | ------- | ---------------------------------- |
| `page`       | `int`  | `1`     | Page number (1-based)              |
| `page_size`  | `int`  | `20`    | Items per page (max `100`)         |
| `account_id` | `int?` | `null`  | Filter by account                  |
| `status`     | `str?` | `null`  | Filter by status enum value        |

#### Response `200 OK`

```/dev/null/response-list.json#L1-26
{
  "items": [
    {
      "id": 42,
      "account_id": 1,
      "status": "completed",
      "total_files": 2,
      "total_transactions": 87,
      "new_transactions": 85,
      "duplicate_transactions": 2,
      "failed_files": 0,
      "created_at": "2025-01-20T14:30:00Z",
      "completed_at": "2025-01-20T14:30:12Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 156,
    "total_pages": 8
  }
}
```

---

### 2.3 GET `/api/v1/imports/{import_id}` — Import Detail

Returns full detail for a single import session, including per-file status.

#### Response `200 OK`

```/dev/null/response-detail.json#L1-40
{
  "id": 42,
  "account_id": 1,
  "status": "completed_with_errors",
  "total_files": 3,
  "total_transactions": 87,
  "new_transactions": 85,
  "duplicate_transactions": 2,
  "created_at": "2025-01-20T14:30:00Z",
  "completed_at": "2025-01-20T14:30:12Z",
  "files": [
    {
      "id": 101,
      "filename": "statement_jan.csv",
      "status": "completed",
      "transactions_count": 45,
      "new_count": 44,
      "duplicate_count": 1,
      "error_message": null
    },
    {
      "id": 102,
      "filename": "statement_feb.csv",
      "status": "completed",
      "transactions_count": 42,
      "new_count": 41,
      "duplicate_count": 1,
      "error_message": null
    },
    {
      "id": 103,
      "filename": "corrupt.pdf",
      "status": "failed",
      "transactions_count": 0,
      "new_count": 0,
      "duplicate_count": 0,
      "error_message": "PDF_PARSE_ERROR: No table data detected in file"
    }
  ]
}
```

#### Error Responses

| Status | Code              | Condition              |
| ------ | ----------------- | ---------------------- |
| `404`  | `IMPORT_NOT_FOUND`| `import_id` not found  |

---

## 3. Data Models

### 3.1 `imports` Table

Represents a single import session (one user action that may include multiple files).

```/dev/null/imports.sql#L1-18
CREATE TABLE imports (
    id                      SERIAL PRIMARY KEY,
    account_id              INTEGER NOT NULL REFERENCES accounts(id),
    status                  VARCHAR(24) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'processing', 'completed', 'completed_with_errors', 'failed')),
    total_files             INTEGER NOT NULL DEFAULT 0,
    total_transactions      INTEGER NOT NULL DEFAULT 0,
    new_transactions        INTEGER NOT NULL DEFAULT 0,
    duplicate_transactions  INTEGER NOT NULL DEFAULT 0,
    failed_files            INTEGER NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,

    CONSTRAINT chk_completed_at CHECK (
        (status IN ('completed', 'completed_with_errors', 'failed') AND completed_at IS NOT NULL)
        OR (status IN ('pending', 'processing') AND completed_at IS NULL)
    )
);
```

### 3.2 `import_files` Table

Tracks each individual file within an import session.

```/dev/null/import_files.sql#L1-16
CREATE TABLE import_files (
    id                  SERIAL PRIMARY KEY,
    import_id           INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    filename            VARCHAR(255) NOT NULL,
    file_type           VARCHAR(10) NOT NULL CHECK (file_type IN ('csv', 'pdf')),
    file_size_bytes     INTEGER NOT NULL,
    status              VARCHAR(24) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    transactions_count  INTEGER NOT NULL DEFAULT 0,
    new_count           INTEGER NOT NULL DEFAULT 0,
    duplicate_count     INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);
CREATE INDEX idx_import_files_import_id ON import_files(import_id);
```

### 3.3 `import_transactions` Linking Table

Links each imported transaction back to the file and import session that created it. Enables audit trails and the ability to "view transactions from import X".

```/dev/null/import_transactions.sql#L1-12
CREATE TABLE import_transactions (
    id              SERIAL PRIMARY KEY,
    import_id       INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    import_file_id  INTEGER NOT NULL REFERENCES import_files(id) ON DELETE CASCADE,
    transaction_id  INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    was_duplicate   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_import_tx_import_id ON import_transactions(import_id);
CREATE INDEX idx_import_tx_file_id ON import_transactions(import_file_id);
CREATE UNIQUE INDEX idx_import_tx_unique ON import_transactions(import_id, transaction_id);
```

### 3.4 `transaction_hashes` Table

Stores precomputed content hashes for deduplication. Separated from the `transactions` table to keep concerns isolated and allow index-only scans on the hash column.

```/dev/null/transaction_hashes.sql#L1-10
CREATE TABLE transaction_hashes (
    id              SERIAL PRIMARY KEY,
    transaction_id  INTEGER NOT NULL UNIQUE REFERENCES transactions(id) ON DELETE CASCADE,
    content_hash    VARCHAR(64) NOT NULL,
    account_id      INTEGER NOT NULL REFERENCES accounts(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_tx_hash_unique ON transaction_hashes(account_id, content_hash);
```

> The unique index on `(account_id, content_hash)` enforces deduplication at the database level as a final safety net. This means two different accounts can independently have identical transaction data — deduplication is scoped per account.

---

## 4. Business Logic

### 4.1 Batch Processing Pipeline

The pipeline runs as a background task (FastAPI `BackgroundTasks`) triggered after the upload endpoint returns `201`. The response is immediate; processing is asynchronous.

```/dev/null/pipeline.txt#L1-24
┌─────────────┐
│  User POST  │──▶ Validate files ──▶ Create import record (status=pending)
└─────────────┘                              │
       ┌─────────────────────────────────────┘
       ▼
  Set import status = processing
       │
       ▼
  FOR EACH file in the batch:
       │
       ├──▶ Set import_file status = processing
       ├──▶ Parse file (delegates to SPEC1 ingestion: CSV parser / PDF parser)
       ├──▶ Normalize rows (SPEC1: date → ISO 8601, amount → Decimal, trim strings)
       ├──▶ Compute content_hash for each row
       ├──▶ Deduplicate (batch lookup against transaction_hashes)
       ├──▶ INSERT new transactions + hashes (within a per-file DB transaction)
       ├──▶ Record import_transactions links (was_duplicate = true/false)
       ├──▶ Update import_file counters & status = completed | failed
       │
  END FOR
       │
       ▼
  Aggregate file results ──▶ Update import counters & final status
```

### 4.2 Hash Computation Algorithm

The content hash uniquely identifies a transaction within an account. It uses SHA-256 over a canonical string representation of the immutable fields.

**Fields included in hash:**

| Field            | Normalization Before Hashing             |
| ---------------- | ---------------------------------------- |
| `account_id`     | Integer → string                         |
| `date`           | ISO 8601 date string (`YYYY-MM-DD`)      |
| `amount`         | Decimal with exactly 2 places (`-123.45`), no thousands separator |
| `description`    | Lowercased, whitespace collapsed and trimmed |

**Canonical string format:**

```/dev/null/hash-format.txt#L1-1
{account_id}|{date}|{amount}|{description}
```

**Python implementation:**

```/dev/null/hash.py#L1-25
import hashlib
import re
from decimal import Decimal

def compute_transaction_hash(
    account_id: int,
    date: str,
    amount: Decimal,
    description: str,
) -> str:
    """
    Compute a SHA-256 content hash for deduplication.
    All inputs MUST be pre-normalized before calling this function.
    """
    # Normalize description: lowercase, collapse whitespace
    normalized_desc = re.sub(r"\s+", " ", description.strip().lower())

    # Format amount: exactly 2 decimal places, no trailing whitespace
    normalized_amount = f"{amount:.2f}"

    canonical = f"{account_id}|{date}|{normalized_amount}|{normalized_desc}"

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### 4.3 Deduplication Strategy

A **pre-check + ON CONFLICT** two-layer approach is used:

1. **Layer 1 — Batch pre-check (performance optimization):** Before inserting, collect all computed hashes for the current file, then `SELECT content_hash FROM transaction_hashes WHERE account_id = :aid AND content_hash = ANY(:hashes)`. Mark matched rows as duplicates immediately. This avoids the overhead of preparing full INSERT statements for rows that already exist.

2. **Layer 2 — `ON CONFLICT DO NOTHING` (safety net):** The `idx_tx_hash_unique` index on `transaction_hashes(account_id, content_hash)` provides a database-level uniqueness guarantee. If a race condition causes two concurrent imports to pass Layer 1 simultaneously, the `ON CONFLICT` clause silently prevents the duplicate.

```/dev/null/dedup.py#L1-32
async def deduplicate_and_insert(
    db: AsyncSession,
    account_id: int,
    import_file_id: int,
    import_id: int,
    parsed_rows: list[dict],
) -> dict:
    """Returns counts: { new: int, duplicate: int }"""
    hashes = {
        compute_transaction_hash(account_id, r["date"], r["amount"], r["description"]): r
        for r in parsed_rows
    }

    # Layer 1: batch pre-check
    existing = await db.execute(
        select(TransactionHash.content_hash)
        .where(TransactionHash.account_id == account_id)
        .where(TransactionHash.content_hash.in_(list(hashes.keys())))
    )
    existing_hashes = {row.content_hash for row in existing}

    new_rows = {h: r for h, r in hashes.items() if h not in existing_hashes}
    duplicate_count = len(hashes) - len(new_rows)

    # Layer 2: insert with ON CONFLICT safety net
    for content_hash, row in new_rows.items():
        # Insert transaction, then hash record, then link
        # Each wrapped in savepoint for individual row failure isolation
        ...

    return {"new": len(new_rows), "duplicate": duplicate_count}
```

### 4.4 Import Status Lifecycle

```/dev/null/status-lifecycle.txt#L1-13
  pending ──────▶ processing ──────┬──▶ completed
                                   │
                                   ├──▶ completed_with_errors
                                   │
                                   └──▶ failed

  Transition rules:
  - pending → processing       : background task picks up the import
  - processing → completed     : all files succeeded (0 failed_files)
  - processing → completed_with_errors : at least 1 file succeeded AND at least 1 failed
  - processing → failed        : ALL files failed (failed_files == total_files)
```

**Status determination logic (Python):**

```/dev/null/status-logic.py#L1-11
def resolve_import_status(total_files: int, failed_files: int) -> str:
    if failed_files == 0:
        return "completed"
    elif failed_files == total_files:
        return "failed"
    else:
        return "completed_with_errors"
```

### 4.5 Relationship with SPEC 1 — Ingestion Pipeline

This spec **reuses** SPEC 1's file parsing and normalization modules. It does **not** duplicate them.

| SPEC 1 Responsibility                     | SPEC 6 Addition                              |
| ----------------------------------------- | -------------------------------------------- |
| CSV column mapping & parsing              | Batch orchestration across multiple files     |
| PDF table extraction                      | Import session lifecycle management          |
| Date normalization (→ ISO 8601)           | Content hashing after normalization          |
| Amount parsing (→ Decimal)                | Deduplication against existing records       |
| Validation & null-check on required fields | `import_transactions` audit linking          |
| Single-file upload endpoint               | Multi-file batch endpoint                    |

The SPEC 1 parsers are called as internal functions by the SPEC 6 batch pipeline:

```/dev/null/integration.py#L1-9
from app.ingestion.csv_parser import parse_csv   # SPEC 1
from app.ingestion.pdf_parser import parse_pdf   # SPEC 1
from app.ingestion.normalizer import normalize   # SPEC 1

async def process_file(file: ImportFile) -> list[dict]:
    if file.file_type == "csv":
        raw_rows = parse_csv(file.content)
    elif file.file_type == "pdf":
        raw_rows = parse_pdf(file.content)
    return [normalize(row) for row in raw_rows]
```

---

## 5. Error Handling

### 5.1 Partial Failure Strategy

Each file is processed **independently** within the batch. One file's failure does not abort the entire import.

- Each file is processed in its own database transaction (using a SAVEPOINT within the import's outer transaction or an independent transaction per file).
- If parsing or insertion fails for a file, that `import_file` record is marked `status = 'failed'` with a descriptive `error_message`.
- Remaining files continue processing.
- The parent `imports` record reflects partial success via `completed_with_errors`.

### 5.2 Error Codes

All error responses follow a consistent envelope:

```/dev/null/error-envelope.json#L1-6
{
  "error": {
    "code": "INVALID_FILE_TYPE",
    "message": "File 'report.xlsx' has unsupported type. Accepted: csv, pdf.",
    "details": { "filename": "report.xlsx", "detected_type": "xlsx" }
  }
}
```

| Code                   | HTTP | Description                                             |
| ---------------------- | ---- | ------------------------------------------------------- |
| `NO_FILES`             | 400  | Request contained no file attachments                   |
| `INVALID_FILE_TYPE`    | 400  | File extension or MIME type not in allowlist             |
| `BATCH_SIZE_EXCEEDED`  | 400  | Batch contains more than 20 files                       |
| `FILE_TOO_LARGE`       | 400  | Single file exceeds 10 MB                               |
| `ACCOUNT_NOT_FOUND`    | 404  | Referenced `account_id` does not exist                  |
| `IMPORT_NOT_FOUND`     | 404  | Requested `import_id` does not exist                    |
| `VALIDATION_ERROR`     | 422  | Schema validation failed (missing/malformed fields)     |
| `CSV_PARSE_ERROR`      | —    | Stored in `import_files.error_message` (not HTTP error) |
| `PDF_PARSE_ERROR`      | —    | Stored in `import_files.error_message` (not HTTP error) |
| `NORMALIZATION_ERROR`  | —    | Stored in `import_files.error_message` (not HTTP error) |
| `DB_WRITE_ERROR`       | —    | Stored in `import_files.error_message` (not HTTP error) |

> Codes marked `—` are **internal** — they appear only in the `import_files.error_message` column and the import detail API response, never as direct HTTP error responses.

### 5.3 Logging Strategy

Use Python `structlog` with structured JSON output. Every log entry includes:

| Field            | Source                          |
| ---------------- | ------------------------------- |
| `import_id`      | Current import session          |
| `import_file_id` | Current file being processed    |
| `account_id`     | Target account                  |
| `event`          | Descriptive event name          |
| `level`          | `info` / `warning` / `error`    |

**Key log events:**

| Event                          | Level   | When                                        |
| ------------------------------ | ------- | ------------------------------------------- |
| `import.created`               | info    | Import record created, processing queued    |
| `import.file.processing_start` | info    | Individual file processing begins           |
| `import.file.parse_complete`   | info    | File parsed successfully, N rows extracted  |
| `import.file.duplicates_found` | info    | N duplicates detected during dedup check    |
| `import.file.completed`        | info    | File fully processed, counters updated      |
| `import.file.failed`           | error   | File processing failed (with traceback)     |
| `import.completed`             | info    | All files processed, import finalized       |
| `import.failed`                | error   | All files in batch failed                   |

---

## 6. Frontend Components

All component names follow **camelCase** convention per AGENTS.md.

### 6.1 Component Tree

```/dev/null/component-tree.txt#L1-12
importPage
├── importUploader
│   ├── fileDropZone
│   └── importProgressTracker
│       └── importFileStatus  (× N per file)
└── importHistory
    ├── importHistoryFilters
    ├── importHistoryTable
    │   └── importHistoryRow  (× N per import)
    └── importDetailModal
        └── importFileResultList
            └── importFileResultItem  (× N per file)
```

### 6.2 Component Specifications

#### `importPage`

- **Path:** `src/views/importPage.vue`
- **Responsibility:** Top-level route view. Renders `importUploader` and `importHistory` in a vertical layout.
- **State:** None (orchestration only).

#### `importUploader`

- **Path:** `src/components/import/importUploader.vue`
- **Responsibility:** File selection and upload initiation.
- **Props:** `accountId: number`
- **Emits:** `importCreated(importId: number)`
- **Behavior:**
  - Contains an account selector dropdown (if `accountId` not pre-set).
  - Renders `fileDropZone` for drag-and-drop or click-to-browse.
  - Validates file count (≤ 20) and individual file size (≤ 10 MB) client-side before upload.
  - On submit, calls `POST /api/v1/imports` and transitions to progress view.

#### `fileDropZone`

- **Path:** `src/components/import/fileDropZone.vue`
- **Responsibility:** Drag-and-drop area with file type validation.
- **Props:** `acceptedTypes: string[]` (default: `['.csv', '.pdf']`), `maxFiles: number`, `maxFileSizeMb: number`
- **Emits:** `filesSelected(files: File[])`
- **Behavior:**
  - Visual feedback on drag-over (border highlight).
  - Rejects files with wrong extensions immediately with inline toast.
  - Displays selected file list with name, size, and a remove button.

#### `importProgressTracker`

- **Path:** `src/components/import/importProgressTracker.vue`
- **Responsibility:** Polls import status and displays real-time progress.
- **Props:** `importId: number`
- **Emits:** `importFinished(importDetail: ImportDetail)`
- **Behavior:**
  - Polls `GET /api/v1/imports/{importId}` every **2 seconds** while `status` is `pending` or `processing`.
  - Stops polling on terminal status (`completed`, `completed_with_errors`, `failed`).
  - Shows overall progress bar: `(completed_files + failed_files) / total_files`.
  - Renders one `importFileStatus` per file.

#### `importFileStatus`

- **Path:** `src/components/import/importFileStatus.vue`
- **Responsibility:** Single file status indicator within the progress tracker.
- **Props:** `file: ImportFileDetail`
- **Behavior:**
  - Spinner icon while `pending` / `processing`.
  - Green check + count on `completed`.
  - Red ✕ + error message on `failed`.

#### `importHistory`

- **Path:** `src/components/import/importHistory.vue`
- **Responsibility:** Container for filters and history table.
- **State:** `page`, `pageSize`, `statusFilter`, `accountFilter`.
- **Behavior:** Fetches `GET /api/v1/imports` on mount and on filter/page change.

#### `importHistoryFilters`

- **Path:** `src/components/import/importHistoryFilters.vue`
- **Responsibility:** Filter controls for the history table.
- **Emits:** `filtersChanged({ accountId?, status? })`
- **Behavior:** Dropdowns for account and status. Debounces changes by 300 ms.

#### `importHistoryTable`

- **Path:** `src/components/import/importHistoryTable.vue`
- **Responsibility:** Paginated table displaying import sessions.
- **Props:** `imports: ImportSummary[]`, `pagination: Pagination`
- **Emits:** `pageChanged(page: number)`, `importSelected(importId: number)`
- **Columns:** ID, Account, Status (badge), Files, New Txns, Duplicates, Date, Actions.

#### `importDetailModal`

- **Path:** `src/components/import/importDetailModal.vue`
- **Responsibility:** Modal overlay showing full import detail when a row is clicked.
- **Props:** `importId: number`, `visible: boolean`
- **Emits:** `close`
- **Behavior:** Fetches `GET /api/v1/imports/{importId}` on open. Displays summary stats and `importFileResultList`.

### 6.3 TypeScript Interfaces

```/dev/null/types.ts#L1-37
interface ImportSummary {
  id: number;
  accountId: number;
  status: 'pending' | 'processing' | 'completed' | 'completed_with_errors' | 'failed';
  totalFiles: number;
  totalTransactions: number;
  newTransactions: number;
  duplicateTransactions: number;
  failedFiles: number;
  createdAt: string;
  completedAt: string | null;
}

interface ImportDetail extends ImportSummary {
  files: ImportFileDetail[];
}

interface ImportFileDetail {
  id: number;
  filename: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  transactionsCount: number;
  newCount: number;
  duplicateCount: number;
  errorMessage: string | null;
}

interface Pagination {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

interface ImportCreateResponse {
  id: number;
  accountId: number;
  status: string;
  totalFiles: number;
  createdAt: string;
  files: ImportFileDetail[];
}
```

---

## 7. Non-Functional Requirements

### 7.1 Limits

| Parameter                        | Value  | Rationale                                    |
| -------------------------------- | ------ | -------------------------------------------- |
| Max files per batch              | 20     | Prevent memory exhaustion on upload          |
| Max single file size             | 10 MB  | Typical bank statement is < 2 MB             |
| Max total batch size             | 50 MB  | Sum of all files in one request              |
| Max rows per file                | 50,000 | Guard against malformed files                |
| Polling interval (frontend)      | 2 sec  | Balance between responsiveness and load      |
| Max concurrent import sessions   | 5      | Per-application limit (not per-user)         |

### 7.2 Concurrency & Processing

- **Background processing:** Import processing runs via `BackgroundTasks` (for MVP). Future: migrate to a task queue (Celery/arq) for horizontal scaling.
- **Concurrent imports:** A semaphore (`asyncio.Semaphore(5)`) limits concurrent background import tasks to prevent database connection pool exhaustion.
- **Per-file isolation:** Each file is processed in its own database transaction. A failure in file N does not roll back files 1…N-1.
- **No file-level parallelism within a single import:** Files within one batch are processed sequentially to simplify status tracking and avoid write contention on the parent `imports` row.

### 7.3 Idempotency Guarantees

| Scenario                                  | Expected Behavior                                           |
| ----------------------------------------- | ----------------------------------------------------------- |
| Same file uploaded twice in separate imports | Zero new transactions on second upload; all marked duplicate |
| Same file included twice in one batch      | Second occurrence is fully deduplicated against the first    |
| Concurrent uploads of overlapping files    | `ON CONFLICT` prevents duplicate hashes at DB level          |
| Re-upload after partial failure            | Only previously-failed files produce new transactions        |

**Idempotency key:** The `(account_id, content_hash)` pair in `transaction_hashes` is the sole determinant. No client-provided idempotency keys are required — the content itself is the key.

### 7.4 Performance Targets

| Metric                            | Target          |
| --------------------------------- | --------------- |
| Upload acceptance response time   | < 500 ms        |
| Per-file processing time (CSV)    | < 5 sec / 10k rows |
| Per-file processing time (PDF)    | < 15 sec / file |
| Import history list response time | < 200 ms        |
| Import detail response time       | < 200 ms        |

### 7.5 Data Retention

- `imports` and `import_files` records are retained indefinitely for audit purposes.
- Raw uploaded file bytes are **not** stored after processing. Only parsed and normalized transaction data is persisted.
- The `import_transactions` linking table allows tracing any transaction back to its source import.

---

## Appendix A: Backend File Structure

```/dev/null/file-structure.txt#L1-16
app/
├── api/
│   └── v1/
│       └── imports.py          # Router: POST, GET list, GET detail
├── models/
│   ├── import_model.py         # SQLAlchemy: Import, ImportFile, ImportTransaction
│   └── transaction_hash.py     # SQLAlchemy: TransactionHash
├── schemas/
│   └── import_schema.py        # Pydantic: request/response models
├── services/
│   └── import_service.py       # Business logic: batch pipeline, dedup
├── utils/
│   └── hashing.py              # compute_transaction_hash()
└── ingestion/                  # SPEC 1 (existing)
    ├── csv_parser.py
    ├── pdf_parser.py
    └── normalizer.py
```

## Appendix B: Migration Script

```/dev/null/migration.sql#L1-46
-- Migration: 006_create_import_tables
-- Description: SPEC 6 — Recurring Import tables

BEGIN;

CREATE TABLE imports (
    id                      SERIAL PRIMARY KEY,
    account_id              INTEGER NOT NULL REFERENCES accounts(id),
    status                  VARCHAR(24) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'processing', 'completed', 'completed_with_errors', 'failed')),
    total_files             INTEGER NOT NULL DEFAULT 0,
    total_transactions      INTEGER NOT NULL DEFAULT 0,
    new_transactions        INTEGER NOT NULL DEFAULT 0,
    duplicate_transactions  INTEGER NOT NULL DEFAULT 0,
    failed_files            INTEGER NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ
);

CREATE TABLE import_files (
    id                  SERIAL PRIMARY KEY,
    import_id           INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    filename            VARCHAR(255) NOT NULL,
    file_type           VARCHAR(10) NOT NULL CHECK (file_type IN ('csv', 'pdf')),
    file_size_bytes     INTEGER NOT NULL,
    status              VARCHAR(24) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    transactions_count  INTEGER NOT NULL DEFAULT 0,
    new_count           INTEGER NOT NULL DEFAULT 0,
    duplicate_count     INTEGER NOT NULL DEFAULT 0,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);
CREATE INDEX idx_import_files_import_id ON import_files(import_id);

CREATE TABLE import_transactions (
    id              SERIAL PRIMARY KEY,
    import_id       INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
    import_file_id  INTEGER NOT NULL REFERENCES import_files(id) ON DELETE CASCADE,
    transaction_id  INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    was_duplicate   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_import_tx_import_id ON import_transactions(import_id);
CREATE INDEX idx_import_tx_file_id ON import_transactions(import_file_id);
CREATE UNIQUE INDEX idx_import_tx_unique ON import_transactions(import_id, transaction_id);

CREATE TABLE transaction_hashes (
    id              SERIAL PRIMARY KEY,
    transaction_id  INTEGER NOT NULL UNIQUE REFERENCES transactions(id) ON DELETE CASCADE,
    content_hash    VARCHAR(64) NOT NULL,
    account_id      INTEGER NOT NULL REFERENCES accounts(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_tx_hash_unique ON transaction_hashes(account_id, content_hash);

COMMIT;
```
