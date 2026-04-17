# SPEC 2 — Categorization

> Technical Specification for PRD 2 — Categorization
>
> Status: Draft
> Created: 2025-01-20
> Related PRDs: PRD1 (Ingestion), PRD2 (Categorization), PRD3 (Transactions)

---

## 1. Overview

The Categorization system automatically assigns categories to financial transactions using a rule-based engine and allows users to override, create, and manage categorization rules. The system learns from user overrides by persisting new keyword-to-category mappings so that future similar transactions are categorized automatically.

### Scope

| In Scope                                      | Out of Scope                          |
| --------------------------------------------- | ------------------------------------- |
| Keyword-based auto-categorization             | ML/AI-based categorization (Phase 2)  |
| User category overrides on transactions       | Multi-user / role-based rule scoping  |
| CRUD for categorization rules                 | Cross-account rule inheritance        |
| Learning from overrides (rule auto-creation)  | Natural language rule definitions     |
| Batch re-categorization of existing data      | Real-time streaming categorization    |
| "Uncategorized" fallback for unknown entries  | Scheduled / cron-based re-processing  |

### Design Principles (from AGENTS.md)

- **Transactions are immutable** except for category edits.
- **Batch-oriented** data pipeline — categorization runs on sets of transactions.
- **Source of truth**: PostgreSQL database.
- **Normalize before saving** — keywords are lowercased/trimmed before storage.
- **Never trust input formats** — all inputs are validated and sanitized.
- **Idempotent operations** — re-running categorization produces the same result.

---

## 2. Data Models

### 2.1 `categories` Table

Stores the canonical set of categories available in the system.

```sql
CREATE TABLE categories (
    id            SERIAL        PRIMARY KEY,
    name          VARCHAR(100)  NOT NULL UNIQUE,
    color         VARCHAR(7)    NOT NULL DEFAULT '#6B7280',  -- hex color for UI
    icon          VARCHAR(50)   NULL,                        -- optional icon identifier
    is_system     BOOLEAN       NOT NULL DEFAULT FALSE,      -- TRUE for "Uncategorized" etc.
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Seed the mandatory system category
INSERT INTO categories (name, color, is_system)
VALUES ('Uncategorized', '#9CA3AF', TRUE);
```

| Column     | Type          | Constraints              | Notes                                     |
| ---------- | ------------- | ------------------------ | ----------------------------------------- |
| id         | SERIAL        | PK                       | Auto-increment                            |
| name       | VARCHAR(100)  | NOT NULL, UNIQUE         | Display name, normalized on write         |
| color      | VARCHAR(7)    | NOT NULL, DEFAULT        | Hex color code for frontend badges        |
| icon       | VARCHAR(50)   | NULL                     | Optional icon key (e.g., `"shopping"`)    |
| is_system  | BOOLEAN       | NOT NULL, DEFAULT FALSE  | Prevents deletion of system categories    |
| created_at | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()  |                                           |
| updated_at | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()  | Updated via trigger or application layer  |

### 2.2 `categorization_rules` Table

Stores keyword-to-category mapping rules. Rules can be user-created or auto-learned from overrides.

```sql
CREATE TABLE categorization_rules (
    id            SERIAL        PRIMARY KEY,
    keyword       VARCHAR(255)  NOT NULL,
    category_id   INTEGER       NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    match_type    VARCHAR(20)   NOT NULL DEFAULT 'contains'
                                CHECK (match_type IN ('exact', 'contains', 'starts_with', 'ends_with')),
    priority      INTEGER       NOT NULL DEFAULT 0,
    source        VARCHAR(20)   NOT NULL DEFAULT 'manual'
                                CHECK (source IN ('manual', 'learned', 'system')),
    is_active     BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_keyword_match UNIQUE (keyword, match_type)
);

CREATE INDEX idx_rules_active     ON categorization_rules (is_active) WHERE is_active = TRUE;
CREATE INDEX idx_rules_category   ON categorization_rules (category_id);
CREATE INDEX idx_rules_priority   ON categorization_rules (priority DESC);
```

