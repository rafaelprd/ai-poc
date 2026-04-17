# SPEC4 — Fixed Expenses

> **Status:** Draft
> **PRD:** [PRD4_FixedExpenses](../prds/PRD4_FixedExpenses.md)
> **Last updated:** 2025-01-01

---

## 1. Overview

The Fixed Expenses feature allows users to register recurring financial obligations (rent, subscriptions, utilities, etc.) and have corresponding transaction entries generated automatically on a scheduled basis. The system guarantees **idempotent generation** — running the generator multiple times for the same period never creates duplicate entries.

### Scope

| In Scope                                      | Out of Scope                          |
| --------------------------------------------- | ------------------------------------- |
| CRUD for fixed expense definitions             | Payment processing / integrations     |
| Frequency configuration (monthly, weekly, etc.)| Notification/reminder system          |
| Automatic & on-demand entry generation         | Variable-amount recurring expenses    |
| Duplicate prevention via unique constraints     | Multi-currency support                |
| Linking generated entries to transactions table | Approval workflows                    |

### User Stories Covered

- **US1** — Create fixed expense: User inputs name, value, frequency. Saved successfully.
- **US2** — Monthly generation: Auto-create entries monthly. No duplicates created.

---

## 2. Data Models

### 2.1 `fixed_expenses` Table

Stores the definition/template of each recurring expense.

```/dev/null/schema.sql#L1-30
CREATE TABLE fixed_expenses (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID            NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    category_id     UUID            REFERENCES categories(id) ON DELETE SET NULL,
    name            VARCHAR(255)    NOT NULL,
    description     TEXT,
    amount          NUMERIC(14, 2)  NOT NULL CHECK (amount > 0),
    frequency       VARCHAR(20)     NOT NULL CHECK (frequency IN ('weekly', 'biweekly', 'monthly', 'bimonthly', 'quarterly', 'semiannual', 'annual')),
    day_of_month    SMALLINT        CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week     SMALLINT        CHECK (day_of_week BETWEEN 0 AND 6),  -- 0=Monday, 6=Sunday
    start_date      DATE            NOT NULL,
    end_date        DATE,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT chk_date_range CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT chk_day_context CHECK (
        (frequency IN ('weekly', 'biweekly') AND day_of_week IS NOT NULL)
        OR
        (frequency NOT IN ('weekly', 'biweekly') AND day_of_month IS NOT NULL)
    )
);

CREATE INDEX idx_fixed_expenses_account ON fixed_expenses(account_id);
CREATE INDEX idx_fixed_expenses_active ON fixed_expenses(is_active) WHERE is_active = TRUE;
```

### 2.2 `fixed_expense_entries` Table

Stores each generated occurrence. Links back to both the fixed expense definition and (optionally) a transaction record.

```/dev/null/schema.sql#L32-62
CREATE TABLE fixed_expense_entries (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    fixed_expense_id    UUID            NOT NULL REFERENCES fixed_expenses(id) ON DELETE CASCADE,
    reference_date      DATE            NOT NULL,
    due_date            DATE            NOT NULL,
    amount              NUMERIC(14, 2)  NOT NULL CHECK (amount > 0),
    transaction_id      UUID            REFERENCES transactions(id) ON DELETE SET NULL,
    status              VARCHAR(20)     NOT NULL DEFAULT 'pending'
                                        CHECK (status IN ('pending', 'paid', 'skipped', 'cancelled')),
    generation_hash     VARCHAR(64)     NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_generation_hash UNIQUE (generation_hash)
);

CREATE INDEX idx_fee_fixed_expense ON fixed_expense_entries(fixed_expense_id);
CREATE INDEX idx_fee_reference_date ON fixed_expense_entries(reference_date);
CREATE INDEX idx_fee_status ON fixed_expense_entries(status);
CREATE INDEX idx_fee_due_date ON fixed_expense_entries(due_date);
```

### 2.3 `generation_hash` Calculation

The `generation_hash` is a SHA-256 digest that guarantees idempotent generation. It is computed as:

