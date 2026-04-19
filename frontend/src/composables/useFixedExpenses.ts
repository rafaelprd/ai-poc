import { ref, readonly } from "vue";
import {
  listFixedExpenses,
  getFixedExpense,
  createFixedExpense,
  updateFixedExpense,
  deleteFixedExpense,
  listFixedExpenseEntries,
  generateFixedExpenseEntries,
  updateFixedExpenseEntryStatus,
  type FixedExpenseItem,
  type FixedExpenseEntryItem,
  type CreateFixedExpenseInput,
  type UpdateFixedExpenseInput,
  type GenerationResult,
  type FixedExpenseEntryStatus,
} from "../lib/api";

export function useFixedExpenses() {
  const expenses = ref<FixedExpenseItem[]>([]);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const total = ref(0);
  const totalPages = ref(1);
  const currentPage = ref(1);

  async function fetchExpenses(
    params: {
      account_id?: string | null;
      is_active?: boolean;
      page?: number;
      page_size?: number;
    } = {},
  ) {
    isLoading.value = true;
    error.value = null;
    try {
      const res = await listFixedExpenses(params);
      expenses.value = res.items;
      total.value = res.total;
      totalPages.value = res.total_pages;
      currentPage.value = res.page;
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : "Failed to load fixed expenses";
    } finally {
      isLoading.value = false;
    }
  }

  async function createExpense(
    data: CreateFixedExpenseInput,
  ): Promise<FixedExpenseItem | null> {
    try {
      const created = await createFixedExpense(data);
      expenses.value = [created, ...expenses.value];
      total.value += 1;
      return created;
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : "Failed to create fixed expense";
      return null;
    }
  }

  async function updateExpense(
    id: string,
    data: UpdateFixedExpenseInput,
  ): Promise<FixedExpenseItem | null> {
    try {
      const updated = await updateFixedExpense(id, data);
      const idx = expenses.value.findIndex(
        (exp: FixedExpenseItem) => exp.id === id,
      );
      if (idx !== -1) {
        expenses.value = [
          ...expenses.value.slice(0, idx),
          updated,
          ...expenses.value.slice(idx + 1),
        ];
      }
      return updated;
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : "Failed to update fixed expense";
      return null;
    }
  }

  async function removeExpense(id: string): Promise<boolean> {
    try {
      await deleteFixedExpense(id);
      expenses.value = expenses.value.filter(
        (exp: FixedExpenseItem) => exp.id !== id,
      );
      total.value = Math.max(0, total.value - 1);
      return true;
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : "Failed to delete fixed expense";
      return false;
    }
  }

  async function fetchEntries(
    expenseId: string,
    params: {
      status?: string | null;
      from_date?: string | null;
      to_date?: string | null;
      page?: number;
      page_size?: number;
    } = {},
  ): Promise<{
    items: FixedExpenseEntryItem[];
    total: number;
    totalPages: number;
  } | null> {
    try {
      const res = await listFixedExpenseEntries(expenseId, params);
      return {
        items: res.items,
        total: res.total,
        totalPages: res.total_pages,
      };
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : "Failed to load entries";
      return null;
    }
  }

  async function updateEntryStatus(
    entryId: string,
    status: FixedExpenseEntryStatus,
    transactionId?: number | null,
  ): Promise<FixedExpenseEntryItem | null> {
    try {
      return await updateFixedExpenseEntryStatus(entryId, {
        status,
        transaction_id: transactionId,
      });
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : "Failed to update entry status";
      return null;
    }
  }

  async function generateEntries(
    targetDate: string,
    expenseId?: string | null,
  ): Promise<GenerationResult | null> {
    try {
      return await generateFixedExpenseEntries({
        target_date: targetDate,
        fixed_expense_id: expenseId ?? null,
      });
    } catch (e: unknown) {
      error.value =
        e instanceof Error ? e.message : "Failed to generate entries";
      return null;
    }
  }

  return {
    expenses: readonly(expenses),
    isLoading: readonly(isLoading),
    error: readonly(error),
    total: readonly(total),
    totalPages: readonly(totalPages),
    currentPage: readonly(currentPage),
    fetchExpenses,
    createExpense,
    updateExpense,
    removeExpense,
    fetchEntries,
    updateEntryStatus,
    generateEntries,
  };
}
