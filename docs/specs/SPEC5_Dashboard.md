# SPEC 5 — Dashboard

**Status:** Draft
**PRD:** PRD5_Dashboard
**Created:** 2026-04-17

---

## 1. Overview

The Dashboard is the primary landing page of the finance system. It provides users with an at-a-glance view of their financial health for a selected month/year, including:

- **Monthly summary** — total expenses broken down by category (US1)
- **Charts** — a pie chart of category distribution and a time-series line chart of daily/monthly spending trends (US2)
- **Card tracking** — current credit card invoice totals and upcoming payment due dates (US3)

All data originates from the `transactions` table (source of truth: database). The dashboard consumes read-only aggregated views; it never mutates transaction data. Aggregation is performed server-side via SQL with an optional caching layer for performance.

---

## 2. API Endpoints

Base path: `/api/v1/dashboard`

### 2.1 GET `/api/v1/dashboard/monthly-summary`

Returns total expenses for a given month, grouped by category.

**Query Parameters**

| Name    | Type | Required | Default       | Description                  |
|---------|------|----------|---------------|------------------------------|
| `month` | int  | No       | current month | Month number (1–12)          |
| `year`  | int  | No       | current year  | Four-digit year (e.g., 2026) |

**Response — 200 OK**

```/dev/null/monthly_summary_response.json#L1-22
{
  "month": 4,
  "year": 2026,
  "total_expenses": 4523.87,
  "total_income": 8200.00,
  "net": 3676.13,
  "categories": [
    {
      "category_id": 1,
      "category_name": "Alimentação",
      "total": 1250.30,
      "percentage": 27.64,
      "transaction_count": 42
    },
    {
      "category_id": 2,
      "category_name": "Transporte",
      "total": 680.00,
      "percentage": 15.03,
      "transaction_count": 15
    }
  ]
}
```

**Error Responses**

| Status | Code                    | Condition                                       |
|--------|-------------------------|-------------------------------------------------|
| 400    | `INVALID_MONTH`         | `month` not in range 1–12                       |
| 400    | `INVALID_YEAR`          | `year` < 2000 or `year` > current year + 1      |
| 500    | `AGGREGATION_FAILED`    | Unexpected database error during query           |

---

### 2.2 GET `/api/v1/dashboard/charts/category-breakdown`

Returns data formatted for the pie chart (same period granularity as the summary).

**Query Parameters**

| Name    | Type | Required | Default       |
|---------|------|----------|---------------|
| `month` | int  | No       | current month |
| `year`  | int  | No       | current year  |

**Response — 200 OK**

```/dev/null/category_breakdown_response.json#L1-17
{
  "month": 4,
  "year": 2026,
  "slices": [
    {
      "category_id": 1,
      "category_name": "Alimentação",
      "total": 1250.30,
      "percentage": 27.64,
      "color": "#FF6384"
    }
  ],
  "uncategorized_total": 120.00,
  "uncategorized_percentage": 2.65
}
```

---

### 2.3 GET `/api/v1/dashboard/charts/time-series`

Returns daily or monthly aggregated spending for the time-series chart.

**Query Parameters**

| Name          | Type   | Required | Default       | Description                             |
|---------------|--------|----------|---------------|-----------------------------------------|
| `month`       | int    | No       | current month | Month number (1–12)                     |
| `year`        | int    | No       | current year  | Four-digit year                         |
| `granularity` | string | No       | `"daily"`     | `"daily"` (single month) or `"monthly"` (full year) |
| `months_back` | int    | No       | 6             | For `"monthly"` granularity: how many months to look back (max 24) |

**Response — 200 OK**

```/dev/null/time_series_response.json#L1-23
{
  "granularity": "daily",
  "period": {
    "start": "2026-04-01",
    "end": "2026-04-30"
  },
  "data_points": [
    {
      "date": "2026-04-01",
      "total_expenses": 230.50,
      "total_income": 0.00
    },
    {
      "date": "2026-04-02",
      "total_expenses": 85.00,
      "total_income": 8200.00
    }
  ],
  "cumulative_expenses": 4523.87,
  "cumulative_income": 8200.00
}
```

---

### 2.4 GET `/api/v1/dashboard/card-tracking`

Returns credit card invoice totals and upcoming payment info.

**Query Parameters**

| Name    | Type | Required | Default       |
|---------|------|----------|---------------|
| `month` | int  | No       | current month |
| `year`  | int  | No       | current year  |