```/dev/null/hash.py#L1-5
import hashlib

def compute_generation_hash(fixed_expense_id: str, reference_date: str) -> str:
    payload = f"{fixed_expense_id}:{reference_date}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

Because of the `UNIQUE` constraint on `generation_hash`, attempting to insert a duplicate entry for the same expense + period will raise a database conflict, which the application handles gracefully (skip, no error).

### 2.4 Updated At Trigger

```/dev/null/trigger.sql#L1-12
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_fixed_expenses_updated
    BEFORE UPDATE ON fixed_expenses FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_fee_updated
    BEFORE UPDATE ON fixed_expense_entries FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

---

## 3. API Endpoints

**Base path:** `/api/v1/fixed-expenses`

All request/response bodies use JSON. Dates use `YYYY-MM-DD` format. Amounts are decimal numbers (never floats in JS — transmitted as strings when precision matters, parsed server-side).

### 3.1 Create Fixed Expense

| Field    | Value                                |
| -------- | ------------------------------------ |
| Method   | `POST`                               |
| Path     | `/api/v1/fixed-expenses`             |
| Auth     | Required                             |

**Request Body:**

```/dev/null/request.json#L1-11
{
    "account_id": "uuid",
    "category_id": "uuid | null",
    "name": "string (1-255 chars, required)",
    "description": "string | null",
    "amount": "decimal > 0 (required)",
    "frequency": "weekly | biweekly | monthly | bimonthly | quarterly | semiannual | annual",
    "day_of_month": "integer 1-31 | null",
    "day_of_week": "integer 0-6 | null",
    "start_date": "YYYY-MM-DD (required)",
    "end_date": "YYYY-MM-DD | null"
}
```

**Response `201 Created`:**

```/dev/null/response.json#L1-17
{
    "id": "uuid",
    "account_id": "uuid",
    "category_id": "uuid | null",
    "name": "string",
    "description": "string | null",
    "amount": "decimal",
    "frequency": "string",
    "day_of_month": "integer | null",
    "day_of_week": "integer | null",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD | null",
    "is_active": true,
    "created_at": "ISO-8601",
    "updated_at": "ISO-8601"
}
```

**Error Responses:** `400` (validation), `422` (constraint violation)

---

### 3.2 List Fixed Expenses

| Field    | Value                                |
| -------- | ------------------------------------ |
| Method   | `GET`                                |
| Path     | `/api/v1/fixed-expenses`             |
| Auth     | Required                             |

**Query Parameters:**

| Param        | Type    | Default | Description                            |
| ------------ | ------- | ------- | -------------------------------------- |
| `account_id` | UUID    | —       | Filter by account (required)           |
| `is_active`  | bool    | `true`  | Filter active/inactive                 |
| `page`       | int     | `1`     | Page number (1-based)                  |
| `page_size`  | int     | `20`    | Items per page (max 100)               |

**Response `200 OK`:**

```/dev/null/response.json#L1-10
{
    "items": ["...FixedExpense objects"],
    "total": 42,
    "page": 1,
    "page_size": 20,
    "total_pages": 3
}
```

---

### 3.3 Get Fixed Expense by ID

| Field    | Value                                      |
| -------- | ------------------------------------------ |
| Method   | `GET`                                      |
| Path     | `/api/v1/fixed-expenses/{id}`              |
| Auth     | Required                                   |

**Response:** `200 OK` with FixedExpense object. `404` if not found.

---

### 3.4 Update Fixed Expense

| Field    | Value                                      |
| -------- | ------------------------------------------ |
| Method   | `PATCH`                                    |
| Path     | `/api/v1/fixed-expenses/{id}`              |
| Auth     | Required                                   |

**Request Body (partial update — only provided fields are changed):**

```/dev/null/request.json#L1-10
{
    "name": "string | undefined",
    "description": "string | null | undefined",
    "category_id": "uuid | null | undefined",
    "amount": "decimal | undefined",
    "frequency": "string | undefined",
    "day_of_month": "integer | null | undefined",
    "day_of_week": "integer | null | undefined",
    "end_date": "YYYY-MM-DD | null | undefined",
    "is_active": "boolean | undefined"
}
```