| Column      | Type          | Constraints                         | Notes                                              |
| ----------- | ------------- | ----------------------------------- | -------------------------------------------------- |
| id          | SERIAL        | PK                                  |                                                    |
| keyword     | VARCHAR(255)  | NOT NULL                            | Stored lowercase/trimmed (normalized)              |
| category_id | INTEGER       | FK → categories.id, ON DELETE CASCADE | Target category                                  |
| match_type  | VARCHAR(20)   | NOT NULL, CHECK                     | `exact`, `contains`, `starts_with`, `ends_with`    |
| priority    | INTEGER       | NOT NULL, DEFAULT 0                 | Higher value = higher priority                     |
| source      | VARCHAR(20)   | NOT NULL, CHECK                     | `manual` (user-created), `learned` (from override), `system` (seed) |
| is_active   | BOOLEAN       | NOT NULL, DEFAULT TRUE              | Soft-disable without deletion                      |
| created_at  | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()             |                                                    |
| updated_at  | TIMESTAMPTZ   | NOT NULL, DEFAULT NOW()             |                                                    |

### 2.3 `transactions` Table — Category Columns (partial, relevant fields only)

The `transactions` table is defined in SPEC 1 / SPEC 3. Categorization adds/uses these columns:

```sql
ALTER TABLE transactions
    ADD COLUMN category_id          INTEGER       REFERENCES categories(id) ON DELETE SET NULL,
    ADD COLUMN categorized_at       TIMESTAMPTZ   NULL,
    ADD COLUMN categorization_source VARCHAR(20)  NULL
                                    CHECK (categorization_source IN ('auto', 'manual', 'bulk'));

CREATE INDEX idx_transactions_category ON transactions (category_id);
```

| Column                 | Type         | Notes                                          |
| ---------------------- | ------------ | ----------------------------------------------- |
| category_id            | INTEGER      | FK → categories.id; NULL means uncategorized    |
| categorized_at         | TIMESTAMPTZ  | When the category was last set                  |
| categorization_source  | VARCHAR(20)  | `auto`, `manual` (user override), `bulk`        |

---

## 3. API Endpoints

Base path: `/api/v1`

### 3.1 Categories

#### `GET /api/v1/categories`

List all categories.

**Query Parameters:**

| Param     | Type    | Default | Description                       |
| --------- | ------- | ------- | --------------------------------- |
| include_system | bool | true  | Include system categories like "Uncategorized" |

**Response `200 OK`:**

```json
{
  "data": [
    {
      "id": 1,
      "name": "Uncategorized",
      "color": "#9CA3AF",
      "icon": null,
      "is_system": true,
      "created_at": "2025-01-20T10:00:00Z",
      "updated_at": "2025-01-20T10:00:00Z"
    },
    {
      "id": 2,
      "name": "Groceries",
      "color": "#10B981",
      "icon": "shopping-cart",
      "is_system": false,
      "created_at": "2025-01-20T10:05:00Z",
      "updated_at": "2025-01-20T10:05:00Z"
    }
  ],
  "total": 2
}
```

---

#### `POST /api/v1/categories`

Create a new category.

**Request Body:**

```json
{
  "name": "Groceries",
  "color": "#10B981",
  "icon": "shopping-cart"
}
```

| Field | Type   | Required | Validation                              |
| ----- | ------ | -------- | --------------------------------------- |
| name  | string | Yes      | 1–100 chars, trimmed, unique (case-insensitive) |
| color | string | No       | Hex color `/^#[0-9A-Fa-f]{6}$/`, default `#6B7280` |
| icon  | string | No       | Max 50 chars                            |

**Response `201 Created`:** Returns created category object.

**Error Responses:**

| Status | Code                     | Condition                  |
| ------ | ------------------------ | -------------------------- |
| 400    | `INVALID_CATEGORY_NAME`  | Name empty or too long     |
| 400    | `INVALID_COLOR_FORMAT`   | Color not valid hex        |
| 409    | `CATEGORY_ALREADY_EXISTS`| Duplicate name             |

---

#### `PUT /api/v1/categories/{category_id}`

Update an existing category.

