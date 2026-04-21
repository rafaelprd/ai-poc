const apiBase = import.meta.env.VITE_API_BASE ?? "/api/v1";

export type JsonRecord = Record<string, unknown>;

export interface ApiErrorPayload {
  code?: string;
  message?: string;
  details?: unknown;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(
    status: number,
    code: string,
    message: string,
    details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export interface IngestionFileSummary {
  fileId: string;
  originalFilename: string;
  mimeType: string;
  sizeBytes: number;
  status: string;
  rowsExtracted?: number;
  rowsFailed?: number;
  errorMessage?: string | null;
  createdAt?: string | null;
  startedAt?: string | null;
  completedAt?: string | null;
}

export interface IngestionBatchSummary {
  batchId: string;
  status: string;
  createdAt?: string | null;
  files?: IngestionFileSummary[];
  totalTransactionsCreated?: number;
  duplicatesSkipped?: number;
}

export interface BatchErrorItem {
  fileId: string;
  originalFilename?: string | null;
  rowNumber?: number | null;
  rawData?: string | null;
  errorType: string;
  errorMessage: string;
}

export interface Category {
  id: number;
  name: string;
  color: string;
  icon: string | null;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface Rule {
  id: number;
  keyword: string;
  category_id: number;
  category_name: string | null;
  match_type: "exact" | "contains" | "starts_with" | "ends_with";
  priority: number;
  source: "manual" | "learned" | "system";
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TransactionItem {
  id: number;
  date: string;
  description: string;
  original_description: string;
  amount: number;
  category_id: number | null;
  category_name: string | null;
  account_id: string | number | null;
  account_name: string | null;
  import_id: string | number | null;
  created_at: string;
  updated_at: string;
}

export interface TransactionListResponse {
  items: TransactionItem[];
  pagination: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
  };
}

export interface BatchListResponse {
  batches: Array<{
    batch_id: string;
    status: string;
    file_count: number;
    total_transactions_created: number;
    created_at: string | null;
  }>;
  total: number;
  page: number;
  page_size: number;
}

export interface BatchErrorsResponse {
  batch_id: string;
  errors: BatchErrorItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface CategorizeLearnedRule {
  id: number;
  keyword: string;
  category_id: number;
  category_name: string | null;
  match_type: string;
  priority: number;
  source: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CategorizeTransactionResponse {
  transaction_id: number;
  category_id: number | null;
  category_name: string | null;
  categorization_source: string;
  categorized_at: string | null;
  learned_rule: CategorizeLearnedRule | null;
}

export interface CategorizeBulkResponse {
  updated_count: number;
  transaction_ids?: number[];
  category_id?: number | null;
  category_name?: string | null;
  errors?: Array<{
    transaction_id: number;
    error: string;
    message?: string;
  }>;
}

export interface CategorizationRunResponse {
  processed: number;
  categorized: number;
  uncategorized: number;
  duration_ms: number;
}

export interface UploadIngestionResponse {
  batch_id: string;
  status: string;
  files: Array<{
    file_id: string;
    original_filename: string;
    mime_type: string;
    size_bytes: number;
    status: string;
  }>;
}

function joinPath(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  const normalizedBase = apiBase.endsWith("/") ? apiBase.slice(0, -1) : apiBase;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (normalizedPath.startsWith("/api/") && normalizedBase === "/api/v1") {
    return normalizedPath;
  }

  return `${normalizedBase}${normalizedPath}`;
}

function toQueryString(params?: Record<string, unknown>): string {
  if (!params) return "";

  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;

    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item === undefined || item === null || item === "") return;
        searchParams.append(key, String(item));
      });
      return;
    }

    searchParams.set(key, String(value));
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function normalizeErrorDetail(detail: unknown): ApiErrorPayload {
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const record = detail as JsonRecord;
    if ("code" in record || "message" in record || "details" in record) {
      return {
        code: typeof record.code === "string" ? record.code : undefined,
        message:
          typeof record.message === "string" ? record.message : undefined,
        details: "details" in record ? record.details : null,
      };
    }
  }

  return {
    code: "UNKNOWN_ERROR",
    message: "Request failed.",
    details: detail,
  };
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(joinPath(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(init.headers ?? {}),
    },
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const parsed = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = parsed?.detail ?? parsed?.error ?? parsed;
    const normalized = normalizeErrorDetail(detail);
    throw new ApiError(
      response.status,
      normalized.code ?? `HTTP_${response.status}`,
      normalized.message ?? `Request failed with status ${response.status}.`,
      normalized.details ?? detail,
    );
  }

  return parsed as T;
}

export async function uploadIngestionFiles(
  files: File[],
  accountId?: string | null,
): Promise<UploadIngestionResponse> {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append("files", file);
  });

  if (accountId) {
    formData.append("account_id", accountId);
  }

  return requestJson<UploadIngestionResponse>("/ingestion/upload", {
    method: "POST",
    body: formData,
  });
}

