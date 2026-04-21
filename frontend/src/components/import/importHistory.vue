<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { listImports } from '../../lib/api'
import type { ImportSummary, ImportStatus } from '../../lib/api'
import importHistoryFilters from './importHistoryFilters.vue'
import importHistoryTable from './importHistoryTable.vue'
import importDetailModal from './importDetailModal.vue'
import Button from '../ui/Button.vue'

// ── State ─────────────────────────────────────────────────────────────────────

const page = ref(1)
const pageSize = 20

const statusFilter = ref<ImportStatus | undefined>(undefined)
const accountFilter = ref<string | undefined>(undefined)

const imports = ref<ImportSummary[]>([])
const pagination = ref({
  page: 1,
  pageSize,
  totalItems: 0,
  totalPages: 1,
})

const loading = ref(false)
const fetchError = ref<string | null>(null)

// Modal
const modalVisible = ref(false)
const selectedImportId = ref<number | null>(null)

// ── Data fetching ─────────────────────────────────────────────────────────────

async function fetchImports(): Promise<void> {
  loading.value = true
  fetchError.value = null

  try {
    const result = await listImports({
      page: page.value,
      pageSize,
      accountId: accountFilter.value,
      status: statusFilter.value,
    })

    imports.value = result.items
    pagination.value = result.pagination
  } catch (err) {
    fetchError.value =
      err instanceof Error ? err.message : 'Failed to load imports.'
    imports.value = []
  } finally {
    loading.value = false
  }
}

// ── Event handlers ────────────────────────────────────────────────────────────

function onFiltersChanged(filters: { accountId?: string; status?: ImportStatus }): void {
  // Reset to first page whenever filters change
  page.value = 1
  statusFilter.value = filters.status
  accountFilter.value = filters.accountId
  // watch will trigger fetchImports
}

function onPageChanged(newPage: number): void {
  page.value = newPage
}

function onImportSelected(importId: number): void {
  selectedImportId.value = importId
  modalVisible.value = true
}

function closeModal(): void {
  modalVisible.value = false
  // Keep selectedImportId so the modal fade-out animation finishes cleanly
}

// ── Reactivity ────────────────────────────────────────────────────────────────

// Re-fetch when page or filters change
watch([page, statusFilter, accountFilter], () => {
  fetchImports()
})

onMounted(() => {
  fetchImports()
})
</script>

<template>
  <section class="stack importHistoryRoot">
    <!-- ── Panel header ── -->
    <div class="panelHeader">
      <div>
        <h2 class="panelTitle">Import History</h2>
        <p class="panelDescription">
          All file imports and their processing results.
        </p>
      </div>

      <Button
        variant="outline"
        size="sm"
        type="button"
        :disabled="loading"
        @click="fetchImports"
      >
        <svg
          v-if="loading"
          class="refreshSpinner"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" stroke-opacity="0.2" />
          <path d="M12 2a10 10 0 0 1 10 10" />
        </svg>
        <svg
          v-else
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <polyline points="23 4 23 10 17 10" />
          <polyline points="1 20 1 14 7 14" />
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
        </svg>
        {{ loading ? 'Loading…' : 'Refresh' }}
      </Button>
    </div>

    <!-- ── Filters ── -->
    <importHistoryFilters @filters-changed="onFiltersChanged" />

    <!-- ── Error banner ── -->
    <div
      v-if="fetchError"
      class="banner"
      style="border-color: hsl(var(--destructive) / 0.22); background: hsl(var(--destructive) / 0.07);"
      role="alert"
    >
      <div>
        <p class="bannerTitle">Failed to load imports</p>
        <p class="bannerText">{{ fetchError }}</p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        type="button"
        @click="fetchImports"
      >
        Retry
      </Button>
    </div>

    <!-- ── Loading skeleton (first load only, no data yet) ── -->
    <div v-if="loading && imports.length === 0" class="importHistoryLoading">
      <svg
        class="loadingSpinner"
        width="22"
        height="22"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        aria-label="Loading imports…"
      >
        <circle cx="12" cy="12" r="10" stroke-opacity="0.2" />
        <path d="M12 2a10 10 0 0 1 10 10" />
      </svg>
      <span class="helperText">Loading imports…</span>
    </div>

    <!-- ── Table + pagination (rendered once we have either data or confirmed empty) ── -->
    <div
      v-else
      class="importHistoryTableWrap"
      :class="{ importHistoryFading: loading }"
    >
      <importHistoryTable
        :imports="imports"
        :pagination="pagination"
        @page-changed="onPageChanged"
        @import-selected="onImportSelected"
      />
    </div>

    <!-- ── Detail modal ── -->
    <importDetailModal
      :import-id="selectedImportId"
      :visible="modalVisible"
      @close="closeModal"
    />
  </section>
</template>

<style scoped>
/* ── Root layout ─────────────────────────────────────────── */
.importHistoryRoot {
  display: grid;
  gap: var(--space-5);
}

/* ── Panel header inherits global style;                  ── */
/* ── override gap to keep the refresh button aligned      ── */
.panelHeader {
  margin-bottom: 0;
}

/* ── Loading state ───────────────────────────────────────── */
.importHistoryLoading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-10);
  color: hsl(var(--muted-foreground));
}

/* ── Subtle fade while re-fetching with existing data ─── */
.importHistoryTableWrap {
  transition: opacity 0.2s ease;
}

.importHistoryFading {
  opacity: 0.55;
  pointer-events: none;
}

/* ── Spinner animations ──────────────────────────────────── */
.loadingSpinner,
.refreshSpinner {
  animation: spin 0.9s linear infinite;
  transform-origin: center;
  flex-shrink: 0;
}

.loadingSpinner {
  color: hsl(var(--warning));
}

.refreshSpinner {
  color: currentColor;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