**Request Body:** Same schema as `POST` (all fields optional).

**Response `200 OK`:** Returns updated category object.

**Error Responses:**

| Status | Code                      | Condition                          |
| ------ | ------------------------- | ---------------------------------- |
| 404    | `CATEGORY_NOT_FOUND`      | ID does not exist                  |
| 403    | `SYSTEM_CATEGORY_PROTECTED`| Attempt to rename system category |
| 409    | `CATEGORY_ALREADY_EXISTS` | Name conflict with another category|

---

#### `DELETE /api/v1/categories/{category_id}`

Delete a category. Transactions using this category will have `category_id` set to `NULL` (via `ON DELETE SET NULL`), effectively becoming uncategorized. Associated rules are cascade-deleted.

**Response `204 No Content`**

**Error Responses:**

| Status | Code                       | Condition                            |
| ------ | -------------------------- | ------------------------------------ |
| 404    | `CATEGORY_NOT_FOUND`       | ID does not exist                    |
| 403    | `SYSTEM_CATEGORY_PROTECTED`| Attempt to delete system category    |

---

### 3.2 Categorization Rules

#### `GET /api/v1/rules`

List categorization rules with optional filtering.

**Query Parameters:**

| Param       | Type    | Default | Description                             |
| ----------- | ------- | ------- | --------------------------------------- |
| category_id | int     | —       | Filter by category                      |
| source      | string  | —       | Filter by source: `manual`, `learned`, `system` |
| is_active   | bool    | —       | Filter by active status                 |
| search      | string  | —       | Search keyword field (case-insensitive) |
| page        | int     | 1       | Page number (1-based)                   |
| page_size   | int     | 50      | Items per page, max 200                 |
| sort_by     | string  | `priority` | `priority`, `keyword`, `created_at`  |
| sort_order  | string  | `desc`  | `asc` or `desc`                         |

**Response `200 OK`:**