> **Note:** `start_date` and `account_id` are immutable after creation. Changes to `amount` or `frequency` only affect **future** generated entries; existing entries remain unchanged (transaction immutability principle).

**Response:** `200 OK` with updated FixedExpense object. `404` if not found. `400` / `422` on validation error.

---

### 3.5 Delete Fixed Expense

| Field    | Value                                      |
| -------- | ------------------------------------------ |
| Method   | `DELETE`                                   |
| Path     | `/api/v1/fixed-expenses/{id}`              |
| Auth     | Required                                   |

**Behavior:** Soft-delete by setting `is_active = FALSE` and `end_date = current_date`. Does **not** remove previously generated entries.

**Response:** `204 No Content`. `404` if not found.

---

### 3.6 List Entries for a Fixed Expense

| Field    | Value                                                     |
| -------- | --------------------------------------------------------- |
| Method   | `GET`                                                     |
| Path     | `/api/v1/fixed-expenses/{id}/entries`                     |
| Auth     | Required                                                  |

**Query Parameters:**

| Param         | Type   | Default   | Description                  |
| ------------- | ------ | --------- | ---------------------------- |
| `status`      | string | —         | Filter by status             |
| `from_date`   | date   | —         | Minimum `reference_date`     |
| `to_date`     | date   | —         | Maximum `reference_date`     |
| `page`        | int    | `1`       | Page number                  |
| `page_size`   | int    | `20`      | Items per page (max 100)     |

**Response `200 OK`:** Paginated list of `FixedExpenseEntry` objects.

---

### 3.7 Trigger Generation (On-Demand)

| Field    | Value                                         |
| -------- | --------------------------------------------- |
| Method   | `POST`                                        |
| Path     | `/api/v1/fixed-expenses/generate`             |
| Auth     | Required (admin or system)                    |

**Request Body:**

```/dev/null/request.json#L1-4
{
    "target_date": "YYYY-MM-DD (required, the month/week to generate for)",
    "fixed_expense_id": "uuid | null (null = generate for all active expenses)"
}
```

**Response `200 OK`:**

```/dev/null/response.json#L1-6
{
    "generated_count": 15,
    "skipped_count": 3,
    "errors": []
}
```

> Idempotent: repeated calls with the same `target_date` return `generated_count: 0` and `skipped_count: N` because entries already exist.

**Error Response:** `400` if `target_date` is invalid.

---

### 3.8 Update Entry Status

| Field    | Value                                                              |
| -------- | ------------------------------------------------------------------ |
| Method   | `PATCH`                                                            |
| Path     | `/api/v1/fixed-expenses/entries/{entry_id}`                        |
| Auth     | Required                                                           |

**Request Body:**

```/dev/null/request.json#L1-4
{
    "status": "pending | paid | skipped | cancelled",
    "transaction_id": "uuid | null"
}
```

**Response:** `200 OK` with updated entry. `404` if not found.

---

## 4. Business Logic

### 4.1 Frequency Options

| Frequency     | Period          | Scheduling Field Used | Entries per Year |
| ------------- | --------------- | --------------------- | ---------------- |
| `weekly`      | Every 7 days    | `day_of_week`         | ~52              |
| `biweekly`    | Every 14 days   | `day_of_week`         | ~26              |
| `monthly`     | Every month     | `day_of_month`        | 12               |
| `bimonthly`   | Every 2 months  | `day_of_month`        | 6                |
| `quarterly`   | Every 3 months  | `day_of_month`        | 4                |
| `semiannual`  | Every 6 months  | `day_of_month`        | 2                |
| `annual`      | Every 12 months | `day_of_month`        | 1                |

**Day clamping:** If `day_of_month = 31` and the target month has only 28/29/30 days, clamp to the last day of that month (e.g., Feb 28 or Feb 29 in leap years).

### 4.2 Generation Algorithm

