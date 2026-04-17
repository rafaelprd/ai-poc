/// <reference types="vite/client" />

export type BatchStatus = 'processing' | 'completed' | 'partial_failure' | 'failed'
export type FileStatus = 'queued' | 'processing' | 'completed' | 'failed'
export type MatchType = 'exact' | 'contains' | 'starts_with' | 'ends_with'
export type RuleSource = 'manual' | 'learned' | 'system'
export type CategorizationSource = 'auto' | 'manual' | 'bulk'

export interface ApiError {
  code: string
  message: string
}

export interface ApiErrorResponse {
  detail?: ApiError
  error?: ApiError
}

export interface Category {
  id: number
  name: string
  color: string
  icon: string | null
  is_system: boolean
  created_at: string
  updated_at: string
}

export interface Rule {
  id: number
  keyword: string
  category_id: number
  category_name: string | null
  match_type: MatchType
  priority: number
  source: RuleSource
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Transaction {
  id: number
  date: string
  description: string
  original_description: string
  amount: number
  category_id: number | null
  category_name: string | null
  account_id: string | null
  account_name: string | null
  import_id: string | null
  categorization_source?: CategorizationSource | null
  categorized_at?: string | null
  created_at: string
  updated_at: string
}

export interface Pagination {
  page: number
  page_size: number
  total_items: number
  total_pages: number
}

export interface TransactionListResponse {
  items: Transaction[]
  pagination: Pagination
}

export interface CategoryListResponse {
  data: Category[]
  total: number
}

export interface RuleListResponse {
  data: Rule[]
  total: number
  page: number
  page_size: number
}

export interface IngestionFileSummary {
  file_id: string
  original_filename: string
  mime_type: string
  size_bytes: number
  status: FileStatus
}

export interface IngestionBatchFileStatus {
  file_id: string
  original_filename: string
  status: FileStatus
  rows_extracted: number
  rows_failed: number
  error_message: string | null
}

export interface IngestionBatchCreateResponse {
  batch_id: string
  status: BatchStatus
  files: IngestionFileSummary[]
}

export interface IngestionBatchStatusResponse {
  batch_id: string
  status: BatchStatus
  created_at: string
  files: IngestionBatchFileStatus[]
  total_transactions_created: number
  duplicates_skipped: number
}

export interface IngestionErrorItem {
  file_id: string
  original_filename: string | null
  row_number: number | null
  raw_data: string | null
  error_type: string
  error_message: string
}

export interface IngestionBatchErrorsResponse {
  batch_id: string
  errors: IngestionErrorItem[]
  total: number
  page: number
  page_size: number
}

export interface IngestionBatchesResponse {
  batches: Array<{
    batch_id: string
    status: BatchStatus
    file_count: number
    total_transactions_created: number
    created_at: string
  }>
  total: number
  page: number
  page_size: number
}

export interface TransactionCategorizeResponse {
  transaction_id: number
  category_id: number | null
  category_name: string | null
  categorization_source: CategorizationSource
  categorized_at: string | null
  learned_rule: Rule | null
}

export interface BulkCategorizeResponse {
  updated_count: number
  transaction_ids?: number[]
  category_id?: number | null
  category_name?: string | null
  errors?: Array<{
    transaction_id: number
    error: string
  }>
}

export interface CategorizationRunResponse {
  processed: number
  categorized: number
  uncategorized: number
  duration_ms: number
}

export interface FileUploadState {
  batchId: string | null
  status: BatchStatus | null
  message: string | null
}