**Response — 200 OK**

```/dev/null/card_tracking_response.json#L1-31
{
  "month": 4,
  "year": 2026,
  "cards": [
    {
      "account_id": 10,
      "account_name": "Nubank",
      "current_invoice_total": 2340.50,
      "transaction_count": 28,
      "closing_date": "2026-04-15",
      "due_date": "2026-04-25",
      "status": "open",
      "days_until_due": 8
    },
    {
      "account_id": 11,
      "account_name": "Itaú Visa",
      "current_invoice_total": 1580.00,
      "transaction_count": 12,
      "closing_date": "2026-04-10",
      "due_date": "2026-04-20",
      "status": "closed",
      "days_until_due": 3
    }
  ],
  "upcoming_payments": [
    {
      "account_id": 11,
      "account_name": "Itaú Visa",
      "due_date": "2026-04-20",
      "amount": 1580.00,
      "days_until_due": 3,
      "is_urgent": true
    }
  ],
  "total_card_debt": 3920.50
}
```

**Invoice Status Values**

| Status     | Meaning                                              |
|------------|------------------------------------------------------|
| `open`     | Closing date is in the future; charges still accruing |
| `closed`   | Closing date passed; amount is final, payment pending |
| `paid`     | Payment recorded for this billing cycle               |
| `overdue`  | Due date passed without recorded payment              |

---

## 3. Data Models

### 3.1 Assumed Existing Tables

The following tables are assumed to exist based on the Key Entities in AGENTS.md and sibling PRDs:

```/dev/null/existing_tables.sql#L1-32
-- transactions (source of truth, immutable except category edits)
CREATE TABLE transactions (
    id              BIGSERIAL PRIMARY KEY,
    account_id      INTEGER NOT NULL REFERENCES accounts(id),
    category_id     INTEGER REFERENCES categories(id),
    description     VARCHAR(500) NOT NULL,
    amount          NUMERIC(14,2) NOT NULL,
    transaction_date DATE NOT NULL,
    type            VARCHAR(20) NOT NULL CHECK (type IN ('expense', 'income', 'transfer')),
    import_id       INTEGER REFERENCES imports(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- accounts
CREATE TABLE accounts (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    type            VARCHAR(50) NOT NULL CHECK (type IN ('checking', 'savings', 'credit_card')),
    closing_day     INTEGER,          -- credit cards: day of month invoice closes
    due_day         INTEGER,          -- credit cards: day of month payment is due
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- categories
CREATE TABLE categories (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL UNIQUE,
    color           VARCHAR(7),       -- hex color code for charts
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3.2 Materialized View — Monthly Category Aggregation

This materialized view pre-computes the most expensive query (monthly grouping by category). It is refreshed on a schedule or after each import batch completes.

```/dev/null/mv_monthly_category_summary.sql#L1-22
CREATE MATERIALIZED VIEW mv_monthly_category_summary AS
SELECT
    DATE_TRUNC('month', t.transaction_date)::DATE AS month_start,
    EXTRACT(MONTH FROM t.transaction_date)::INT   AS month,
    EXTRACT(YEAR FROM t.transaction_date)::INT    AS year,
    t.category_id,
    c.name                                         AS category_name,
    c.color                                        AS category_color,
    t.type,
    COUNT(*)                                       AS transaction_count,
    SUM(t.amount)                                  AS total
FROM transactions t
LEFT JOIN categories c ON c.id = t.category_id
GROUP BY
    DATE_TRUNC('month', t.transaction_date),
    EXTRACT(MONTH FROM t.transaction_date),
    EXTRACT(YEAR FROM t.transaction_date),
    t.category_id,
    c.name,
    c.color,
    t.type;

CREATE UNIQUE INDEX idx_mv_mcs_month_cat_type
    ON mv_monthly_category_summary (month_start, category_id, type);
```

**Refresh strategy:**

```/dev/null/refresh.sql#L1-1
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_monthly_category_summary;
```

Triggered by:
1. A cron job every 15 minutes during business hours.
2. Explicitly after an import batch completes (via `POST /api/v1/imports` handler).

### 3.3 Materialized View — Daily Spending Aggregation

```/dev/null/mv_daily_spending.sql#L1-14
CREATE MATERIALIZED VIEW mv_daily_spending AS
SELECT
    t.transaction_date                             AS date,
    t.type,
    COUNT(*)                                       AS transaction_count,
    SUM(t.amount)                                  AS total