```/dev/null/generate.py#L1-65
from datetime import date, timedelta
from calendar import monthrange
import hashlib
from typing import List

def generate_entries(target_date: date, expenses: List[FixedExpense]) -> GenerationResult:
    """
    Generate fixed expense entries for the period containing target_date.
    Called by both the cron scheduler and the on-demand API endpoint.
    """
    generated = 0
    skipped = 0
    errors = []

    for expense in expenses:
        try:
            # Step 1: Determine all due dates in the target period
            due_dates = compute_due_dates(expense, target_date)

            for due_date in due_dates:
                # Step 2: Check active window
                if due_date < expense.start_date:
                    continue
                if expense.end_date and due_date > expense.end_date:
                    continue

                # Step 3: Compute idempotency hash
                reference = due_date.isoformat()
                gen_hash = hashlib.sha256(
                    f"{expense.id}:{reference}".encode()
                ).hexdigest()

                # Step 4: Attempt INSERT with ON CONFLICT DO NOTHING
                result = db.execute("""
                    INSERT INTO fixed_expense_entries
                        (fixed_expense_id, reference_date, due_date, amount, generation_hash)
                    VALUES
                        (:expense_id, :ref_date, :due_date, :amount, :hash)
                    ON CONFLICT (generation_hash) DO NOTHING
                    RETURNING id
                """, {
                    "expense_id": expense.id,
                    "ref_date": reference,
                    "due_date": due_date,
                    "amount": expense.amount,
                    "hash": gen_hash,
                })

                if result.rowcount > 0:
                    generated += 1
                else:
                    skipped += 1

        except Exception as e:
            errors.append({"fixed_expense_id": str(expense.id), "error": str(e)})
            logger.error(f"Generation failed for expense {expense.id}: {e}")

    return GenerationResult(
        generated_count=generated,
        skipped_count=skipped,
        errors=errors,
    )
```

### 4.3 `compute_due_dates` Logic

| Frequency        | Logic                                                                                  |
| ---------------- | -------------------------------------------------------------------------------------- |
| `monthly`        | One date: `target_month / clamped_day_of_month`                                        |
| `weekly`         | All dates in `target_month` where `weekday == day_of_week`                             |
| `biweekly`       | Every other occurrence of `day_of_week` in `target_month`, aligned to `start_date`     |
| `bimonthly`      | Generate only if `(target_month - start_month) % 2 == 0`                               |
| `quarterly`      | Generate only if `(target_month - start_month) % 3 == 0`                               |
| `semiannual`     | Generate only if `(target_month - start_month) % 6 == 0`                               |
| `annual`         | Generate only if `target_month == start_month`                                         |

### 4.4 Duplicate Prevention

Duplicate prevention relies on **three layers**:

1. **`generation_hash` UNIQUE constraint** — database-level guarantee. Even under concurrent execution, only one row can exist per `(fixed_expense_id, reference_date)` pair.
2. **`ON CONFLICT DO NOTHING`** — application-level idempotency. The INSERT silently skips if the hash already exists, avoiding exceptions.
3. **Pre-check query (optional optimization)** — before batch generation, query existing hashes for the target period to skip known entries early, reducing unnecessary INSERT attempts.

### 4.5 Scheduling Strategy

| Method           | Trigger                           | Purpose                                  |
| ---------------- | --------------------------------- | ---------------------------------------- |
| **Cron job**     | Daily at `02:00 UTC`              | Primary: auto-generate upcoming entries  |
| **On-demand API**| `POST /generate`                  | Manual trigger, backfills, testing        |

**Cron job details:**

- Runs daily but only generates entries for the **current month** (for monthly+ frequencies) or the **current week** (for weekly/biweekly).
- Implemented via an external scheduler (e.g., `cron`, Celery Beat, or APScheduler) that calls the generation service function directly.
- The cron job is itself idempotent — safe to re-run on failure or restart.

```/dev/null/cron.py#L1-15
# Scheduled task — runs daily at 02:00 UTC
async def scheduled_generate_entries():
    """
    Batch generation of fixed expense entries.
    Idempotent: safe to retry on failure.
    """
    today = date.today()

    active_expenses = await repository.get_active_expenses()

    result = await generate_entries(target_date=today, expenses=active_expenses)

    logger.info(
        f"Scheduled generation complete: {result.generated_count} created, "
        f"{result.skipped_count} skipped, {len(result.errors)} errors"
    )
```