export async function listBatches(
  params: {
    page?: number;
    pageSize?: number;
    status?: string | null;
  } = {},
): Promise<BatchListResponse> {
  return requestJson<BatchListResponse>(
    `/ingestion/batches${toQueryString({
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      status: params.status ?? undefined,
    })}`,
  );
}

export async function getBatchStatus(batchId: string): Promise<{
  batch_id: string;
  status: string;
  created_at: string | null;
  files: Array<{
    file_id: string;
    original_filename: string;
    status: string;
    rows_extracted: number;
    rows_failed: number;
    error_message: string | null;
  }>;
  total_transactions_created: number;
  duplicates_skipped: number;
}> {
  return requestJson(`/ingestion/batches/${encodeURIComponent(batchId)}`);
}

export async function getBatchErrors(
  batchId: string,
  params: { page?: number; pageSize?: number } = {},
): Promise<BatchErrorsResponse> {
  return requestJson<BatchErrorsResponse>(
    `/ingestion/batches/${encodeURIComponent(batchId)}/errors${toQueryString({
      page: params.page ?? 1,
      page_size: params.pageSize ?? 50,
    })}`,
  );
}

export async function listCategories(includeSystem = true): Promise<{
  data: Category[];
  total: number;
}> {
  return requestJson(
    `/categories${toQueryString({ include_system: includeSystem })}`,
  );
}

