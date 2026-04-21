<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ImportStatus } from '../../lib/api'

const emit = defineEmits<{
  filtersChanged: [filters: { accountId?: string; status?: ImportStatus }]
}>()

const statusOptions: { value: ImportStatus | ''; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'completed_with_errors', label: 'Completed with errors' },
  { value: 'failed', label: 'Failed' },
]

const selectedStatus = ref<ImportStatus | ''>('')
const accountIdInput = ref('')

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function emitFilters(): void {
  emit('filtersChanged', {
    accountId: accountIdInput.value.trim() || undefined,
    status: (selectedStatus.value as ImportStatus) || undefined,
  })
}

function scheduleEmit(): void {
  if (debounceTimer !== null) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emitFilters()
    debounceTimer = null
  }, 300)
}

// Status change is instant (dropdown) but still debounced for consistency
watch(selectedStatus, () => scheduleEmit())
watch(accountIdInput, () => scheduleEmit())

function clearFilters(): void {
  if (debounceTimer !== null) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
  selectedStatus.value = ''
  accountIdInput.value = ''
  emitFilters()
}

const hasActiveFilters = () =>
  selectedStatus.value !== '' || accountIdInput.value.trim() !== ''
</script>

<template>
  <div class="filtersBar">
    <div class="filtersRow">
      <!-- Status filter -->
      <label class="field filtersField">
        <span class="fieldLabel">Status</span>
        <select
          v-model="selectedStatus"
          class="select"
          aria-label="Filter by status"
        >
          <option
            v-for="opt in statusOptions"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </option>
        </select>
      </label>

      <!-- Account ID filter -->
      <label class="field filtersField">
        <span class="fieldLabel">Account ID</span>
        <input
          v-model="accountIdInput"
          type="text"
          class="input"
          placeholder="Filter by account…"
          aria-label="Filter by account ID"
        />
      </label>

      <!-- Clear button — only visible when a filter is active -->
      <div class="filtersClearWrap">
        <span class="fieldLabel filtersFieldLabelHidden" aria-hidden="true">&#8203;</span>
        <button
          v-if="hasActiveFilters()"
          type="button"
          class="button buttonGhost buttonCompact filtersClear"
          @click="clearFilters"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            aria-hidden="true"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          Clear filters
        </button>
      </div>
    </div>

    <!-- Active filter chips -->
    <div v-if="hasActiveFilters()" class="filtersActive" aria-live="polite">
      <span class="helperText">Active filters:</span>

      <span
        v-if="selectedStatus"
        class="filterChip"
      >
        Status:
        <strong>{{ statusOptions.find((o) => o.value === selectedStatus)?.label ?? selectedStatus }}</strong>
        <button
          type="button"
          class="filterChipRemove"
          :aria-label="`Remove status filter: ${selectedStatus}`"
          @click="() => { selectedStatus = ''; scheduleEmit() }"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </span>

      <span
        v-if="accountIdInput.trim()"
        class="filterChip"
      >
        Account:
        <strong>{{ accountIdInput.trim() }}</strong>
        <button
          type="button"
          class="filterChipRemove"
          aria-label="Remove account filter"
          @click="() => { accountIdInput = ''; scheduleEmit() }"
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </span>
    </div>
  </div>
</template>

<style scoped>
/* ── Outer shell ─────────────────────────────────────────── */
.filtersBar {
  display: grid;
  gap: var(--space-3);
}

/* ── Controls row ────────────────────────────────────────── */
.filtersRow {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  align-items: flex-end;
}

.filtersField {
  flex: 1 1 180px;
  min-width: 150px;
  max-width: 320px;
}

/* ── Clear button alignment ──────────────────────────────── */
.filtersClearWrap {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding-bottom: 0;
}

.filtersFieldLabelHidden {
  display: block;
  /* mirrors the .fieldLabel height so the button aligns with inputs */
  visibility: hidden;
  user-select: none;
  pointer-events: none;
  margin-bottom: 0.3rem;
}

.filtersClear {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  white-space: nowrap;
}

/* ── Active chips row ────────────────────────────────────── */
.filtersActive {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.filterChip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.28rem 0.55rem 0.28rem 0.65rem;
  font-size: 0.8rem;
  border-radius: 999px;
  background: hsl(var(--secondary));
  border: 1px solid hsl(var(--border));
  color: hsl(var(--foreground));
  line-height: 1;
}

.filterChip strong {
  font-weight: 800;
}

.filterChipRemove {
  all: unset;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  color: hsl(var(--muted-foreground));
  transition: color 0.14s ease, background 0.14s ease;
  margin-left: 0.1rem;
}

.filterChipRemove:hover {
  color: hsl(var(--foreground));
  background: hsl(var(--accent));
}

.filterChipRemove:focus-visible {
  outline: 2px solid hsl(var(--ring));
  outline-offset: 1px;
}
</style>