---

## 5. Error Handling

### 5.1 Error Codes & Messages

| HTTP Status | Code                          | Message                                                  | Trigger                                      |
| ----------- | ----------------------------- | -------------------------------------------------------- | -------------------------------------------- |
| `400`       | `VALIDATION_ERROR`            | Field-specific messages                                  | Invalid input (name empty, amount <= 0, etc.)|
| `400`       | `INVALID_FREQUENCY`           | `"Unsupported frequency: {value}"`                       | Frequency not in allowed enum                |
| `400`       | `INVALID_DAY_CONFIG`          | `"Weekly/biweekly requires day_of_week; others require day_of_month"` | Missing or conflicting day field |
| `400`       | `INVALID_DATE_RANGE`          | `"end_date must be on or after start_date"`              | `end_date < start_date`                      |
| `404`       | `NOT_FOUND`                   | `"Fixed expense {id} not found"`                         | ID does not exist                            |
| `409`       | `CONFLICT`                    | `"Entry already exists for this period"`                 | Explicit duplicate attempt (non-batch)       |
| `422`       | `UNPROCESSABLE_ENTITY`        | `"Referenced account_id does not exist"`                 | FK violation                                 |
| `500`       | `GENERATION_ERROR`            | `"Failed to generate entries. Check logs."`              | Unexpected failure during batch generation   |

### 5.2 Error Response Schema

```/dev/null/error.json#L1-8
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Human-readable summary",
        "details": [
            {"field": "amount", "message": "Must be greater than 0"}
        ]
    }
}
```

### 5.3 Logging Strategy

| Level    | When                                                        |
| -------- | ----------------------------------------------------------- |
| `INFO`   | Fixed expense created/updated/deactivated                   |
| `INFO`   | Generation batch completed (with counts)                    |
| `WARNING`| Entry skipped due to duplicate hash (expected but logged)   |
| `WARNING`| Day clamped (e.g., day 31 → 28 for February)               |
| `ERROR`  | Generation failed for a specific expense (with traceback)   |
| `ERROR`  | Database connection or constraint errors                    |

All log entries must include: `timestamp`, `level`, `fixed_expense_id` (when applicable), `correlation_id` (for batch operations).

---

## 6. Frontend Components

### 6.1 Component Tree

```/dev/null/tree.txt#L1-12
views/
  fixedExpenses/
    FixedExpensesView.vue          # Page-level route component

components/
  fixedExpenses/
    FixedExpenseList.vue            # Table/list of all fixed expenses
    FixedExpenseListItem.vue        # Single row in the list
    FixedExpenseForm.vue            # Create/edit form (modal or page)
    FixedExpenseEntries.vue         # Generated entries for one expense
    FixedExpenseEntryRow.vue        # Single entry row with status badge
    FixedExpenseGenerateButton.vue  # Trigger manual generation
```

### 6.2 Component Specifications

#### `FixedExpensesView`

- **Route:** `/fixed-expenses`
- **Responsibility:** Top-level layout. Fetches initial data, manages page-level state.
- **Contains:** `FixedExpenseList`, `FixedExpenseForm` (shown via modal toggle).

#### `FixedExpenseList`

- **Props:** none (fetches own data via composable)
- **State:** `fixedExpenses[]`, `isLoading`, `currentPage`, `filters`
- **Behavior:**
  - Paginated table with columns: Name, Amount, Frequency, Status (active/inactive), Actions.
  - Filter toggle for active/inactive.
  - Click row → expand to show `FixedExpenseEntries`.
  - "New Expense" button → opens `FixedExpenseForm`.

#### `FixedExpenseListItem`

- **Props:** `expense: FixedExpense`
- **Events:** `@edit`, `@delete`, `@toggle-entries`
- **Behavior:**
  - Displays formatted amount (BRL locale).
  - Frequency displayed as human-readable label (e.g., "Monthly", "Every 2 weeks").
  - Active/inactive badge.
  - Action buttons: Edit (pencil icon), Deactivate/Activate (toggle), Delete (trash icon with confirmation).

#### `FixedExpenseForm`