export async function createCategory(input: {
  name: string;
  color?: string;
  icon?: string | null;
}): Promise<Category> {
  return requestJson<Category>("/categories", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateCategory(
  categoryId: number,
  input: Partial<{
    name: string;
    color: string;
    icon: string | null;
  }>,
): Promise<Category> {
  return requestJson<Category>(`/categories/${categoryId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deleteCategory(categoryId: number): Promise<void> {
  await requestJson<void>(`/categories/${categoryId}`, {
    method: "DELETE",
  });
}

export async function listRules(
  params: {
    categoryId?: number | null;
    source?: string | null;
    isActive?: boolean | null;
    search?: string | null;
    page?: number;
    pageSize?: number;
    sortBy?: string;
    sortOrder?: "asc" | "desc";
  } = {},
): Promise<{
  data: Rule[];
  total: number;
  page: number;
  page_size: number;
}> {
  return requestJson(
    `/rules${toQueryString({
      category_id: params.categoryId ?? undefined,
      source: params.source ?? undefined,
      is_active: params.isActive ?? undefined,
      search: params.search ?? undefined,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 50,
      sort_by: params.sortBy ?? "priority",
      sort_order: params.sortOrder ?? "desc",
    })}`,
  );
}

export async function createRule(input: {
  keyword: string;
  category_id: number;
  match_type?: "exact" | "contains" | "starts_with" | "ends_with";
  priority?: number;
}): Promise<Rule> {
  return requestJson<Rule>("/rules", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateRule(
  ruleId: number,
  input: Partial<{
    keyword: string;
    category_id: number;
    match_type: "exact" | "contains" | "starts_with" | "ends_with";
    priority: number;
    is_active: boolean;
  }>,
): Promise<Rule> {
  return requestJson<Rule>(`/rules/${ruleId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deleteRule(ruleId: number): Promise<void> {
  await requestJson<void>(`/rules/${ruleId}`, {
    method: "DELETE",
  });
}

export async function listTransactions(
  params: {
    page?: number;
    pageSize?: number;
    dateFrom?: string | null;
    dateTo?: string | null;
    categoryId?: number | null;
    accountId?: string | number | null;
    search?: string | null;
    sortBy?: string;
    sortOrder?: "asc" | "desc";
  } = {},
): Promise<TransactionListResponse> {
  return requestJson<TransactionListResponse>(
    `/transactions${toQueryString({
      page: params.page ?? 1,
      page_size: params.pageSize ?? 50,
      date_from: params.dateFrom ?? undefined,
      date_to: params.dateTo ?? undefined,
      category_id: params.categoryId ?? undefined,
      account_id: params.accountId ?? undefined,
      search: params.search ?? undefined,
      sort_by: params.sortBy ?? "date",
      sort_order: params.sortOrder ?? "desc",
    })}`,
  );
}

export async function getTransaction(
  transactionId: number,
): Promise<TransactionItem> {
  return requestJson<TransactionItem>(`/transactions/${transactionId}`);
}

export async function patchTransactionCategory(
  transactionId: number,
  categoryId: number | null,
): Promise<TransactionItem> {
  return requestJson<TransactionItem>(`/transactions/${transactionId}`, {
    method: "PATCH",
    body: JSON.stringify({ category_id: categoryId }),
  });
}

export async function bulkPatchTransactionCategories(
  transactionIds: number[],
  categoryId: number | null,
): Promise<CategorizeBulkResponse> {
  return requestJson<CategorizeBulkResponse>("/transactions/bulk", {
    method: "PATCH",
    body: JSON.stringify({
      transaction_ids: transactionIds,
      category_id: categoryId,
    }),
  });
}

export async function categorizeTransaction(
  transactionId: number,
  categoryId: number | null,
  learnRule = true,
): Promise<CategorizeTransactionResponse> {
  return requestJson<CategorizeTransactionResponse>(
    `/transactions/${transactionId}/categorize`,
    {
      method: "POST",
      body: JSON.stringify({ category_id: categoryId, learn_rule: learnRule }),
    },
  );
}

export async function categorizeBulkTransactions(
  transactionIds: number[],
  categoryId: number | null,
  learnRule = false,
): Promise<CategorizeBulkResponse> {
  return requestJson<CategorizeBulkResponse>("/transactions/categorize-bulk", {
    method: "POST",
    body: JSON.stringify({
      transaction_ids: transactionIds,
      category_id: categoryId,
      learn_rule: learnRule,
    }),
  });
}

export async function runCategorization(
  input: {
    scope?: "uncategorized" | "all";
    accountId?: string | number | null;
  } = {},
): Promise<CategorizationRunResponse> {
  return requestJson<CategorizationRunResponse>("/categorize/run", {
    method: "POST",
    body: JSON.stringify({
      scope: input.scope ?? "uncategorized",
      account_id: input.accountId ?? null,
    }),
  });
}

export interface AccountItem {
  id: string | number;
  name: string;
}

export interface AccountListResponse {
  items: AccountItem[];
  total: number;
}

export async function listAccounts(): Promise<AccountListResponse> {
  return requestJson<AccountListResponse>("/accounts");
}

// ── Dashboard (SPEC5) ────────────────────────────────────────────────────────────

export interface PeriodParams {
  month?: number;
  year?: number;
}

export interface MonthlyCategorySummary {
  category_id: number | null;
  category_name: string;
  total: number;
  percentage: number;
  transaction_count: number;
}

export interface MonthlySummaryResponse {
  month: number;
  year: number;
  total_expenses: number;
  total_income: number;
  net: number;
  categories: MonthlyCategorySummary[];
}

export interface CategoryBreakdownSlice {
  category_id: number | null;
  category_name: string;
  total: number;
  percentage: number;
  color: string;
}

export interface CategoryBreakdownResponse {
  month: number;
  year: number;
  slices: CategoryBreakdownSlice[];
  uncategorized_total: number;
  uncategorized_percentage: number;
}

export type TimeSeriesGranularity = "daily" | "monthly";

export interface TimeSeriesPoint {
  date: string;
  total_expenses: number;
  total_income: number;
}

export interface TimeSeriesPeriod {
  start: string;
  end: string;
}

export interface TimeSeriesResponse {
  granularity: TimeSeriesGranularity;
  period: TimeSeriesPeriod;
  data_points: TimeSeriesPoint[];
  cumulative_expenses: number;
  cumulative_income: number;
}

export type CardInvoiceStatus = "open" | "closed" | "paid" | "overdue";

export interface CardInvoice {
  account_id: string | number;
  account_name: string;
  current_invoice_total: number;
  transaction_count: number;
  closing_date: string;
  due_date: string;
  status: CardInvoiceStatus;
  days_until_due: number;
}

export interface UpcomingPayment {
  account_id: string | number;
  account_name: string;
  due_date: string;
  amount: number;
  days_until_due: number;
  is_urgent: boolean;
}

export interface CardTrackingResponse {
  month: number;
  year: number;
  cards: CardInvoice[];
  upcoming_payments: UpcomingPayment[];
  total_card_debt: number;
}

export const dashboardApi = {
  getMonthlySummary(params: PeriodParams) {
    return requestJson<MonthlySummaryResponse>(
      `/dashboard/monthly-summary${toQueryString({
        month: params.month ?? undefined,
        year: params.year ?? undefined,
      })}`,
    );
  },

  getCategoryBreakdown(params: PeriodParams) {
    return requestJson<CategoryBreakdownResponse>(
      `/dashboard/charts/category-breakdown${toQueryString({
        month: params.month ?? undefined,
        year: params.year ?? undefined,
      })}`,
    );
  },

  getTimeSeries(
    params: PeriodParams & {
      granularity?: TimeSeriesGranularity;
      monthsBack?: number;
    },
  ) {
    return requestJson<TimeSeriesResponse>(
      `/dashboard/charts/time-series${toQueryString({
        month: params.month ?? undefined,
        year: params.year ?? undefined,
        granularity: params.granularity ?? undefined,
        months_back: params.monthsBack ?? undefined,
      })}`,
    );
  },

  getCardTracking(params: PeriodParams) {
    return requestJson<CardTrackingResponse>(
      `/dashboard/card-tracking${toQueryString({
        month: params.month ?? undefined,
        year: params.year ?? undefined,
      })}`,
    );
  },
};

// ── Fixed Expenses ────────────────────────────────────────────────────────────

export type FixedExpenseFrequency =
  | "weekly"
  | "biweekly"
  | "monthly"
  | "bimonthly"
  | "quarterly"
  | "semiannual"
  | "annual";

export type FixedExpenseEntryStatus =
  | "pending"
  | "paid"
  | "skipped"
  | "cancelled";

export interface FixedExpenseItem {
  id: string;
  account_id: string;
  account_name: string;
  category_id: number | null;
  category_name: string | null;
  name: string;
  description: string | null;
  amount: string;
  frequency: FixedExpenseFrequency;
  day_of_month: number | null;
  day_of_week: number | null;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FixedExpenseEntryItem {
  id: string;
  fixed_expense_id: string;
  reference_date: string;
  due_date: string;
  amount: string;
  transaction_id: number | null;
  transaction: TransactionItem | null;
  status: FixedExpenseEntryStatus;
  created_at: string;
  updated_at: string;
}

export interface FixedExpenseListResponse {
  items: FixedExpenseItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FixedExpenseEntryListResponse {
  items: FixedExpenseEntryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface GenerationResult {
  generated_count: number;
  skipped_count: number;
  errors: Array<{ fixed_expense_id: string; error: string }>;
}

export interface CreateFixedExpenseInput {
  account_id: string;
  category_id?: number | null;
  name: string;
  description?: string | null;
  amount: string | number;
  frequency: FixedExpenseFrequency;
  day_of_month?: number | null;
  day_of_week?: number | null;
  start_date: string;
  end_date?: string | null;
}

export interface UpdateFixedExpenseInput {
  name?: string;
  description?: string | null;
  category_id?: number | null;
  amount?: string | number;
  frequency?: FixedExpenseFrequency;
  day_of_month?: number | null;
  day_of_week?: number | null;
  end_date?: string | null;
  is_active?: boolean;
}

export async function listFixedExpenses(
  params: {
    account_id?: string | null;
    is_active?: boolean;
    page?: number;
    page_size?: number;
  } = {},
): Promise<FixedExpenseListResponse> {
  return requestJson<FixedExpenseListResponse>(
    `/fixed-expenses${toQueryString({
      account_id: params.account_id ?? undefined,
      is_active: params.is_active ?? undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    })}`,
  );
}

export async function getFixedExpense(id: string): Promise<FixedExpenseItem> {
  return requestJson<FixedExpenseItem>(
    `/fixed-expenses/${encodeURIComponent(id)}`,
  );
}

export async function createFixedExpense(
  input: CreateFixedExpenseInput,
): Promise<FixedExpenseItem> {
  return requestJson<FixedExpenseItem>("/fixed-expenses", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateFixedExpense(
  id: string,
  input: UpdateFixedExpenseInput,
): Promise<FixedExpenseItem> {
  return requestJson<FixedExpenseItem>(
    `/fixed-expenses/${encodeURIComponent(id)}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
}

export async function deleteFixedExpense(id: string): Promise<void> {
  await requestJson<void>(`/fixed-expenses/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function listFixedExpenseEntries(
  expenseId: string,
  params: {
    status?: string | null;
    from_date?: string | null;
    to_date?: string | null;
    page?: number;
    page_size?: number;
  } = {},
): Promise<FixedExpenseEntryListResponse> {
  return requestJson<FixedExpenseEntryListResponse>(
    `/fixed-expenses/${encodeURIComponent(expenseId)}/entries${toQueryString({
      status: params.status ?? undefined,
      from_date: params.from_date ?? undefined,
      to_date: params.to_date ?? undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    })}`,
  );
}

export async function generateFixedExpenseEntries(input: {
  target_date: string;
  fixed_expense_id?: string | null;
}): Promise<GenerationResult> {
  return requestJson<GenerationResult>("/fixed-expenses/generate", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateFixedExpenseEntryStatus(
  entryId: string,
  input: { status: FixedExpenseEntryStatus; transaction_id?: number | null },
): Promise<FixedExpenseEntryItem> {
  return requestJson<FixedExpenseEntryItem>(
    `/fixed-expenses/entries/${encodeURIComponent(entryId)}`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
  );
}



// ─── SPEC 6 — Import ────────────────────────────────────────────────────────

export type ImportStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'completed_with_errors'
  | 'failed'

export type ImportFileStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface ImportFileDetail {
  id: number
  filename: string
  status: ImportFileStatus
  transactionsCount: number
  newCount: number
  duplicateCount: number
  errorMessage: string | null
}

export interface ImportSummary {
  id: number
  accountId: string
  status: ImportStatus
  totalFiles: number
  totalTransactions: number
  newTransactions: number
  duplicateTransactions: number
  failedFiles: number
  createdAt: string
  completedAt: string | null
}

export interface ImportDetail extends ImportSummary {
  files: ImportFileDetail[]
}

export interface ImportPagination {
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}

export interface ImportListResponse {
  items: ImportSummary[]
  pagination: ImportPagination
}

export interface ImportCreateResponse {
  id: number
  accountId: string
  status: string
  totalFiles: number
  createdAt: string
  files: Array<{
    filename: string
    status: string
    transactionsCount: number | null
  }>
}

function normalizeImportFileDetail(raw: Record<string, unknown>): ImportFileDetail {
  return {
    id: raw.id as number,
    filename: raw.filename as string,
    status: raw.status as ImportFileStatus,
    transactionsCount: (raw.transactions_count as number) ?? 0,
    newCount: (raw.new_count as number) ?? 0,
    duplicateCount: (raw.duplicate_count as number) ?? 0,
    errorMessage: (raw.error_message as string | null) ?? null,
  }
}

function normalizeImportSummary(raw: Record<string, unknown>): ImportSummary {
  return {
    id: raw.id as number,
    accountId: raw.account_id as string,
    status: raw.status as ImportStatus,
    totalFiles: (raw.total_files as number) ?? 0,
    totalTransactions: (raw.total_transactions as number) ?? 0,
    newTransactions: (raw.new_transactions as number) ?? 0,
    duplicateTransactions: (raw.duplicate_transactions as number) ?? 0,
    failedFiles: (raw.failed_files as number) ?? 0,
    createdAt: raw.created_at as string,
    completedAt: (raw.completed_at as string | null) ?? null,
  }
}

export async function createImport(
  files: File[],
  accountId: string,
): Promise<ImportCreateResponse> {
  const formData = new FormData()
  formData.append('account_id', accountId)
  files.forEach((f) => formData.append('files', f))

  const raw = await requestJson<Record<string, unknown>>('/imports', {
    method: 'POST',
    body: formData,
  })

  return {
    id: raw.id as number,
    accountId: raw.account_id as string,
    status: raw.status as string,
    totalFiles: raw.total_files as number,
    createdAt: raw.created_at as string,
    files: (raw.files as Array<Record<string, unknown>>).map((f) => ({
      filename: f.filename as string,
      status: f.status as string,
      transactionsCount: f.transactions_count as number | null,
    })),
  }
}

export async function listImports(params: {
  page?: number
  pageSize?: number
  accountId?: string | null
  status?: ImportStatus | null
} = {}): Promise<ImportListResponse> {
  const raw = await requestJson<Record<string, unknown>>(
    `/imports${toQueryString({
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      account_id: params.accountId ?? undefined,
      status: params.status ?? undefined,
    })}`,
  )

  const rawItems = (raw.items as Array<Record<string, unknown>>) ?? []
  const rawPag = (raw.pagination as Record<string, unknown>) ?? {}

  return {
    items: rawItems.map(normalizeImportSummary),
    pagination: {
      page: rawPag.page as number,
      pageSize: rawPag.page_size as number,
      totalItems: rawPag.total_items as number,
      totalPages: rawPag.total_pages as number,
    },
  }
}

export async function getImportDetail(importId: number): Promise<ImportDetail> {
  const raw = await requestJson<Record<string, unknown>>(
    `/imports/${encodeURIComponent(importId)}`,
  )
  const summary = normalizeImportSummary(raw)
  const files = ((raw.files as Array<Record<string, unknown>>) ?? []).map(
    normalizeImportFileDetail,
  )
  return { ...summary, files }
}