FROM transactions t
GROUP BY t.transaction_date, t.type;

CREATE UNIQUE INDEX idx_mv_ds_date_type
    ON mv_daily_spending (date, type);
```

### 3.4 Index Recommendations

```/dev/null/indexes.sql#L1-8
-- Support card tracking queries
CREATE INDEX idx_transactions_account_date
    ON transactions (account_id, transaction_date);

-- Support category filtering on dashboard
CREATE INDEX idx_transactions_category_date
    ON transactions (category_id, transaction_date);
```

---

## 4. Business Logic

### 4.1 Monthly Summary Aggregation

**Backend module:** `app/services/dashboard_service.py`

**Algorithm:**

1. Receive `month` and `year` parameters; default to current month/year if absent.
2. Validate inputs: `1 <= month <= 12`, `2000 <= year <= current_year + 1`.
3. Query `mv_monthly_category_summary` filtered by `month` and `year`.
4. Separate rows by `type` (`expense` vs `income`).
5. Compute `total_expenses` = sum of all expense rows.
6. Compute `total_income` = sum of all income rows.
7. Compute `percentage` for each category: `(category_total / total_expenses) * 100`, rounded to 2 decimal places.
8. Sort categories by `total` descending.
9. If no data exists for the period, return the response structure with `total_expenses: 0`, `categories: []` (empty state — not an error).

```/dev/null/dashboard_service.py#L1-37
from datetime import date
from fastapi import HTTPException

async def get_monthly_summary(db, month: int, year: int):
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_MONTH",
            "message": "month must be between 1 and 12"
        })

    current_year = date.today().year
    if not (2000 <= year <= current_year + 1):
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_YEAR",
            "message": f"year must be between 2000 and {current_year + 1}"
        })

    rows = await db.fetch_all(
        """
        SELECT category_id, category_name, category_color, type,
               transaction_count, total
        FROM mv_monthly_category_summary
        WHERE month = :month AND year = :year
        """,
        {"month": month, "year": year}
    )

    expenses = [r for r in rows if r["type"] == "expense"]
    income = [r for r in rows if r["type"] == "income"]

    total_expenses = sum(r["total"] for r in expenses)
    total_income = sum(r["total"] for r in income)

    categories = []
    for r in sorted(expenses, key=lambda x: x["total"], reverse=True):
        pct = round((r["total"] / total_expenses) * 100, 2) if total_expenses > 0 else 0
        categories.append({
            "category_id": r["category_id"],
            "category_name": r["category_name"] or "Sem Categoria",
            "total": float(r["total"]),
            "percentage": pct,
            "transaction_count": r["transaction_count"],
        })

    return {
        "month": month,
        "year": year,
        "total_expenses": float(total_expenses),
        "total_income": float(total_income),
        "net": float(total_income - total_expenses),
        "categories": categories,
    }
```

### 4.2 Category Breakdown (Pie Chart)

Uses the same aggregation query as §4.1 but adds `color` and isolates uncategorized transactions (where `category_id IS NULL`).

**Logic:**

1. Query `mv_monthly_category_summary` for the requested period, `type = 'expense'`.
2. Split into categorized (`category_id IS NOT NULL`) and uncategorized.
3. Build `slices` array with `color` from the categories table.
4. Return `uncategorized_total` and `uncategorized_percentage` as separate top-level fields.

### 4.3 Time Series

**Daily granularity:**

1. Query `mv_daily_spending` where `date BETWEEN first_day_of_month AND last_day_of_month`.
2. Fill gaps: iterate every calendar day in the range; if no row exists for a day, emit `{ date, total_expenses: 0, total_income: 0 }`.
3. Return ordered array of data points.

**Monthly granularity:**

1. Query `mv_monthly_category_summary` for the last `months_back` months, grouped by `month_start` and `type`.
2. Fill gaps for months with zero activity.
3. Return ordered array of data points with `date` set to the first day of each month.

### 4.4 Card Invoice Calculation

**Algorithm:**

1. Fetch all accounts where `type = 'credit_card'` and `is_active = TRUE`.
2. For each card, compute the billing cycle window:
   - `closing_date` = day `accounts.closing_day` of the requested `month/year`.
   - `cycle_start` = day after the previous month's closing date.
   - `cycle_end` = `closing_date` of current month.
3. Query `transactions` where `account_id = card.id` and `transaction_date BETWEEN cycle_start AND cycle_end`.
4. Sum amounts → `current_invoice_total`.
5. Compute `due_date` = day `accounts.due_day` of the billing month (if `due_day < closing_day`, the due date falls in the next month).
6. Determine `status`:

```/dev/null/card_status_logic.py#L1-12
from datetime import date