- **Props:** `expense?: FixedExpense` (null for create mode)
- **Events:** `@saved`, `@cancelled`
- **Behavior:**
  - Fields: `name` (text), `amount` (currency input), `frequency` (dropdown), `dayOfMonth`/`dayOfWeek` (conditional — shown based on frequency selection), `category` (dropdown), `startDate` (date picker), `endDate` (optional date picker), `description` (textarea).
  - Client-side validation before submit (mirrors backend rules).
  - On `frequency` change: toggle between `dayOfMonth` and `dayOfWeek` inputs.
  - Submit → `POST` (create) or `PATCH` (edit) → emit `@saved` on success.
  - Shows inline error messages from API response.

#### `FixedExpenseEntries`

- **Props:** `fixedExpenseId: string`
- **Behavior:**
  - Fetches entries via `GET /fixed-expenses/{id}/entries`.
  - Table with columns: Due Date, Amount, Status, Linked Transaction.
  - Status badge color: `pending` (yellow), `paid` (green), `skipped` (gray), `cancelled` (red).
  - Click status → dropdown to change status via `PATCH /entries/{id}`.

#### `FixedExpenseEntryRow`

- **Props:** `entry: FixedExpenseEntry`
- **Events:** `@status-changed`
- **Behavior:** Single row rendering with status dropdown and transaction link.

#### `FixedExpenseGenerateButton`

- **Props:** none
- **Behavior:**
  - Button labeled "Generate Entries".
  - Opens a small dialog: date picker for `targetDate` (defaults to current month).
  - On confirm → `POST /generate` → shows toast with `generated_count` / `skipped_count`.
  - Disabled state while request is in-flight.

### 6.3 Composable

```/dev/null/composable.ts#L1-30
// composables/useFixedExpenses.ts

interface UseFixedExpenses {
  fixedExpenses: Ref<FixedExpense[]>
  isLoading: Ref<boolean>
  error: Ref<string | null>
  totalPages: Ref<number>

  fetchExpenses(params: ListParams): Promise<void>
  createExpense(data: CreateFixedExpense): Promise<FixedExpense>
  updateExpense(id: string, data: Partial<FixedExpense>): Promise<FixedExpense>
  deleteExpense(id: string): Promise<void>
  fetchEntries(expenseId: string, params: EntryListParams): Promise<PaginatedEntries>
  updateEntryStatus(entryId: string, status: string, transactionId?: string): Promise<void>
  generateEntries(targetDate: string, expenseId?: string): Promise<GenerationResult>
}
```

### 6.4 TypeScript Interfaces (Frontend)

```/dev/null/types.ts#L1-36
interface FixedExpense {
  id: string
  accountId: string
  categoryId: string | null
  name: string
  description: string | null
  amount: number
  frequency: 'weekly' | 'biweekly' | 'monthly' | 'bimonthly' | 'quarterly' | 'semiannual' | 'annual'
  dayOfMonth: number | null
  dayOfWeek: number | null
  startDate: string
  endDate: string | null
  isActive: boolean
  createdAt: string
  updatedAt: string
}

interface FixedExpenseEntry {
  id: string
  fixedExpenseId: string
  referenceDate: string
  dueDate: string
  amount: number
  transactionId: string | null
  status: 'pending' | 'paid' | 'skipped' | 'cancelled'
  createdAt: string
  updatedAt: string
}

interface GenerationResult {
  generatedCount: number
  skippedCount: number
  errors: Array<{ fixedExpenseId: string; error: string }>
}
```

> **Naming convention:** All frontend interfaces use `camelCase` as per project rules. The API layer (composable) maps between `snake_case` responses and `camelCase` interfaces.

---

## 7. Backend Structure (FastAPI)

### 7.1 Module Layout

```/dev/null/layout.txt#L1-12
app/
  fixed_expenses/
    __init__.py
    router.py           # API route definitions
    schemas.py           # Pydantic request/response models
    models.py            # SQLAlchemy ORM models
    repository.py        # Database queries
    service.py           # Business logic (generation algorithm)
    exceptions.py        # Custom exception classes
  tasks/
    scheduler.py         # Cron job registration
    generate_entries.py  # Scheduled task implementation
```

