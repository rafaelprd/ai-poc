# SPEC 3 — Transactions Management

> Technical Specification for PRD 3  
> Status: Draft  
> Last Updated: 2025-07-10

---

## Table of Contents

1. [Overview](#1-overview)
2. [API Endpoints](#2-api-endpoints)
3. [Data Models](#3-data-models)
4. [Business Logic](#4-business-logic)
5. [Error Handling](#5-error-handling)
6. [Frontend Components](#6-frontend-components)
7. [Non-Functional Requirements](#7-non-functional-requirements)

---

## 1. Overview

This specification covers the **Transactions Management** feature, which allows users to view, filter, and edit financial transactions. It maps directly to the three user stories in PRD 3:

| User Story | Summary |
|------------|---------|
| US1 | View a paginated, filterable list of transactions |
| US2 | Inline-edit a single transaction's category (only field editable per immutability rule) |
| US3 | Bulk-edit: select multiple transactions and apply a single category to all |

### Design Principles (from AGENTS.md)

- **Immutability**: Transaction records are immutable except for the `category_id` field.
- **Normalization**: All data is normalized before persistence.
- **Idempotency**: Update operations are idempotent — applying the same category twice produces no side effects.
- **Source of truth**: PostgreSQL database.
- **Input distrust**: All inputs are validated and sanitized server-side.

---

## 2. API Endpoints

Base path: `/api/v1/transactions`

### 2.1 List Transactions

**`GET /api/v1/transactions`**

Returns a paginated, filterable list of transactions.

#### Query Parameters

| Parameter       | Type     | Required | Default  | Description |
|-----------------|----------|----------|----------|-------------|
| `page`          | int      | No       | `1`      | Page number (1-based) |
| `page_size`     | int      | No       | `50`     | Items per page. Min: 1, Max: 200 |
| `date_from`     | string   | No       | —        | ISO 8601 date (`YYYY-MM-DD`). Inclusive lower bound. |
| `date_to`       | string   | No       | —        | ISO 8601 date (`YYYY-MM-DD`). Inclusive upper bound. |
| `category_id`   | int      | No       | —        | Filter by category. Use `0` for uncategorized. |
| `account_id`    | int      | No       | —        | Filter by account |
| `search`        | string   | No       | —        | Case-insensitive substring match on `description` |
| `sort_by`       | string   | No       | `date`   | Sort field. Allowed: `date`, `amount`, `description` |
| `sort_order`    | string   | No       | `desc`   | Sort direction. Allowed: `asc`, `desc` |

#### Response `200 OK`

```json
{
  "items": [
    {
      "id": 1024,
      "date": "2025-03-15",
      "description": "SUPERMERCADO EXTRA",
      "amount": -234.56,
      "category_id": 5,
      "category_name": "Alimentação",
      "account_id": 2,
      "account_name": "Nubank",
      "import_id": 10,
      "created_at": "2025-03-16T02:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_items": 1342,
    "total_pages": 27
  }
}
```

#### Status Codes

| Code | Condition |
|------|-----------|
| 200  | Success |
| 400  | Invalid query parameter value (e.g., bad date format, page < 1) |
| 422  | Validation error on parameter types |
| 500  | Internal server error |

---

### 2.2 Get Single Transaction

**`GET /api/v1/transactions/{transaction_id}`**

#### Path Parameters

| Parameter        | Type | Required | Description |
|------------------|------|----------|-------------|
| `transaction_id` | int  | Yes      | Transaction primary key |

#### Response `200 OK`

```json
{
  "id": 1024,
  "date": "2025-03-15",
  "description": "SUPERMERCADO EXTRA",
  "original_description": "SUPERMERCADO EXTRA  15/03",
  "amount": -234.56,
  "category_id": 5,
  "category_name": "Alimentação",
  "account_id": 2,
  "account_name": "Nubank",
  "import_id": 10,
  "created_at": "2025-03-16T02:30:00Z",
  "updated_at": "2025-03-17T10:00:00Z"
}
```

#### Status Codes

| Code | Condition |
|------|-----------|
| 200  | Success |
| 404  | Transaction not found |
| 500  | Internal server error |

---

### 2.3 Update Transaction Category (Single)

**`PATCH /api/v1/transactions/{transaction_id}`**

Only `category_id` is accepted in the request body. Any other fields are rejected to enforce immutability.

#### Path Parameters

| Parameter        | Type | Required | Description |
|------------------|------|----------|-------------|
| `transaction_id` | int  | Yes      | Transaction primary key |

#### Request Body

```json
{
  "category_id": 8
}
```

| Field         | Type     | Required | Description |
|---------------|----------|----------|-------------|
| `category_id` | int/null | Yes      | New category FK. `null` sets to uncategorized. |

#### Response `200 OK`

Returns the full updated transaction object (same schema as GET single).

#### Status Codes

| Code | Condition |
|------|-----------|
| 200  | Category updated successfully |
| 400  | Request body contains disallowed fields |
| 404  | Transaction not found |
| 422  | Invalid `category_id` (e.g., references non-existent category) |
| 500  | Internal server error |

---

### 2.4 Bulk Update Transaction Categories

**`PATCH /api/v1/transactions/bulk`**

Applies a single `category_id` to multiple transactions in one atomic operation.

#### Request Body

```json
{
  "transaction_ids": [101, 102, 103, 104],
  "category_id": 8
}
```

| Field             | Type      | Required | Constraints |
|-------------------|-----------|----------|-------------|
| `transaction_ids` | int[]     | Yes      | Min: 1, Max: 500 items. No duplicates. |
| `category_id`     | int/null  | Yes      | Must reference existing category, or `null` for uncategorized. |

#### Response `200 OK`

```json
{
  "updated_count": 4,
  "transaction_ids": [101, 102, 103, 104]
}
```

#### Response `207 Multi-Status` (partial failure)

```json
{
  "updated_count": 3,
  "transaction_ids": [101, 102, 104],
  "errors": [
    {
      "transaction_id": 103,
      "error": "TRANSACTION_NOT_FOUND",
      "message": "Transaction with id 103 does not exist"
    }
  ]
}
```

#### Status Codes

| Code | Condition |
|------|-----------|
| 200  | All transactions updated |
| 207  | Partial success — some IDs not found |
| 400  | Empty `transaction_ids`, exceeds 500 limit, or contains duplicates |
| 422  | Invalid `category_id` |
| 500  | Internal server error |

---

### 2.5 List Categories (supporting endpoint)

**`GET /api/v1/categories`**

Returns all categories for use in filter dropdowns and category selectors.

#### Response `200 OK`

```json
{
  "items": [
    { "id": 1, "name": "Alimentação", "color": "#4CAF50" },
    { "id": 2, "name": "Transporte", "color": "#2196F3" }
  ]
}
```

---

### 2.6 List Accounts (supporting endpoint)

**`GET /api/v1/accounts`**

Returns all accounts for use in filter dropdowns.

#### Response `200 OK`

```json
{
  "items": [
    { "id": 1, "name": "Nubank" },
    { "id": 2, "name": "Itaú" }
  ]
}
```

---

## 3. Data Models

### 3.1 `transactions` Table

```sql
CREATE TABLE transactions (
    id              SERIAL          PRIMARY KEY,
    date            DATE            NOT NULL,
    description     VARCHAR(500)    NOT NULL,
    original_description VARCHAR(500) NOT NULL,
    amount          NUMERIC(14,2)   NOT NULL,
    category_id     INTEGER         REFERENCES categories(id) ON DELETE SET NULL,
    account_id      INTEGER         NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    import_id       INTEGER         NOT NULL REFERENCES imports(id) ON DELETE RESTRICT,
    hash            VARCHAR(64)     NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON COLUMN transactions.description IS 'Normalized description (trimmed, uppercased, cleaned)';
COMMENT ON COLUMN transactions.original_description IS 'Raw description as it appeared in the source file';
COMMENT ON COLUMN transactions.hash IS 'SHA-256 of (date + original_description + amount + account_id) for deduplication';
COMMENT ON COLUMN transactions.updated_at IS 'Only changes when category_id is updated';
```

#### Indexes

```sql
-- Primary query: date-sorted paginated listing
CREATE INDEX idx_transactions_date_desc ON transactions (date DESC, id DESC);

-- Filter by category
CREATE INDEX idx_transactions_category_id ON transactions (category_id);

-- Filter by account
CREATE INDEX idx_transactions_account_id ON transactions (account_id);

-- Filter by date range + account (composite for common query pattern)
CREATE INDEX idx_transactions_account_date ON transactions (account_id, date DESC);

-- Search by description (trigram for substring/ILIKE support)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_transactions_description_trgm ON transactions
    USING gin (description gin_trgm_ops);

-- Deduplication lookup during import
CREATE UNIQUE INDEX idx_transactions_hash ON transactions (hash);
```

### 3.2 `categories` Table

```sql
CREATE TABLE categories (
    id          SERIAL          PRIMARY KEY,
    name        VARCHAR(100)    NOT NULL UNIQUE,
    color       VARCHAR(7)      NOT NULL DEFAULT '#9E9E9E',
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
```

### 3.3 `accounts` Table

```sql
CREATE TABLE accounts (
    id          SERIAL          PRIMARY KEY,
    name        VARCHAR(100)    NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
```

### 3.4 `imports` Table (reference only)

```sql
CREATE TABLE imports (
    id              SERIAL          PRIMARY KEY,
    filename        VARCHAR(255)    NOT NULL,
    file_type       VARCHAR(10)     NOT NULL CHECK (file_type IN ('csv', 'pdf')),
    row_count       INTEGER         NOT NULL DEFAULT 0,
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
```

### 3.5 `transaction_audit_log` Table

Tracks every category change for audit purposes.

```sql
CREATE TABLE transaction_audit_log (
    id                  SERIAL          PRIMARY KEY,
    transaction_id      INTEGER         NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    old_category_id     INTEGER         REFERENCES categories(id),
    new_category_id     INTEGER         REFERENCES categories(id),
    changed_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_transaction_id ON transaction_audit_log (transaction_id);
```

---

## 4. Business Logic

### 4.1 Pagination Strategy

**Approach: Offset-based pagination** using `LIMIT` / `OFFSET`.

Rationale:
- Simpler for the frontend to implement page-number navigation.
- Transaction lists are typically filtered by date range, keeping result sets manageable.
- Acceptable performance for datasets up to ~1M rows with proper indexing.

```sql
-- Example generated query
SELECT
    t.id, t.date, t.description, t.amount,
    t.category_id, c.name AS category_name,
    t.account_id, a.name AS account_name,
    t.import_id, t.created_at
FROM transactions t
LEFT JOIN categories c ON t.category_id = c.id
JOIN accounts a ON t.account_id = a.id
WHERE t.date >= :date_from
  AND t.date <= :date_to
  AND t.account_id = :account_id
ORDER BY t.date DESC, t.id DESC
LIMIT :page_size OFFSET :offset;
```

Count query runs in parallel:

```sql
SELECT COUNT(*) FROM transactions t
WHERE t.date >= :date_from
  AND t.date <= :date_to
  AND t.account_id = :account_id;
```

> **Future consideration**: If total row count exceeds 1M, migrate to cursor-based pagination using `(date, id)` as the cursor key.

### 4.2 Filtering Logic

All filters are **AND-combined**. Empty/omitted filters are ignored (no restriction on that dimension).

| Filter          | SQL Clause                                          |
|-----------------|-----------------------------------------------------|
| `date_from`     | `t.date >= :date_from`                              |
| `date_to`       | `t.date <= :date_to`                                |
| `category_id`   | `t.category_id = :category_id` (use `IS NULL` for `0`) |
| `account_id`    | `t.account_id = :account_id`                        |
| `search`        | `t.description ILIKE '%' \|\| :search \|\| '%'`     |

**Input normalization before filtering:**
- `date_from` / `date_to`: Parse and validate as ISO 8601 dates. Reject if `date_from > date_to`.
- `search`: Strip leading/trailing whitespace. Escape SQL wildcards (`%`, `_`). Max length: 100 characters.
- `category_id=0`: Mapped to `WHERE t.category_id IS NULL` (uncategorized transactions).

### 4.3 Immutability Enforcement

**Rule**: Only `category_id` and `updated_at` may be modified after a transaction is created.

Enforcement layers:

1. **API layer** (FastAPI): The `PATCH` request body schema (`TransactionUpdateSchema`) allows only `category_id`. Any extra fields in the body trigger a `400 Bad Request`.

    ```python
    class TransactionUpdateSchema(BaseModel):
        category_id: Optional[int] = None

        class Config:
            extra = "forbid"  # Rejects any field not declared
    ```

2. **Database layer**: The UPDATE query explicitly sets only `category_id` and `updated_at`:

    ```sql
    UPDATE transactions
    SET category_id = :category_id,
        updated_at = NOW()
    WHERE id = :transaction_id;
    ```

3. **Audit trail**: Every category change is logged to `transaction_audit_log` within the same database transaction.

### 4.4 Single Update Logic

```
1. Validate category_id exists in categories table (or is null).
2. Fetch transaction by id → 404 if not found.
3. If transaction.category_id == new category_id → return current state (idempotent, no write).
4. BEGIN transaction:
   a. INSERT into transaction_audit_log (old_category_id, new_category_id).
   b. UPDATE transactions SET category_id, updated_at.
5. COMMIT.
6. Return updated transaction.
```

### 4.5 Bulk Update Logic

```
1. Validate request:
   a. transaction_ids is not empty and has ≤ 500 items.
   b. No duplicate IDs in the array.
   c. category_id exists in categories table (or is null).
2. BEGIN transaction:
   a. SELECT id, category_id FROM transactions WHERE id = ANY(:transaction_ids) FOR UPDATE.
   b. Identify found_ids and missing_ids.
   c. Filter out transactions where category_id already matches (idempotent — skip unchanged).
   d. For changed transactions: batch INSERT into transaction_audit_log.
   e. UPDATE transactions SET category_id, updated_at WHERE id = ANY(:changed_ids).
3. COMMIT.
4. If missing_ids is empty → 200 OK.
5. If missing_ids is not empty → 207 Multi-Status with errors array.
```

**Atomicity**: All updates within a single bulk request succeed or fail together (excluding non-existent IDs, which are reported separately).

**Idempotency**: Re-sending the same bulk request with the same `category_id` is a no-op for already-matching transactions. No duplicate audit log entries are created.

---

## 5. Error Handling

### 5.1 Error Response Schema

All error responses follow a consistent structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description of the error",
    "details": [
      {
        "field": "date_from",
        "message": "Invalid date format. Expected YYYY-MM-DD."
      }
    ]
  }
}
```

### 5.2 Error Codes

| Code                        | HTTP Status | Trigger |
|-----------------------------|-------------|---------|
| `VALIDATION_ERROR`          | 400         | Malformed request parameters or body |
| `DISALLOWED_FIELDS`         | 400         | PATCH body contains fields other than `category_id` |
| `TRANSACTION_NOT_FOUND`     | 404         | Transaction ID does not exist |
| `CATEGORY_NOT_FOUND`        | 422         | Referenced `category_id` does not exist |
| `BULK_LIMIT_EXCEEDED`       | 400         | `transaction_ids` array exceeds 500 items |
| `DUPLICATE_IDS`             | 400         | `transaction_ids` contains duplicate values |
| `INVALID_DATE_RANGE`        | 400         | `date_from` is after `date_to` |
| `INVALID_SORT_FIELD`        | 400         | `sort_by` is not one of the allowed values |
| `INTERNAL_ERROR`            | 500         | Unhandled server exception |

### 5.3 Logging Strategy

| Level    | What to Log |
|----------|-------------|
| `INFO`   | Every successful category update (single and bulk): transaction ID(s), old category, new category |
| `INFO`   | List requests with active filters (for analytics on usage patterns) |
| `WARNING`| Bulk update with partial failures (207 response) |
| `WARNING`| Requests with disallowed fields in PATCH body |
| `ERROR`  | Database connection failures, query timeouts, unhandled exceptions |

Log format (structured JSON):

```json
{
  "timestamp": "2025-03-17T10:00:00Z",
  "level": "INFO",
  "event": "transaction_category_updated",
  "transaction_id": 1024,
  "old_category_id": 5,
  "new_category_id": 8,
  "source": "single_update"
}
```

---

## 6. Frontend Components

All component names follow **camelCase** convention per AGENTS.md.

### 6.1 Component Tree

```
transactionPage
├── transactionFilters
│   ├── dateRangePicker
│   ├── categorySelect
│   ├── accountSelect
│   └── searchInput
├── transactionTable
│   ├── transactionRow
│   │   └── categoryInlineEditor
│   └── bulkActionBar
└── paginationControls
```

### 6.2 Component Specifications

#### `transactionPage`

- **Path**: `src/pages/transactionPage.vue`
- **Responsibility**: Top-level page layout. Orchestrates data fetching, filter state, and selection state.
- **State**: Holds reactive `filters`, `pagination`, `selectedIds`, and `transactions` array.
- **Behavior**:
  - On mount: fetch transactions with default filters (current month, page 1).
  - On filter change: reset to page 1, re-fetch.
  - Provides filter + selection state to child components via props / provide-inject.

#### `transactionFilters`

- **Path**: `src/components/transactions/transactionFilters.vue`
- **Responsibility**: Renders filter controls and emits filter-change events.
- **Props**: `currentFilters` (object with current filter values).
- **Emits**: `@update:filters` with the full updated filter object.
- **Behavior**:
  - Debounces `search` input by 300ms before emitting.
  - Date pickers default to current month range.
  - Category and account dropdowns populated from `/api/v1/categories` and `/api/v1/accounts` (fetched once on mount, cached).

#### `dateRangePicker`

- **Path**: `src/components/common/dateRangePicker.vue`
- **Responsibility**: Two date inputs (from / to) with validation.
- **Props**: `dateFrom`, `dateTo`.
- **Emits**: `@update:dateFrom`, `@update:dateTo`.
- **Validation**: Prevents `dateFrom > dateTo` client-side.

#### `categorySelect`

- **Path**: `src/components/common/categorySelect.vue`
- **Responsibility**: Dropdown to select a category. Reused in filters and inline editor.
- **Props**: `modelValue` (selected category ID), `categories` (array), `allowNull` (shows "Uncategorized" option), `placeholder`.
- **Emits**: `@update:modelValue`.

#### `accountSelect`

- **Path**: `src/components/common/accountSelect.vue`
- **Responsibility**: Dropdown to select an account for filtering.
- **Props**: `modelValue`, `accounts` (array).
- **Emits**: `@update:modelValue`.

#### `searchInput`

- **Path**: `src/components/common/searchInput.vue`
- **Responsibility**: Text input with debounce for description search.
- **Props**: `modelValue`, `debounceMs` (default: 300).
- **Emits**: `@update:modelValue` (debounced).

#### `transactionTable`

- **Path**: `src/components/transactions/transactionTable.vue`
- **Responsibility**: Renders the transaction list as a table. Manages row selection state.
- **Props**: `transactions` (array), `selectedIds` (Set), `loading` (boolean), `sortBy`, `sortOrder`.
- **Emits**: `@update:selectedIds`, `@update:sortBy`, `@update:sortOrder`.
- **Behavior**:
  - Header row with "select all" checkbox (selects current page only).
  - Column headers are clickable for sorting (`date`, `amount`, `description`).
  - Shows skeleton rows while `loading` is true.
  - Empty state message when no transactions match filters.

#### `transactionRow`

- **Path**: `src/components/transactions/transactionRow.vue`
- **Responsibility**: Renders a single transaction row with inline category editing.
- **Props**: `transaction` (object), `selected` (boolean), `categories` (array).
- **Emits**: `@toggle-select`, `@category-updated`.
- **Behavior**:
  - Checkbox for multi-select.
  - Category cell shows current category as a **clickable chip**; clicking opens `categoryInlineEditor`.
  - Amount displayed with locale formatting: negative values in red, positive in green.
  - Date formatted as `DD/MM/YYYY` (Brazilian locale).

#### `categoryInlineEditor`

- **Path**: `src/components/transactions/categoryInlineEditor.vue`
- **Responsibility**: Inline dropdown that replaces the category chip in edit mode.
- **Props**: `transactionId` (int), `currentCategoryId` (int/null), `categories` (array).
- **Emits**: `@saved` (with updated transaction), `@cancel`.
- **Behavior**:
  - Opens as a dropdown overlay on click.
  - On selection: immediately calls `PATCH /api/v1/transactions/{id}`.
  - Shows loading spinner during save.
  - On success: emits `@saved`, closes editor, shows brief success toast.
  - On error: shows inline error message, keeps editor open.
  - Clicking outside or pressing `Escape` cancels (emits `@cancel`).

#### `bulkActionBar`

- **Path**: `src/components/transactions/bulkActionBar.vue`
- **Responsibility**: Sticky bar that appears when 1+ transactions are selected.
- **Props**: `selectedCount` (int), `categories` (array).
- **Emits**: `@bulk-update` (with `{ categoryId }`), `@clear-selection`.
- **Behavior**:
  - Shows: "{N} transactions selected".
  - Category dropdown + "Apply" button.
  - "Clear selection" link.
  - On "Apply": calls `PATCH /api/v1/transactions/bulk`.
  - Shows confirmation dialog before applying if `selectedCount > 20`.
  - Shows success/error toast after completion.
  - On 207 response: shows warning toast with count of failed IDs.

#### `paginationControls`

- **Path**: `src/components/common/paginationControls.vue`
- **Responsibility**: Page navigation (previous / next / page numbers).
- **Props**: `page`, `pageSize`, `totalItems`, `totalPages`.
- **Emits**: `@update:page`, `@update:pageSize`.
- **Behavior**:
  - Shows page numbers with ellipsis for large page counts.
  - Page size selector: 25 / 50 / 100 / 200.
  - Changing page size resets to page 1.
  - Clears selection when navigating pages.

### 6.3 State Management

Use Vue 3 composables (no Pinia required for this scope):

#### `useTransactions` composable

- **Path**: `src/composables/useTransactions.ts`
- **Exports**: `transactions`, `pagination`, `loading`, `error`, `fetchTransactions(filters, page, pageSize)`, `updateCategory(transactionId, categoryId)`, `bulkUpdateCategory(transactionIds, categoryId)`.
- **Behavior**: Wraps all API calls. Manages loading/error state. Optimistically updates local state on successful category change.

#### `useCategories` composable

- **Path**: `src/composables/useCategories.ts`
- **Exports**: `categories`, `loading`, `fetchCategories()`.
- **Behavior**: Fetches once, caches in memory. Refreshed only on explicit call.

#### `useAccounts` composable

- **Path**: `src/composables/useAccounts.ts`
- **Exports**: `accounts`, `loading`, `fetchAccounts()`.
- **Behavior**: Same caching strategy as `useCategories`.

### 6.4 API Client

- **Path**: `src/api/transactionsApi.ts`
- Uses `fetch` or `axios` (project choice).
- All API functions return typed responses.
- Centralized error interceptor maps HTTP errors to user-facing messages.

---

## 7. Non-Functional Requirements

### 7.1 Pagination Limits

| Parameter  | Min | Default | Max | Rationale |
|------------|-----|---------|-----|-----------|
| `page`     | 1   | 1       | —   | No upper limit; validated against total_pages |
| `page_size`| 1   | 50      | 200 | Caps payload size; 200 rows ≈ 40KB JSON |

### 7.2 Bulk Operation Limits

| Constraint            | Value | Rationale |
|-----------------------|-------|-----------|
| Max IDs per bulk call | 500   | Prevents oversized DB transactions; keeps lock time < 200ms |
| Max concurrent bulk requests | 1 per user | Frontend disables button during request |

### 7.3 Query Performance Targets

| Operation              | Target (p95) | Notes |
|------------------------|--------------|-------|
| List (filtered, paginated) | < 200ms | With indexes; up to 1M rows |
| COUNT query            | < 150ms      | Parallel with main query |
| Single update          | < 100ms      | Single row UPDATE + audit INSERT |
| Bulk update (500 IDs)  | < 500ms      | Batch UPDATE + batch audit INSERT |
| Category/account list  | < 50ms       | Small tables, cached by frontend |

### 7.4 Payload Size Limits

| Constraint              | Value |
|--------------------------|-------|
| Max response body (list) | ~200KB (200 rows) |
| Max request body (bulk)  | ~8KB (500 int IDs + category) |

### 7.5 Reliability

- **Idempotency**: Re-sending any PATCH request with the same data produces no side effects and returns the same response.
- **Atomicity**: Bulk updates are wrapped in a single database transaction. Either all valid IDs update or none do (excluding genuinely missing IDs, which are reported).
- **Concurrency**: `SELECT ... FOR UPDATE` prevents race conditions during bulk updates on the same rows.

### 7.6 Observability

- All API endpoints emit structured JSON logs (see §5.3).
- Response time tracked per endpoint via middleware.
- Alert threshold: p99 latency > 1s on list endpoint triggers investigation.

---

## Appendix A: Backend File Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── transactions.py      # Router with all transaction endpoints
│   │       ├── categories.py        # Router for category list
│   │       └── accounts.py          # Router for account list
│   ├── models/
│   │   ├── transaction.py           # SQLAlchemy model
│   │   ├── category.py
│   │   ├── account.py
│   │   └── transaction_audit_log.py
│   ├── schemas/
│   │   ├── transaction.py           # Pydantic request/response schemas
│   │   ├── category.py
│   │   └── pagination.py
│   ├── services/
│   │   └── transaction_service.py   # Business logic (update, bulk update)
│   └── core/
│       └── exceptions.py            # Custom exception classes + handlers
```

## Appendix B: Frontend File Structure

```
frontend/src/
├── pages/
│   └── transactionPage.vue
├── components/
│   ├── transactions/
│   │   ├── transactionFilters.vue
│   │   ├── transactionTable.vue
│   │   ├── transactionRow.vue
│   │   ├── categoryInlineEditor.vue
│   │   └── bulkActionBar.vue
│   └── common/
│       ├── dateRangePicker.vue
│       ├── categorySelect.vue
│       ├── accountSelect.vue
│       ├── searchInput.vue
│       └── paginationControls.vue
├── composables/
│   ├── useTransactions.ts
│   ├── useCategories.ts
│   └── useAccounts.ts
└── api/
    └── transactionsApi.ts
```
