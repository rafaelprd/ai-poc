// Re-exports and typed wrappers for transaction-related API calls
export {
  listTransactions,
  getTransaction,
  patchTransactionCategory,
  bulkPatchTransactionCategories,
  listCategories,
  listAccounts,
  ApiError,
  type TransactionItem,
  type TransactionListResponse,
  type Category,
  type AccountItem,
  type AccountListResponse,
} from '../lib/api'