def compute_invoice_status(closing_date, due_date, has_payment, today=None):
    today = today or date.today()
    if has_payment:
        return "paid"
    if today <= closing_date:
        return "open"
    if today <= due_date:
        return "closed"
    return "overdue"
```

### 4.5 Upcoming Payment Detection

**Algorithm:**

1. From the card tracking results (§4.4), filter cards where `status IN ('closed', 'open')`.
2. Compute `days_until_due = (due_date - today).days`.
3. Mark `is_urgent = True` if `days_until_due <= 5`.
4. Sort by `due_date` ascending (soonest first).
5. Return as the `upcoming_payments` array.

---

## 5. Error Handling

### 5.1 Error Response Schema

All error responses follow a consistent envelope:

```/dev/null/error_schema.json#L1-7
{
  "detail": {
    "code": "INVALID_MONTH",
    "message": "month must be between 1 and 12",
    "field": "month"
  }
}
```

### 5.2 Error Code Reference

| HTTP Status | Code                    | Message                                          | Trigger                              |
|-------------|-------------------------|--------------------------------------------------|--------------------------------------|
| 400         | `INVALID_MONTH`         | month must be between 1 and 12                   | `month` param out of range           |
| 400         | `INVALID_YEAR`          | year must be between 2000 and {max}               | `year` param out of range            |
| 400         | `INVALID_GRANULARITY`   | granularity must be "daily" or "monthly"          | Bad `granularity` param              |
| 400         | `INVALID_MONTHS_BACK`   | months_back must be between 1 and 24              | `months_back` out of range           |
| 404         | `ACCOUNT_NOT_FOUND`     | No active credit card accounts found              | Card tracking with no card accounts  |
| 500         | `AGGREGATION_FAILED`    | Failed to compute dashboard aggregation           | Database timeout or query error      |
| 503         | `VIEW_REFRESH_IN_PROGRESS` | Data is being updated, try again in a few seconds | Concurrent materialized view refresh |

### 5.3 Empty State Handling

Empty states are **not errors**. The API always returns 200 with zero-valued totals and empty arrays:

| Scenario                            | Behavior                                                       |
|-------------------------------------|----------------------------------------------------------------|
| No transactions in selected month   | `total_expenses: 0`, `categories: []`, chart data points all 0 |
| No credit card accounts             | `cards: []`, `upcoming_payments: []`, `total_card_debt: 0`     |
| Category with no color defined      | Default color `"#9E9E9E"` assigned in the pie chart response   |
| Uncategorized transactions          | Grouped under `"Sem Categoria"` with `category_id: null`      |

---

## 6. Frontend Components

### 6.1 Chart Library

**Recommendation: ApexCharts** (via `vue3-apexcharts`)

Rationale:
- Built-in Vue 3 wrapper (`vue3-apexcharts`).
- Responsive and animated out of the box.
- Supports pie, donut, line, area, and bar charts with minimal configuration.
- Lightweight compared to D3-based alternatives.
- Good TypeScript support.

**Installation:**

```/dev/null/install.sh#L1-1
npm install apexcharts vue3-apexcharts
```

### 6.2 Component Tree

```/dev/null/component_tree.txt#L1-15
src/views/
  dashboardView.vue              ← Page-level route component

src/components/dashboard/
  monthYearSelector.vue          ← Month/year picker (shared across all panels)
  monthlySummaryCard.vue         ← Total expenses / income / net display
  categoryBreakdownTable.vue     ← Tabular list of categories with amounts
  categoryPieChart.vue           ← Pie/donut chart of category distribution
  spendingTimeSeriesChart.vue    ← Line/area chart of daily or monthly spending
  cardTrackingPanel.vue          ← List of credit cards with invoice details
  upcomingPaymentsList.vue       ← Sorted list of upcoming due dates
  dashboardEmptyState.vue        ← Shown when no data exists for the period
  dashboardSkeleton.vue          ← Loading skeleton placeholder
