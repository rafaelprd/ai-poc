<script setup lang="ts">
import { computed } from 'vue'
import type { ImportSummary } from '../../lib/api'
import Badge from '../ui/Badge.vue'
import Button from '../ui/Button.vue'

const props = defineProps<{
  imports: ImportSummary[]
  pagination: {
    page: number
    pageSize: number
    totalItems: number
    totalPages: number
  }
}>()

const emit = defineEmits<{
  pageChanged: [page: number]
  importSelected: [importId: number]
}>()

// ── Helpers ───────────────────────────────────────────────────────────────────

type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'destructive'

function statusVariant(status: string): BadgeVariant {
  switch (status) {
    case 'completed':
      return 'success'
    case 'completed_with_errors':
      return 'warning'
    case 'failed':
      return 'destructive'
    case 'processing':
      return 'warning'
    case 'pending':
      return 'secondary'
    default:
      return 'default'
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'pending':
      return 'Pending'
    case 'processing':
      return 'Processing'
    case 'completed':
      return 'Completed'
    case 'completed_with_errors':
      return 'Partial'
    case 'failed':
      return 'Failed'
    default:
      return status
  }
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

function truncateId(id: string | null): string {
  if (!id) return '—'
  return id.length > 16 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id
}

// ── Pagination ─────────────────────────────────────────────────────────────────

const hasPrev = computed(() => props.pagination.page > 1)
const hasNext = computed(() => props.pagination.page < props.pagination.totalPages)

const pageStart = computed(() => {
  if (props.pagination.totalItems === 0) return 0
  return (props.pagination.page - 1) * props.pagination.pageSize + 1
})

const pageEnd = computed(() =>
  Math.min(
    props.pagination.page * props.pagination.pageSize,
    props.pagination.totalItems,
  ),
)

function goTo(page: number): void {
  if (page < 1 || page > props.pagination.totalPages) return
  emit('pageChanged', page)
}
</script>

<template>
  <div class="stack historyTableRoot">
    <!-- ── Table ── -->
    <div class="tableWrap">
      <table class="table">
        <thead>
          <tr>
            <th class="colId">ID</th>
            <th class="colAccount">Account</th>
            <th class="colStatus">Status</th>
            <th class="colNum">Files</th>
            <th class="colNum">New Txns</th>
            <th class="colNum">Duplicates</th>
            <th class="colDate">Date</th>
            <th class="colActions">Actions</th>
          </tr>
        </thead>

        <tbody>
          <!-- Empty state row -->
          <tr v-if="imports.length === 0">
            <td colspan="8" class="emptyCell">
              <div class="emptyState">
                <p class="emptyStateTitle">No imports found</p>
                <p class="emptyStateText">
                  No imports match your current filters. Try adjusting them or upload new files.
                </p>
              </div>
            </td>
          </tr>

          <!-- Data rows -->
          <tr
            v-for="row in imports"
            :key="row.id"
            class="historyRow"
          >
            <!-- ID -->
            <td>
              <span class="rowId">#{{ row.id }}</span>
            </td>

            <!-- Account -->
            <td>
              <span
                class="accountId truncate"
                :title="row.accountId || undefined"
              >
                {{ truncateId(row.accountId) }}
              </span>
            </td>

            <!-- Status -->
            <td>
              <Badge :variant="statusVariant(row.status)">
                {{ statusLabel(row.status) }}
              </Badge>
            </td>

            <!-- Files -->
            <td>
              <span class="numCell">
                <span class="numPrimary">{{ row.totalFiles }}</span>
                <span
                  v-if="row.failedFiles > 0"
                  class="numFailed"
                  :title="`${row.failedFiles} failed`"
                >
                  ({{ row.failedFiles }} failed)
                </span>
              </span>
            </td>

            <!-- New transactions -->
            <td>
              <span class="numPrimary numSuccess">{{ row.newTransactions }}</span>
            </td>

            <!-- Duplicates -->
            <td>
              <span class="numPrimary numMuted">{{ row.duplicateTransactions }}</span>
            </td>

            <!-- Date -->
            <td>
              <span class="dateCell">{{ formatDate(row.createdAt) }}</span>
            </td>

            <!-- Actions -->
            <td>
              <div class="tableActions">
                <Button
                  variant="outline"
                  size="sm"
                  type="button"
                  :aria-label="`View import #${row.id}`"
                  @click="emit('importSelected', row.id)"
                >
                  View
                </Button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Pagination ── -->
    <div v-if="pagination.totalItems > 0" class="rowBetween paginationBar">
      <!-- Item count summary -->
      <p class="helperText paginationSummary">
        Showing
        <strong>{{ pageStart }}–{{ pageEnd }}</strong>
        of
        <strong>{{ pagination.totalItems }}</strong>
        imports
      </p>

      <!-- Page controls -->
      <div class="paginationControls">
        <Button
          variant="outline"
          size="sm"
          type="button"
          :disabled="!hasPrev"
          aria-label="Previous page"
          @click="goTo(pagination.page - 1)"
        >
          <svg
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
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Prev
        </Button>

        <!-- Page number pills -->
        <div class="paginationPages" aria-label="Page navigation">
          <button
            v-for="p in pagination.totalPages"
            :key="p"
            type="button"
            class="pagePill"
            :class="{ pagePillActive: p === pagination.page }"
            :aria-current="p === pagination.page ? 'page' : undefined"
            :aria-label="`Page ${p}`"
            @click="goTo(p)"
          >
            {{ p }}
          </button>
        </div>

        <Button
          variant="outline"
          size="sm"
          type="button"
          :disabled="!hasNext"
          aria-label="Next page"
          @click="goTo(pagination.page + 1)"
        >
          Next
          <svg
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
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.historyTableRoot {
  display: grid;
  gap: var(--space-4);
}

/* ── Column widths ───────────────────────────────────────── */
.colId      { width: 60px; }
.colAccount { width: 160px; }
.colStatus  { width: 130px; }
.colNum     { width: 90px; text-align: right; }
.colDate    { width: 160px; }
.colActions { width: 80px; }

.table td.colNum,
.table th.colNum {
  text-align: right;
}

/* ── Row ID ──────────────────────────────────────────────── */
.rowId {
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: -0.01em;
  color: hsl(var(--muted-foreground));
}

/* ── Account ID ──────────────────────────────────────────── */
.accountId {
  display: block;
  max-width: 150px;
  font-size: 0.82rem;
  font-family: ui-monospace, 'Cascadia Code', 'Fira Mono', monospace;
  color: hsl(var(--foreground));
}

/* ── Numeric cells ───────────────────────────────────────── */
.numCell {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.numPrimary {
  font-weight: 800;
  font-size: 0.9rem;
  letter-spacing: -0.02em;
}

.numSuccess {
  color: hsl(var(--success));
}

.numMuted {
  color: hsl(var(--muted-foreground));
}

.numFailed {
  font-size: 0.75rem;
  color: hsl(var(--destructive));
  font-weight: 600;
}

/* ── Date cell ───────────────────────────────────────────── */
.dateCell {
  font-size: 0.82rem;
  color: hsl(var(--muted-foreground));
  white-space: nowrap;
}

/* ── Hover row ───────────────────────────────────────────── */
.historyRow {
  transition: background 0.12s ease;
}

/* ── Empty cell ──────────────────────────────────────────── */
.emptyCell {
  padding: 0 !important;
  border-bottom: none !important;
}

.emptyCell .emptyState {
  border-radius: 0;
  border: none;
  border-top: none;
}

/* ── Pagination bar ──────────────────────────────────────── */
.paginationBar {
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: center;
}

.paginationSummary {
  margin: 0;
}

.paginationControls {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* ── Page number pills ───────────────────────────────────── */
.paginationPages {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.pagePill {
  appearance: none;
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius);
  background: transparent;
  color: hsl(var(--foreground));
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  padding: 0.28rem 0.6rem;
  line-height: 1;
  transition: background 0.14s ease, border-color 0.14s ease, color 0.14s ease;
  min-width: 2rem;
  text-align: center;
}

.pagePill:hover:not(.pagePillActive) {
  background: hsl(var(--accent));
  border-color: hsl(var(--border));
}

.pagePillActive {
  background: hsl(var(--primary));
  border-color: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
  cursor: default;
}

.pagePill:focus-visible {
  outline: 2px solid hsl(var(--ring));
  outline-offset: 2px;
}

/* ── Responsive: hide page pills on very small screens ──── */
@media (max-width: 500px) {
  .paginationPages {
    display: none;
  }
}
</style>
