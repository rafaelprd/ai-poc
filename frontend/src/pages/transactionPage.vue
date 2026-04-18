<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useTransactions, type TransactionFilters as FilterState } from '../composables/useTransactions'
import { useCategories } from '../composables/useCategories'
import { useAccounts } from '../composables/useAccounts'
import TransactionFilters from '../components/transactions/transactionFilters.vue'
import TransactionTable from '../components/transactions/transactionTable.vue'
import BulkActionBar from '../components/transactions/bulkActionBar.vue'
import PaginationControls from '../components/common/paginationControls.vue'
import type { TransactionItem } from '../lib/api'

// ── helpers ──────────────────────────────────────────────────────────────────

function currentMonthRange(): { dateFrom: string; dateTo: string } {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const lastDay = new Date(y, now.getMonth() + 1, 0).getDate()
  return {
    dateFrom: `${y}-${m}-01`,
    dateTo: `${y}-${m}-${String(lastDay).padStart(2, '0')}`,
  }
}

// ── composables ───────────────────────────────────────────────────────────────

const { transactions, pagination, loading, error, fetchTransactions, bulkUpdateCategory } =
  useTransactions()
const { categories, fetchCategories } = useCategories()
const { accounts, fetchAccounts } = useAccounts()

// ── state ─────────────────────────────────────────────────────────────────────

const { dateFrom, dateTo } = currentMonthRange()

const filters = reactive<FilterState>({
  dateFrom,
  dateTo,
  categoryId: null,
  accountId: null,
  search: '',
  sortBy: 'date',
  sortOrder: 'desc',
})

const page = ref(1)
const pageSize = ref(50)

const selectedIds = ref<Set<number>>(new Set())

// toast -----------------------------------------------------------------------

interface Toast {
  id: number
  type: 'success' | 'error' | 'warning'
  title: string
  body: string
}

let _toastSeq = 0
const toasts = ref<Toast[]>([])

function showToast(type: Toast['type'], title: string, body: string) {
  const id = ++_toastSeq
  toasts.value.push({ id, type, title, body })
  setTimeout(() => {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }, 5000)
}

function dismissToast(id: number) {
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

// ── data loading ──────────────────────────────────────────────────────────────

async function load() {
  await fetchTransactions(filters, page.value, pageSize.value)
  if (error.value) {
    showToast('error', 'Failed to load', error.value)
  }
}

async function onFiltersUpdated(newFilters: FilterState) {
  Object.assign(filters, newFilters)
  page.value = 1
  selectedIds.value = new Set()
  await load()
}

async function onPageChange(newPage: number) {
  page.value = newPage
  selectedIds.value = new Set()
  await load()
}

async function onPageSizeChange(newSize: number) {
  pageSize.value = newSize
  page.value = 1
  selectedIds.value = new Set()
  await load()
}

// ── sorting ───────────────────────────────────────────────────────────────────

async function onSortByChange(col: string) {
  filters.sortBy = col
  page.value = 1
  await load()
}

async function onSortOrderChange(order: 'asc' | 'desc') {
  filters.sortOrder = order
  page.value = 1
  await load()
}

// ── selection ─────────────────────────────────────────────────────────────────

function onSelectedIdsUpdate(next: Set<number>) {
  selectedIds.value = next
}

// ── category update (inline single) ──────────────────────────────────────────

function onCategoryUpdated(tx: TransactionItem) {
  showToast('success', 'Category saved', `Transaction #${tx.id} updated.`)
  // The composable already patches local state optimistically via patchTransactionCategory,
  // but here the update arrived via the inline editor directly — re-fetch to stay in sync.
  load()
}

// ── bulk update ───────────────────────────────────────────────────────────────

async function onBulkUpdate({ categoryId }: { categoryId: number | null }) {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return

  const result = await bulkUpdateCategory(ids, categoryId)

  if (!result) {
    showToast('error', 'Bulk update failed', error.value ?? 'Unknown error')
    return
  }

  const updated = result.updated_count ?? 0
  const errors = result.errors ?? []

  if (errors.length > 0) {
    showToast(
      'warning',
      'Partial update',
      `${updated} updated, ${errors.length} not found.`,
    )
  } else {
    showToast('success', 'Bulk update complete', `${updated} transaction(s) updated.`)
  }

  selectedIds.value = new Set()
  await load()
}

function onClearSelection() {
  selectedIds.value = new Set()
}

// ── lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  await Promise.all([fetchCategories(), fetchAccounts(), load()])
})
</script>

<template>
  <div class="stack" style="gap: 16px; position: relative;">

    <!-- Toast stack -->
    <div class="toastStack">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast"
        :class="{
          toastSuccess: toast.type === 'success',
          toastError: toast.type === 'error',
        }"
        style="cursor: pointer;"
        @click="dismissToast(toast.id)"
      >
        <p class="toastTitle">{{ toast.title }}</p>
        <p class="toastBody">{{ toast.body }}</p>
      </div>
    </div>

    <!-- KPI bar -->
    <div class="kpiRow">
      <div class="kpiCard">
        <p class="kpiValue">{{ pagination.totalItems }}</p>
        <p class="kpiLabel">Transactions</p>
      </div>
      <div class="kpiCard">
        <p class="kpiValue">{{ pagination.totalPages }}</p>
        <p class="kpiLabel">Pages</p>
      </div>
      <div class="kpiCard">
        <p class="kpiValue">{{ selectedIds.size }}</p>
        <p class="kpiLabel">Selected</p>
      </div>
      <div class="kpiCard">
        <p class="kpiValue">{{ categories.length }}</p>
        <p class="kpiLabel">Categories</p>
      </div>
    </div>

    <!-- Filters -->
    <TransactionFilters
      :current-filters="filters"
      :categories="(categories as any)"
      :accounts="(accounts as any)"
      @update:filters="onFiltersUpdated"
    />

    <!-- Bulk action bar (appears when rows selected) -->
    <BulkActionBar
      :selected-count="selectedIds.size"
      :categories="(categories as any)"
      @bulk-update="onBulkUpdate"
      @clear-selection="onClearSelection"
    />

    <!-- Table -->
    <TransactionTable
      :transactions="transactions"
      :selected-ids="selectedIds"
      :loading="loading"
      :sort-by="filters.sortBy"
      :sort-order="filters.sortOrder"
      :categories="(categories as any)"
      @update:selected-ids="onSelectedIdsUpdate"
      @update:sort-by="onSortByChange"
      @update:sort-order="onSortOrderChange"
      @category-updated="onCategoryUpdated"
    />

    <!-- Pagination -->
    <PaginationControls
      :page="pagination.page"
      :page-size="pagination.pageSize"
      :total-items="pagination.totalItems"
      :total-pages="pagination.totalPages"
      @update:page="onPageChange"
      @update:page-size="onPageSizeChange"
    />

  </div>
</template>