```

### 6.3 Component Responsibilities

#### `dashboardView.vue`

- Route: `/dashboard` (default landing page).
- Manages the selected `month` and `year` state (reactive refs).
- Fetches all four API endpoints in parallel on mount and when month/year changes.
- Passes data down as props to child components.
- Shows `dashboardSkeleton` during loading, `dashboardEmptyState` when all panels are empty.

#### `monthYearSelector.vue`

- Props: `modelValue: { month: number, year: number }`.
- Emits: `update:modelValue`.
- UI: Two dropdowns (month name list + year list) or left/right arrow navigation.
- Constrains year range to `2000 – currentYear + 1`.

#### `monthlySummaryCard.vue`

- Props: `totalExpenses: number`, `totalIncome: number`, `net: number`.
- Renders three metric cards side-by-side.
- Color-codes net value: green if positive, red if negative.

#### `categoryBreakdownTable.vue`

- Props: `categories: CategorySummary[]`.
- Sortable table with columns: Category Name, Total (R$), % of Total, # Transactions.
- Each row shows a colored dot matching the category color.
- Clicking a row could navigate to filtered transaction list (future enhancement).

#### `categoryPieChart.vue`

- Props: `slices: PieSlice[]`, `uncategorizedTotal: number`.
- Renders an ApexCharts donut chart.
- Tooltip shows category name, amount (R$), and percentage.
- Legend displayed below the chart on mobile, to the right on desktop.

#### `spendingTimeSeriesChart.vue`

- Props: `dataPoints: TimeSeriesPoint[]`, `granularity: 'daily' | 'monthly'`.
- Renders an ApexCharts area chart with two series (expenses, income).
- X-axis: dates. Y-axis: amounts in R$.
- Toggle between daily/monthly granularity via a segmented control.

#### `cardTrackingPanel.vue`

- Props: `cards: CardInvoice[]`.
- Renders a card (UI card) per credit card account.
- Shows: account name, invoice total, closing date, due date, status badge.
- Status badge colors: `open` → blue, `closed` → orange, `paid` → green, `overdue` → red.

#### `upcomingPaymentsList.vue`

- Props: `payments: UpcomingPayment[]`.
- Sorted list with urgency indicator.
- `is_urgent` items get a red highlight and a warning icon.
- Shows `days_until_due` as a human-readable label (e.g., "em 3 dias").

#### `dashboardEmptyState.vue`

- Displayed when the selected period has no transactions.
- Shows an illustration and a message: "Nenhuma movimentação encontrada para este período."
- CTA button to navigate to the import page.

#### `dashboardSkeleton.vue`

- Pulsing placeholder rectangles matching the layout of the real dashboard.
- Shown during initial load and period changes.

### 6.4 UI Layout

```/dev/null/layout.txt#L1-20
┌─────────────────────────────────────────────────────────┐
│  [← Abril 2026 →]   monthYearSelector                  │
├──────────┬──────────┬───────────────────────────────────┤
│ Despesas │ Receitas │ Saldo Líquido                     │
│  R$ 4.5k │  R$ 8.2k │  R$ 3.7k     monthlySummaryCard  │
├──────────┴──────────┼───────────────────────────────────┤
│                     │                                   │
│  categoryPieChart   │  categoryBreakdownTable           │
│  (donut)            │  (sortable table)                 │
│                     │                                   │
├─────────────────────┴───────────────────────────────────┤
│                                                         │
│  spendingTimeSeriesChart  [Diário | Mensal]             │
│  (area chart, full width)                               │
│                                                         │
├──────────────────────────┬──────────────────────────────┤
│  cardTrackingPanel       │  upcomingPaymentsList        │
│  (card list)             │  (urgent payments)           │
└──────────────────────────┴──────────────────────────────┘
```

Responsive breakpoints:
- **Desktop (≥1024px):** Two-column layout as shown above.
- **Tablet (768–1023px):** Pie chart and table stack vertically; cards remain side-by-side.
- **Mobile (<768px):** Single column, all panels stack vertically.

### 6.5 Frontend API Client

```/dev/null/dashboardApi.ts#L1-34
// src/api/dashboardApi.ts

import { apiClient } from './client'

interface PeriodParams {
  month?: number
  year?: number
}