### 7.2 Pydantic Schemas

```/dev/null/schemas.py#L1-52
from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Optional
from decimal import Decimal
from enum import Enum
import uuid


class FrequencyEnum(str, Enum):
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"
    bimonthly = "bimonthly"
    quarterly = "quarterly"
    semiannual = "semiannual"
    annual = "annual"


class FixedExpenseCreate(BaseModel):
    account_id: uuid.UUID
    category_id: Optional[uuid.UUID] = None
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    amount: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2)
    frequency: FrequencyEnum
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_date: date
    end_date: Optional[date] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v, info):
        if v is not None and "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("end_date must be on or after start_date")
        return v


class FixedExpenseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    amount: Optional[Decimal] = Field(None, gt=0, max_digits=14, decimal_places=2)
    frequency: Optional[FrequencyEnum] = None
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
```

### 7.3 Input Normalization

Per project rules ("Always normalize data before saving, never trust input formats"):

- `name` is stripped of leading/trailing whitespace.
- `amount` is rounded to 2 decimal places.
- `start_date` and `end_date` are parsed strictly as `YYYY-MM-DD`; any other format is rejected.
- `frequency` is lowercased and validated against the enum.

---

## 8. Non-Functional Requirements

### 8.1 Idempotency Guarantees

| Scenario                                   | Behavior                                        |
| ------------------------------------------ | ----------------------------------------------- |
| Cron runs twice in same day                | Second run generates 0, skips all (hash exists)  |
| API `/generate` called with same date      | Returns `generated_count: 0`, `skipped_count: N`|
| Two concurrent cron processes              | Only one INSERT wins per hash; no duplicates     |
| Server crash mid-generation                | Re-run safely produces only missing entries      |

### 8.2 Scheduling Reliability

- The cron job must be registered with a **distributed lock** (e.g., PostgreSQL advisory lock or Redis lock) to prevent overlapping runs in multi-instance deployments.
- If the cron job fails, it should be retried with exponential backoff (max 3 retries).
- A health-check endpoint or monitoring alert should fire if no generation run has succeeded in the last 48 hours.

### 8.3 Performance

- Generation batch should process up to **10,000 active expenses** within 30 seconds.
- Use bulk `INSERT ... ON CONFLICT DO NOTHING` (batches of 500 rows) instead of individual inserts.
- Database indexes on `generation_hash`, `fixed_expense_id`, and `reference_date` ensure fast lookups.

### 8.4 Data Integrity

- All generation operations run within a **single database transaction** per expense (not per batch) so that partial failures for one expense don't roll back others.
- Foreign key constraints ensure referential integrity between `fixed_expense_entries` → `fixed_expenses` and `fixed_expense_entries` → `transactions`.
- The `amount` column uses `NUMERIC(14, 2)` to avoid floating-point precision issues.

### 8.5 Observability

- Structured JSON logs with fields: `event`, `fixed_expense_id`, `batch_id`, `duration_ms`.
- Metrics to track: `generation_total` (counter), `generation_duration_seconds` (histogram), `generation_errors_total` (counter).
- Dashboard or alert on error rate > 5% of generation attempts.

---

## 9. Migration & Rollout Plan

1. **Database migration:** Create `fixed_expenses` and `fixed_expense_entries` tables (reversible migration).
2. **Backend deployment:** Ship API endpoints behind feature flag `FEATURE_FIXED_EXPENSES=true`.
3. **Cron registration:** Enable scheduled task only after backend is validated in production.
4. **Frontend deployment:** Ship UI components (route guarded by same feature flag).
5. **Feature flag removal:** After 1 week of stable operation, remove flag and make feature generally available.

---

## 10. Open Questions

| #  | Question                                                                 | Status  |
| -- | ------------------------------------------------------------------------ | ------- |
| 1  | Should generated entries auto-create transactions, or just link to them? | Open    |
| 2  | Do we need a "preview" endpoint to show what would be generated?         | Open    |
| 3  | Should users be able to edit the amount on individual entries?            | Open    |
| 4  | What timezone should be used for day/date calculations?                  | Open    |