```json
{
  "data": [
    {
      "id": 1,
      "keyword": "supermarket",
      "category_id": 2,
      "category_name": "Groceries",
      "match_type": "contains",
      "priority": 10,
      "source": "manual",
      "is_active": true,
      "created_at": "2025-01-20T10:00:00Z",
      "updated_at": "2025-01-20T10:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

---

#### `POST /api/v1/rules`

Create a new categorization rule.

**Request Body:**

```json
{
  "keyword": "supermarket",
  "category_id": 2,
  "match_type": "contains",
  "priority": 10
}
```

| Field       | Type   | Required | Validation                                         |
| ----------- | ------ | -------- | -------------------------------------------------- |
| keyword     | string | Yes      | 1–255 chars; normalized to lowercase/trimmed on save|
| category_id | int    | Yes      | Must reference existing category                   |
| match_type  | string | No       | One of `exact`, `contains`, `starts_with`, `ends_with`; default `contains` |
| priority    | int    | No       | Integer ≥ 0; default `0`                           |

**Response `201 Created`:** Returns created rule object.

**Error Responses:**

| Status | Code                    | Condition                              |
| ------ | ----------------------- | -------------------------------------- |
| 400    | `INVALID_KEYWORD`       | Keyword empty or too long              |
| 400    | `INVALID_MATCH_TYPE`    | Unrecognized match_type value          |
| 404    | `CATEGORY_NOT_FOUND`    | Referenced category does not exist     |
| 409    | `RULE_ALREADY_EXISTS`   | Same keyword + match_type combination  |

---

#### `PUT /api/v1/rules/{rule_id}`

Update an existing rule. All fields optional.

**Request Body:**

```json
{
  "keyword": "grocery store",
  "category_id": 3,
  "match_type": "contains",
  "priority": 20,
  "is_active": true
}
```

**Response `200 OK`:** Returns updated rule object.

**Error Responses:**

| Status | Code                  | Condition              |
| ------ | --------------------- | ---------------------- |
| 404    | `RULE_NOT_FOUND`      | ID does not exist      |
| 409    | `RULE_ALREADY_EXISTS` | Duplicate keyword+match|

---

#### `DELETE /api/v1/rules/{rule_id}`

Delete a categorization rule.

**Response `204 No Content`**

**Error Responses:**

| Status | Code             | Condition         |
| ------ | ---------------- | ------------------|
| 404    | `RULE_NOT_FOUND` | ID does not exist |

---

### 3.3 Transaction Categorization Actions

#### `POST /api/v1/transactions/{transaction_id}/categorize`

User overrides (or sets) the category of a single transaction. This is the **US2 — User Override** endpoint. If `learn_rule` is `true` (default), a new `learned` rule is auto-created from the transaction description.

**Request Body:**

```json
{
  "category_id": 2,
  "learn_rule": true
}
```

| Field       | Type | Required | Validation                           |
| ----------- | ---- | -------- | ------------------------------------ |
| category_id | int  | Yes      | Must reference existing category     |
| learn_rule  | bool | No       | Default `true`; creates a learned rule from the transaction description |

**Response `200 OK`:**

```json
{
  "transaction_id": 42,
  "category_id": 2,
  "category_name": "Groceries",
  "categorization_source": "manual",
  "categorized_at": "2025-01-20T14:30:00Z",
  "learned_rule": {
    "id": 15,
    "keyword": "pao de acucar",
    "match_type": "contains",
    "source": "learned"
  }
}
```

If `learn_rule` is `false` or a matching rule already exists, `learned_rule` is `null`.

**Error Responses:**

| Status | Code                    | Condition                        |
| ------ | ----------------------- | -------------------------------- |
| 404    | `TRANSACTION_NOT_FOUND` | Transaction ID does not exist    |
| 404    | `CATEGORY_NOT_FOUND`    | Category ID does not exist       |

---

#### `POST /api/v1/transactions/categorize-bulk`

Apply category to multiple transactions at once (supports PRD 3 US3 — Bulk edit).

**Request Body:**

```json
{
  "transaction_ids": [1, 2, 3, 4],
  "category_id": 5,
  "learn_rule": false
}
```

| Field           | Type   | Required | Validation                     |
| --------------- | ------ | -------- | ------------------------------ |
| transaction_ids | int[]  | Yes      | 1–500 IDs per request          |
| category_id     | int    | Yes      | Must reference existing category|
| learn_rule      | bool   | No       | Default `false` for bulk       |

**Response `200 OK`:**

```json
{
  "updated_count": 4,
  "category_id": 5,
  "category_name": "Transportation"
}
```

**Error Responses:**

| Status | Code                     | Condition                          |
| ------ | ------------------------ | ---------------------------------- |
| 400    | `EMPTY_TRANSACTION_LIST` | Empty array                        |
| 400    | `TOO_MANY_TRANSACTIONS`  | More than 500 IDs                  |
| 404    | `CATEGORY_NOT_FOUND`     | Category ID does not exist         |

---

#### `POST /api/v1/categorize/run`

Trigger the batch categorization engine to process uncategorized transactions (or re-process all). Supports **US1 — Auto Categorization**.

**Request Body:**

```json
{
  "scope": "uncategorized",
  "account_id": null
}
```

| Field      | Type   | Required | Validation                                     |
| ---------- | ------ | -------- | ---------------------------------------------- |
| scope      | string | No       | `uncategorized` (default) or `all`             |
| account_id | int    | No       | Limit to a specific account; null = all accounts|

**Response `200 OK`:**

```json
{
  "processed": 150,
  "categorized": 120,
  "uncategorized": 30,
  "duration_ms": 342
}
```

---

## 4. Business Logic

### 4.1 Categorization Engine Pipeline

The engine runs as a synchronous batch process. It is **idempotent** — running it multiple times with the same rules and data produces the same result.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CATEGORIZATION PIPELINE                       │
│                                                                 │
│  ┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌─────────┐ │
│  │ 1. Load  │──▶│ 2. Normalize │──▶│ 3. Match │──▶│ 4. Save │ │
│  │   Data   │   │   Text       │   │   Rules  │   │ Results │ │
│  └──────────┘   └──────────────┘   └──────────┘   └─────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Step 1 — Load Data:**
- Query transactions based on `scope` (`uncategorized` or `all`).
- Load all active rules ordered by `priority DESC, id ASC`.
- Load in batches of 1000 rows to control memory.

**Step 2 — Normalize Text:**
- For each transaction, normalize the `description` field:
  - Convert to lowercase.
  - Strip leading/trailing whitespace.
  - Collapse multiple spaces into one.
  - Remove diacritical marks (accent folding: `ã` → `a`, `ç` → `c`, etc.).
- The normalized text is used for matching only (original description preserved in DB).

**Step 3 — Match Rules:**
- For each normalized transaction description, iterate rules in priority order.
- Apply the matching algorithm (see §4.2).
- **First match wins** — stop on the first rule that matches.
- If no rule matches, assign `category_id = NULL` (uncategorized) and `categorization_source = 'auto'`.

**Step 4 — Save Results:**
- Batch `UPDATE` transactions with matched `category_id`, `categorized_at = NOW()`, and `categorization_source = 'auto'`.
- Use a single transaction (DB transaction) per batch for atomicity.
- Skip transactions where `categorization_source = 'manual'` when `scope = 'all'` — user overrides are never overwritten by auto-categorization.

### 4.2 Keyword Matching Algorithm

All matching is performed on the **normalized** description text against the **normalized** rule keyword (keywords are stored pre-normalized).

| match_type    | Algorithm                                              | Example keyword | Matches description          |
| ------------- | ------------------------------------------------------ | --------------- | -----------------------------|
| `exact`       | `normalized_description == keyword`                    | `uber`          | `"uber"` only                |
| `contains`    | `keyword IN normalized_description`                    | `uber`          | `"uber trip"`, `"paid uber"` |
| `starts_with` | `normalized_description.startswith(keyword)`           | `uber`          | `"uber trip"`, not `"paid uber"` |
| `ends_with`   | `normalized_description.endswith(keyword)`             | `market`        | `"super market"`, not `"market place"` |

**Implementation note:** Use Python `in` operator and `str.startswith()` / `str.endswith()` for clarity and performance. Do NOT use regex for keyword matching — it adds unnecessary complexity and attack surface. If regex-based matching is needed later, introduce a separate `regex` match_type behind a feature flag.

### 4.3 Rule Priority & Ordering

Rules are evaluated in strict order:

1. **`priority` DESC** — higher numeric priority evaluates first.
2. **`id` ASC** (tie-breaker) — older rules win among equal priority.

Priority guidelines:

| Priority Range | Intended Use                          |
| -------------- | ------------------------------------- |
| 100+           | User-created high-confidence rules    |
| 50–99          | User-created standard rules           |
| 10–49          | Auto-learned rules from overrides     |
| 0–9            | System/seed rules (lowest confidence) |

When a user creates a rule via the UI (`source = 'manual'`), default priority is `50`.
When a rule is learned from an override (`source = 'learned'`), default priority is `10`.

### 4.4 Learning from User Overrides

When a user overrides a transaction's category via `POST /api/v1/transactions/{id}/categorize` with `learn_rule = true`:

1. **Extract keyword** from the transaction's `description`:
   - Normalize the description (lowercase, trim, accent-fold).
   - Use the full normalized description as the keyword.
2. **Check for existing rule:**
   - Query `categorization_rules` for a rule with the same `keyword` and `match_type = 'contains'`.
   - If a rule exists with the **same category** → no action needed.
   - If a rule exists with a **different category** → update `category_id` and `updated_at`.
   - If no rule exists → insert a new rule with `source = 'learned'`, `priority = 10`, `match_type = 'contains'`.
3. **Update the transaction:**
   - Set `category_id`, `categorized_at = NOW()`, `categorization_source = 'manual'`.
4. **Do NOT re-run** the full categorization engine. The learned rule is applied to future imports only.

### 4.5 Idempotency Guarantees

| Operation             | Idempotency Mechanism                                 |
| --------------------- | ----------------------------------------------------- |
| Auto-categorization   | Same rules + same data = same assignments             |
| User override         | PUT-style semantics; final state is the same          |
| Rule creation         | UNIQUE constraint on `(keyword, match_type)` prevents duplicates |
| Batch re-run          | Manual overrides are preserved (`categorization_source = 'manual'` is skipped) |

---

## 5. Error Handling

### 5.1 Error Response Format

All errors follow a consistent JSON envelope:

```json
{
  "error": {
    "code": "CATEGORY_NOT_FOUND",
    "message": "Category with id 99 does not exist.",
    "details": null
  }
}
```

### 5.2 Error Code Catalog

| HTTP Status | Code                         | Message Template                                             |
| ----------- | ---------------------------- | ------------------------------------------------------------ |
| 400         | `INVALID_KEYWORD`            | `"Keyword must be between 1 and 255 characters."`            |
| 400         | `INVALID_MATCH_TYPE`         | `"match_type must be one of: exact, contains, starts_with, ends_with."` |
| 400         | `INVALID_CATEGORY_NAME`      | `"Category name must be between 1 and 100 characters."`      |
| 400         | `INVALID_COLOR_FORMAT`       | `"Color must be a valid hex code (e.g., #FF5733)."`          |
| 400         | `EMPTY_TRANSACTION_LIST`     | `"transaction_ids must contain at least one ID."`            |
| 400         | `TOO_MANY_TRANSACTIONS`      | `"Maximum 500 transactions per bulk operation."`             |
| 403         | `SYSTEM_CATEGORY_PROTECTED`  | `"System categories cannot be modified or deleted."`         |
| 404         | `CATEGORY_NOT_FOUND`         | `"Category with id {id} does not exist."`                    |
| 404         | `RULE_NOT_FOUND`             | `"Rule with id {id} does not exist."`                        |
| 404         | `TRANSACTION_NOT_FOUND`      | `"Transaction with id {id} does not exist."`                 |
| 409         | `CATEGORY_ALREADY_EXISTS`    | `"A category named '{name}' already exists."`                |
| 409         | `RULE_ALREADY_EXISTS`        | `"A rule with keyword '{keyword}' and match_type '{type}' already exists."` |
| 500         | `CATEGORIZATION_ENGINE_ERROR`| `"An error occurred during batch categorization."`           |

### 5.3 Logging Strategy

| Level    | What to Log                                                         |
| -------- | ------------------------------------------------------------------- |
| `INFO`   | Batch categorization started/completed with summary counts          |
| `INFO`   | Rule created/updated/deleted (include rule id and keyword)          |
| `INFO`   | User override applied (transaction_id, old_category, new_category)  |
| `WARNING`| Learned rule creation skipped due to existing conflicting rule      |
| `WARNING`| Transaction not found during bulk categorize (partial success)      |
| `ERROR`  | Database connection failure during batch processing                 |
| `ERROR`  | Unhandled exception in categorization engine (full traceback)       |

Logs use structured JSON format with fields: `timestamp`, `level`, `event`, `context` (dict with relevant IDs/counts).

---

## 6. Frontend Components

All component names use **camelCase** per project convention.

### 6.1 Component Tree

```
categorization/
├── categoryManager.vue           — Main page for category CRUD
├── categoryList.vue              — Table/grid of categories
├── categoryFormDialog.vue        — Create/edit category modal
├── ruleManager.vue               — Main page for rule CRUD
├── ruleList.vue                  — Table of rules with filters
├── ruleFormDialog.vue            — Create/edit rule modal
├── transactionCategorySelect.vue — Inline category picker for transaction rows
├── bulkCategorizeBar.vue         — Floating action bar for bulk operations
└── categorizationRunButton.vue   — Trigger batch auto-categorization
```

### 6.2 Component Specifications

#### `categoryManager.vue`

- **Responsibility:** Top-level page for managing categories.
- **Behavior:**
  - Renders `categoryList` and a "New Category" button.
  - Opens `categoryFormDialog` for create/edit.
  - Confirms before deleting; shows count of affected transactions.
  - Prevents delete/rename of system categories (button disabled, tooltip explains).

#### `categoryList.vue`

- **Responsibility:** Displays categories in a sortable table.
- **Props:** `categories: Category[]`
- **Emits:** `edit(id)`, `delete(id)`
- **Behavior:**
  - Columns: Color swatch, Name, Rule count, Transaction count, Actions.
  - Sort by name or transaction count.
  - Shows a colored badge for each category.

#### `categoryFormDialog.vue`

- **Responsibility:** Modal form for creating/editing a category.
- **Props:** `category?: Category` (null for create mode)
- **Emits:** `saved(category)`, `cancelled()`
- **Behavior:**
  - Fields: Name (text input), Color (color picker), Icon (optional dropdown).
  - Client-side validation: name required, 1–100 chars; color hex format.
  - Shows server-side error if name conflicts (409).
  - Disables name field for system categories.

#### `ruleManager.vue`

- **Responsibility:** Top-level page for managing categorization rules.
- **Behavior:**
  - Renders filter bar (by category, source, active status, keyword search).
  - Renders `ruleList` with paginated data.
  - Opens `ruleFormDialog` for create/edit.
  - Shows badge for rule source (`manual`, `learned`, `system`).

#### `ruleList.vue`

- **Responsibility:** Paginated table of rules.
- **Props:** `rules: Rule[]`, `totalCount: number`, `currentPage: number`
- **Emits:** `edit(id)`, `delete(id)`, `toggleActive(id, boolean)`, `pageChange(page)`
- **Behavior:**
  - Columns: Keyword, Match Type, Category (colored badge), Priority, Source, Active toggle, Actions.
  - Sortable by priority, keyword, created date.
  - Inline toggle for `is_active` (calls `PUT /api/v1/rules/{id}` with `{ "is_active": value }`).
  - Confirmation dialog for delete.

#### `ruleFormDialog.vue`

- **Responsibility:** Modal form for creating/editing a rule.
- **Props:** `rule?: Rule` (null for create mode)
- **Emits:** `saved(rule)`, `cancelled()`
- **Behavior:**
  - Fields: Keyword (text), Category (dropdown from `GET /categories`), Match Type (dropdown), Priority (number input).
  - Client-side validation: keyword required; priority ≥ 0.
  - Keyword is visually shown as normalized (lowercase preview under input).
  - Shows duplicate error (409) inline.

#### `transactionCategorySelect.vue`

- **Responsibility:** Inline dropdown for changing a transaction's category in the transaction list.
- **Props:** `transactionId: number`, `currentCategoryId: number | null`
- **Emits:** `categoryChanged(transactionId, newCategoryId)`
- **Behavior:**
  - Dropdown populated from cached category list.
  - On selection change, calls `POST /api/v1/transactions/{id}/categorize`.
  - Shows checkbox: "Learn this rule for future transactions" (maps to `learn_rule`), default checked.
  - Shows brief toast on success: "Category updated. Rule learned." or "Category updated."
  - Optimistic UI update, reverts on error.

#### `bulkCategorizeBar.vue`

- **Responsibility:** Fixed bottom bar that appears when transactions are selected.
- **Props:** `selectedIds: number[]`
- **Emits:** `bulkApplied()`
- **Behavior:**
  - Shows count of selected transactions.
  - Category dropdown + "Apply" button.
  - Calls `POST /api/v1/transactions/categorize-bulk`.
  - Disabled when `selectedIds` is empty.
  - Shows progress/result toast.

#### `categorizationRunButton.vue`

- **Responsibility:** Button to trigger auto-categorization batch run.
- **Props:** none
- **Emits:** `completed(summary)`
- **Behavior:**
  - Dropdown to select scope: "Uncategorized only" or "All transactions".
  - Calls `POST /api/v1/categorize/run`.
  - Shows spinner while processing.
  - Displays result: "Categorized 120 of 150 transactions in 342ms."
  - Refreshes transaction list on completion.

---

## 7. Non-Functional Requirements

### 7.1 Performance Targets

| Metric                                  | Target              |
| --------------------------------------- | ------------------- |
| Single category override response time  | < 200ms (p95)       |
| Bulk categorize (500 transactions)      | < 2s (p95)          |
| Batch auto-categorize (10k transactions)| < 10s               |
| Rule list load (500 rules)              | < 300ms (p95)       |
| Category list load                      | < 100ms (p95)       |

### 7.2 Scalability Considerations

- **Rule count:** Design assumes ≤ 5,000 active rules. At this scale, in-memory matching (load all rules once per batch run) is acceptable. If rule count exceeds 10,000, consider database-side matching via `ILIKE` or full-text search.
- **Transaction volume:** Batch processing uses chunked queries (1,000 rows per chunk) to avoid loading all transactions into memory. Updates are batched per chunk.
- **Rule caching:** The active rule set should be cached in-memory (Python dict) during a batch run. The cache is rebuilt at the start of each run — no stale-cache invalidation needed.
- **Database indexes:** Ensure indexes on `transactions.category_id`, `transactions.categorization_source`, `categorization_rules.is_active`, and `categorization_rules.priority` are in place (defined in §2).
- **Concurrent access:** The `categorize/run` endpoint should use an advisory lock (`pg_advisory_lock`) to prevent concurrent batch runs. If a run is already in progress, return `409 CONFLICT` with code `CATEGORIZATION_IN_PROGRESS`.

### 7.3 Data Integrity

- Deleting a category cascades to delete its rules and nullifies `category_id` on transactions.
- Learned rules include `source = 'learned'` so they can be audited or bulk-deleted without affecting manually created rules.
- The `UNIQUE (keyword, match_type)` constraint ensures no duplicate rules. The API surfaces this as a `409` error.

### 7.4 Testing Strategy

| Layer          | Coverage Target | Key Scenarios                                                 |
| -------------- | --------------- | ------------------------------------------------------------- |
| Unit tests     | 90%+            | Normalization, matching algorithm, priority ordering          |
| Integration    | 80%+            | CRUD endpoints, override + learn flow, batch categorization   |
| E2E (frontend) | Critical paths  | Create rule → import → verify auto-categorization; override → verify persistence |

### 7.5 Future Considerations (Out of Scope)

- **AI-based suggestions:** AGENTS.md lists "Categorization suggestions" under AI Usage. A future spec may add a `/api/v1/categorize/suggest` endpoint that uses embeddings or frequency analysis.
- **Regex match_type:** Can be added as a new `match_type` value without schema changes.
- **Multi-language keywords:** Accent folding (§4.1) handles Portuguese characters. Additional language support may require ICU normalization.

---

## Appendix A: Backend Module Structure

```
backend/
└── app/
    ├── api/
    │   └── v1/
    │       ├── categories.py      # Category CRUD endpoints
    │       ├── rules.py           # Rule CRUD endpoints
    │       └── categorization.py  # Categorize actions (override, bulk, run)
    ├── models/
    │   ├── category.py            # SQLAlchemy model for categories
    │   └── categorization_rule.py # SQLAlchemy model for rules
    ├── schemas/
    │   ├── category.py            # Pydantic request/response schemas
    │   └── rule.py                # Pydantic request/response schemas
    ├── services/
    │   ├── categorization_engine.py  # Batch engine (§4.1 pipeline)
    │   ├── rule_matcher.py           # Keyword matching logic (§4.2)
    │   └── text_normalizer.py        # Normalization utilities (§4.1 step 2)
    └── tests/
        ├── test_categorization_engine.py
        ├── test_rule_matcher.py
        ├── test_text_normalizer.py
        └── test_api_categories.py
```

## Appendix B: Normalization Reference

The `text_normalizer.normalize(text: str) -> str` function performs:

1. `text.strip()` — remove leading/trailing whitespace.
2. `text.lower()` — convert to lowercase.
3. `unicodedata.normalize('NFD', text)` → remove combining marks → `unicodedata.normalize('NFC', result)` — accent folding.
4. `re.sub(r'\s+', ' ', text)` — collapse whitespace.

Example transformations:

| Input                       | Normalized Output           |
| --------------------------- | --------------------------- |
| `"  Pão de Açúcar  "`      | `"pao de acucar"`           |
| `"UBER   TRIP"`             | `"uber trip"`               |
| `"café-express"`            | `"cafe-express"`            |