export const dashboardApi = {
  getMonthlySummary(params: PeriodParams) {
    return apiClient.get('/dashboard/monthly-summary', { params })
  },

  getCategoryBreakdown(params: PeriodParams) {
    return apiClient.get('/dashboard/charts/category-breakdown', { params })
  },

  getTimeSeries(params: PeriodParams & {
    granularity?: 'daily' | 'monthly'
    monthsBack?: number
  }) {
    return apiClient.get('/dashboard/charts/time-series', {
      params: {
        month: params.month,
        year: params.year,
        granularity: params.granularity,
        months_back: params.monthsBack,
      },
    })
  },

  getCardTracking(params: PeriodParams) {
    return apiClient.get('/dashboard/card-tracking', { params })
  },
}
```

---

## 7. Non-Functional Requirements

### 7.1 Query Performance Targets

| Endpoint                  | Target (p95) | Strategy                                          |
|---------------------------|-------------|---------------------------------------------------|
| `monthly-summary`         | < 100ms     | Reads from materialized view                      |
| `charts/category-breakdown` | < 100ms   | Reads from materialized view                      |
| `charts/time-series`      | < 200ms     | Reads from materialized view; gap-fill in Python  |
| `card-tracking`           | < 300ms     | Direct query with index on `(account_id, date)`   |

### 7.2 Caching Strategy

**Layer 1 — Materialized Views (PostgreSQL)**

- `mv_monthly_category_summary` and `mv_daily_spending` serve as the primary cache.
- Refreshed concurrently (non-blocking reads) every 15 minutes via `pg_cron` or application-level scheduler.
- Force-refresh after each completed import batch by calling `REFRESH MATERIALIZED VIEW CONCURRENTLY`.

**Layer 2 — Application-Level Cache (Redis or in-memory)**

- Cache API responses keyed by `dashboard:{endpoint}:{year}:{month}`.
- TTL: **5 minutes** for the current month, **24 hours** for past months (historical data rarely changes).
- Invalidation: bust cache for affected months when a category edit occurs or a new import completes.

```/dev/null/cache_key_example.py#L1-16
# Cache key generation (backend)
def dashboard_cache_key(endpoint: str, month: int, year: int) -> str:
    return f"dashboard:{endpoint}:{year}:{month:02d}"

def cache_ttl_seconds(month: int, year: int) -> int:
    from datetime import date
    today = date.today()
    if month == today.month and year == today.year:
        return 300       # 5 minutes for current month
    return 86400         # 24 hours for historical months
```

**Layer 3 — HTTP Caching**

- Set `Cache-Control: private, max-age=60` for current-month responses.
- Set `Cache-Control: private, max-age=3600` for historical-month responses.
- Use `ETag` headers based on the materialized view's last refresh timestamp.

### 7.3 Data Freshness

| Data Type         | Max Staleness | Guarantee                                                  |
|-------------------|---------------|-------------------------------------------------------------|
| Current month     | 15 minutes    | Materialized view refresh cycle                             |
| Historical months | 24 hours      | Only changes on category edits (which trigger cache bust)   |
| Card tracking     | Real-time     | Queries live transaction data, not materialized views       |

### 7.4 Load & Scalability

- Dashboard queries should support **50 concurrent users** without degradation.
- Materialized view refresh must complete in under **10 seconds** for up to 1 million transactions.
- If refresh exceeds 10 seconds, consider partitioning `transactions` by month.

### 7.5 Accessibility

- All charts must include `aria-label` descriptions summarizing the data.
- Color choices must pass WCAG 2.1 AA contrast ratio (≥ 4.5:1 against background).
- Chart data must also be available in tabular format (the `categoryBreakdownTable` fulfills this for the pie chart).

### 7.6 Testing Requirements

**Backend:**

- Unit tests for all aggregation functions with known data fixtures.
- Unit tests for card invoice date calculation edge cases (months with different lengths, closing_day = 31 in a 30-day month, due_day in the following month).
- Integration tests hitting the real database with seeded data.

**Frontend:**

- Component tests for each dashboard component using Vitest + Vue Test Utils.
- Verify empty state renders when API returns zero-valued data.
- Verify skeleton shows during loading state.
- E2E test (Cypress or Playwright): load dashboard, change month, verify data updates.

---

## Appendix A — Router Configuration

```/dev/null/router_snippet.ts#L1-8
// src/router/index.ts (partial)
{
  path: '/dashboard',
  name: 'dashboard',
  component: () => import('@/views/dashboardView.vue'),
  meta: { title: 'Dashboard' },
}
```

## Appendix B — Backend Router Registration

```/dev/null/router_registration.py#L1-10
# app/api/routes/__init__.py (partial)
from fastapi import APIRouter
from app.api.routes import dashboard

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["dashboard"],
)
```
