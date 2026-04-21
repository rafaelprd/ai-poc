<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { getImportDetail } from '../../lib/api'
import type { ImportDetail } from '../../lib/api'
import importFileStatus from './importFileStatus.vue'

const props = defineProps<{
  importId: number
}>()

const emit = defineEmits<{
  importFinished: [detail: ImportDetail]
}>()

const importDetail = ref<ImportDetail | null>(null)
const pollError = ref<string | null>(null)
const loading = ref(true)

let timerId: ReturnType<typeof setTimeout> | null = null

const TERMINAL_STATUSES = new Set(['completed', 'completed_with_errors', 'failed'])

const isTerminal = computed(() =>
  importDetail.value ? TERMINAL_STATUSES.has(importDetail.value.status) : false,
)

const progressPercent = computed(() => {
  const detail = importDetail.value
  if (!detail || detail.totalFiles === 0) return 0
  // ImportDetail doesn't expose completedFiles — count terminal files from the
  // files array when available, otherwise fall back to failedFiles alone.
  const done = detail.files && detail.files.length > 0
    ? detail.files.filter((f) => f.status === 'completed' || f.status === 'failed').length
    : detail.failedFiles
  return Math.round((done / detail.totalFiles) * 100)
})

const doneFilesCount = computed(() => {
  const detail = importDetail.value
  if (!detail) return 0
  if (detail.files && detail.files.length > 0) {
    return detail.files.filter((f) => f.status === 'completed' || f.status === 'failed').length
  }
  return detail.failedFiles
})

// Helper: map ImportDetail status label
function statusLabel(status: string): string {
  switch (status) {
    case 'pending': return 'Pending'
    case 'processing': return 'Processing…'
    case 'completed': return 'Completed'
    case 'completed_with_errors': return 'Completed with errors'
    case 'failed': return 'Failed'
    default: return status
  }
}

async function fetchImport(): Promise<void> {
  try {
    const detail = await getImportDetail(props.importId)
    importDetail.value = detail
    pollError.value = null

    if (TERMINAL_STATUSES.has(detail.status)) {
      stopPolling()
      emit('importFinished', detail)
    }
  } catch (err) {
    pollError.value = err instanceof Error ? err.message : 'Failed to load import status.'
    stopPolling()
  } finally {
    loading.value = false
  }
}

function scheduleNext(): void {
  timerId = setTimeout(async () => {
    await fetchImport()
    if (!isTerminal.value && !pollError.value) {
      scheduleNext()
    }
  }, 2000)
}

function stopPolling(): void {
  if (timerId !== null) {
    clearTimeout(timerId)
    timerId = null
  }
}

