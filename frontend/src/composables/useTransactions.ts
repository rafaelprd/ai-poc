import { ref, readonly } from "vue";
import {
  listTransactions,
  patchTransactionCategory,
  bulkPatchTransactionCategories,
  type TransactionItem,
} from "../lib/api";

export interface TransactionFilters {
  dateFrom: string;
  dateTo: string;
  categoryId: number | null;
  accountId: string | number | null;
  search: string;
  sortBy: string;
  sortOrder: "asc" | "desc";
}

export interface Pagination {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export function useTransactions() {
  const transactions = ref<TransactionItem[]>([]);
  const pagination = ref<Pagination>({
    page: 1,
    pageSize: 50,
    totalItems: 0,
    totalPages: 1,
  });
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function fetchTransactions(
    filters: TransactionFilters,
    page: number,
    pageSize: number,
  ) {
    loading.value = true;
    error.value = null;
    try {
      const res = await listTransactions({
        page,
        pageSize,
        dateFrom: filters.dateFrom || null,
        dateTo: filters.dateTo || null,
        categoryId: filters.categoryId,
        accountId: filters.accountId,
        search: filters.search || null,
        sortBy: filters.sortBy,
        sortOrder: filters.sortOrder,
      });
      transactions.value = res.items;
      pagination.value = {
        page: res.pagination.page,
        pageSize: res.pagination.page_size,
        totalItems: res.pagination.total_items,
        totalPages: res.pagination.total_pages,
      };
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : "Failed to load transactions";
    } finally {
      loading.value = false;
    }
  }

  async function updateCategory(
    transactionId: number,
    categoryId: number | null,
  ): Promise<TransactionItem | null> {
    try {
      const updated = await patchTransactionCategory(transactionId, categoryId);
      const idx = transactions.value.findIndex(
        (t: TransactionItem) => t.id === transactionId,
      );
      if (idx !== -1) {
        transactions.value = [
          ...transactions.value.slice(0, idx),
          updated,
          ...transactions.value.slice(idx + 1),
        ];
      }
      return updated;
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : "Failed to update category";
      return null;
    }
  }

  async function bulkUpdateCategory(
    transactionIds: number[],
    categoryId: number | null,
  ) {
    try {
      const res = await bulkPatchTransactionCategories(
        transactionIds,
        categoryId,
      );
      // Optimistically update local state
      const updatedSet = new Set(transactionIds);
      transactions.value = transactions.value.map((t: TransactionItem) => {
        if (updatedSet.has(t.id)) {
          return { ...t, category_id: categoryId, category_name: null };
        }
        return t;
      });
      return res;
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : "Failed to bulk update";
      return null;
    }
  }

  return {
    transactions: readonly(transactions),
    pagination: readonly(pagination),
    loading: readonly(loading),
    error: readonly(error),
    fetchTransactions,
    updateCategory,
    bulkUpdateCategory,
  };
}