// Start polling when importId becomes available / changes
watch(
  () => props.importId,
  (id) => {
    if (id == null) return
    stopPolling()
    loading.value = true
    importDetail.value = null
    pollError.value = null
    fetchImport().then(() => {
      if (!isTerminal.value && !pollError.value) {
        scheduleNext()
      }
    })
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <div class="trackerWrap stack">
    <!-- Loading skeleton -->
    <div v-if="loading && !importDetail" class="trackerLoading">
      <div class="spinnerWrap" aria-label="Loading import status…">
        <svg
          class="spinner"
          width="22"
          height="22"
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
        <span class="helperText">Loading import #{{ importId }}…</span>
      </div>
    </div>

    <!-- Poll error -->
    <div
      v-if="pollError"
      class="banner"
      style="border-color: hsl(var(--destructive) / 0.22); background: hsl(var(--destructive) / 0.07);"
    >
      <div>
        <p class="bannerTitle">Polling error</p>
        <p class="bannerText">{{ pollError }}</p>
      </div>
    </div>

    <!-- Main content (once loaded) -->
    <template v-if="importDetail">
      <!-- Header row -->
      <div class="rowBetween trackerHeader">
        <div class="stackSm">
          <p class="trackerTitle">Import #{{ importDetail.id }}</p>
          <p class="helperText">{{ statusLabel(importDetail.status) }}</p>
        </div>

        <div class="kpiRow trackerKpis">
          <article class="kpiCard">
            <p class="kpiValue">{{ importDetail.totalFiles }}</p>
            <p class="kpiLabel">Files</p>
          </article>
          <article class="kpiCard">
            <p class="kpiValue">{{ importDetail.newTransactions }}</p>
            <p class="kpiLabel">New txns</p>
          </article>
          <article class="kpiCard">
            <p class="kpiValue">{{ importDetail.duplicateTransactions }}</p>
            <p class="kpiLabel">Duplicates</p>
          </article>
          <article class="kpiCard" :class="{ kpiCardAlert: importDetail.failedFiles > 0 }">
            <p class="kpiValue">{{ importDetail.failedFiles }}</p>
            <p class="kpiLabel">Failed files</p>
          </article>
        </div>
      </div>

      <!-- Progress bar -->
      <div class="trackerProgressWrap">
        <div class="rowBetween trackerProgressLabel">
          <span class="helperText">
            {{ doneFilesCount }} / {{ importDetail.totalFiles }} files processed
          </span>
          <span class="helperText">{{ progressPercent }}%</span>
        </div>
        <div class="progressBar" role="progressbar" :aria-valuenow="progressPercent" aria-valuemin="0" aria-valuemax="100">
          <div
            class="progressBarFill"
            :style="{ width: `${progressPercent}%` }"
            :class="{ progressBarFillError: importDetail.failedFiles > 0 && isTerminal }"
          />
        </div>
      </div>

      <!-- Pulsing "in progress" hint -->
      <div v-if="!isTerminal" class="trackerLiveHint">
        <svg
          class="spinner spinnerSmall"
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
        <span class="helperText">Refreshing every 2 seconds…</span>
      </div>

      <!-- Per-file statuses -->
      <div v-if="importDetail.files && importDetail.files.length" class="list">
        <importFileStatus
          v-for="file in importDetail.files"
          :key="file.id"
          :file="{
            filename: file.filename,
            status: file.status,
            transactionsCount: file.transactionsCount,
            newCount: file.newCount,
            duplicateCount: file.duplicateCount,
            errorMessage: file.errorMessage,
          }"
        />
      </div>

      <div v-else class="emptyState">
        <p class="emptyStateTitle">No file details yet</p>
        <p class="emptyStateText">File statuses will appear once processing begins.</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.trackerWrap {
  display: grid;
  gap: var(--space-4);
}

/* ── Loading ─────────────────────────────────────────────── */
.trackerLoading {
  display: flex;
  justify-content: center;
  padding: var(--space-8);
}

.spinnerWrap {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: hsl(var(--muted-foreground));
}

/* ── Header ──────────────────────────────────────────────── */
.trackerHeader {
  flex-wrap: wrap;
  gap: var(--space-4);
  align-items: flex-start;
}

.trackerTitle {
  margin: 0;
  font-size: 1rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

/* ── KPI mini-row ────────────────────────────────────────── */
.trackerKpis {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.trackerKpis .kpiCard {
  min-width: 80px;
  padding: var(--space-3);
}

.trackerKpis .kpiValue {
  font-size: 1.15rem;
}

.kpiCardAlert .kpiValue {
  color: hsl(var(--destructive));
}

/* ── Progress ────────────────────────────────────────────── */
.trackerProgressWrap {
  display: grid;
  gap: var(--space-2);
}

.trackerProgressLabel {
  align-items: center;
}

.progressBarFillError {
  background: linear-gradient(90deg, hsl(var(--warning)), hsl(var(--destructive))) !important;
}

/* ── Live hint ───────────────────────────────────────────── */
.trackerLiveHint {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: hsl(var(--muted-foreground));
}

/* ── Spinner animation ───────────────────────────────────── */
.spinner {
  color: hsl(var(--warning));
  animation: spin 0.9s linear infinite;
  transform-origin: center;
}

.spinnerSmall {
  color: hsl(var(--muted-foreground));
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
