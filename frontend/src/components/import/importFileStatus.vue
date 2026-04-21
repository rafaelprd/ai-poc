<script setup lang="ts">
import { computed } from 'vue'
import Badge from '../ui/Badge.vue'

const props = defineProps<{
  file: {
    filename: string
    status: string
    transactionsCount: number | null
    newCount: number
    duplicateCount: number
    errorMessage: string | null
  }
}>()

type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'destructive'

const isTerminal = computed(() =>
  props.file.status === 'completed' || props.file.status === 'failed',
)

const isPending = computed(() =>
  props.file.status === 'pending' || props.file.status === 'processing',
)

const isCompleted = computed(() => props.file.status === 'completed')
const isFailed = computed(() => props.file.status === 'failed')

const statusVariant = computed((): BadgeVariant => {
  switch (props.file.status) {
    case 'completed':
      return 'success'
    case 'failed':
      return 'destructive'
    case 'processing':
      return 'warning'
    default:
      return 'secondary'
  }
})

const statusLabel = computed(() => {
  switch (props.file.status) {
    case 'pending':
      return 'Pending'
    case 'processing':
      return 'Processing…'
    case 'completed':
      return 'Completed'
    case 'failed':
      return 'Failed'
    default:
      return props.file.status
  }
})
</script>

<template>
  <div class="fileStatusItem" :class="{ fileStatusFailed: isFailed, fileStatusCompleted: isCompleted }">
    <!-- Leading icon / spinner -->
    <div class="fileStatusIcon" aria-hidden="true">
      <!-- Spinner for pending / processing -->
      <svg
        v-if="isPending"
        class="spinner"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
      >
        <circle cx="12" cy="12" r="10" stroke-opacity="0.2" />
        <path d="M12 2a10 10 0 0 1 10 10" />
      </svg>

      <!-- Green check for completed -->
      <svg
        v-else-if="isCompleted"
        class="iconSuccess"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="12" cy="12" r="10" />
        <polyline points="9 12 11 14 15 10" />
      </svg>

      <!-- Red X for failed -->
      <svg
        v-else-if="isFailed"
        class="iconFailed"
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="15" y1="9" x2="9" y2="15" />
        <line x1="9" y1="9" x2="15" y2="15" />
      </svg>
    </div>

    <!-- Main content -->
    <div class="fileStatusBody">
      <div class="fileStatusHeader">
        <span class="fileStatusName truncate">{{ file.filename }}</span>
        <Badge :variant="statusVariant">{{ statusLabel }}</Badge>
      </div>

      <!-- Counts row — only when processing has something to show or completed -->
      <div v-if="isCompleted || (isPending && file.transactionsCount !== null)" class="fileStatusCounts">
        <span v-if="file.transactionsCount !== null" class="countChip">
          <span class="countValue">{{ file.transactionsCount }}</span>
          <span class="countLabel">total</span>
        </span>
        <span class="countDivider" aria-hidden="true" />
        <span class="countChip countChipNew">
          <span class="countValue">{{ file.newCount }}</span>
          <span class="countLabel">new</span>
        </span>
        <span class="countDivider" aria-hidden="true" />
        <span class="countChip countChipDup">
          <span class="countValue">{{ file.duplicateCount }}</span>
          <span class="countLabel">duplicate</span>
        </span>
      </div>

      <!-- Processing hint -->
      <p v-if="isPending && file.transactionsCount === null" class="helperText fileStatusHint">
        {{ file.status === 'processing' ? 'Parsing file…' : 'Waiting in queue…' }}
      </p>

      <!-- Error message -->
      <p v-if="isFailed && file.errorMessage" class="errorText fileStatusError">
        {{ file.errorMessage }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.fileStatusItem {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
  padding: var(--space-3) var(--space-4);
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius-lg);
  background: linear-gradient(
    180deg,
    rgb(255 255 255 / 0.04),
    rgb(255 255 255 / 0.01)
  ),
  hsl(var(--card));
  transition: border-color 0.18s ease;
}

.fileStatusCompleted {
  border-color: hsl(var(--success) / 0.3);
}

.fileStatusFailed {
  border-color: hsl(var(--destructive) / 0.3);
}

/* ── Icon column ─────────────────────────────────────────── */

.fileStatusIcon {
  flex-shrink: 0;
  margin-top: 0.1rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.spinner {
  color: hsl(var(--warning));
  animation: spin 0.9s linear infinite;
  transform-origin: center;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.iconSuccess {
  color: hsl(var(--success));
}

.iconFailed {
  color: hsl(var(--destructive));
}

/* ── Body ────────────────────────────────────────────────── */

.fileStatusBody {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: var(--space-2);
}

.fileStatusHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.fileStatusName {
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  min-width: 0;
}

/* ── Count chips ─────────────────────────────────────────── */

.fileStatusCounts {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.countChip {
  display: inline-flex;
  align-items: baseline;
  gap: 0.3rem;
  font-size: 0.82rem;
}

.countValue {
  font-weight: 800;
  font-size: 0.9rem;
  letter-spacing: -0.02em;
}

.countLabel {
  color: hsl(var(--muted-foreground));
}

.countChipNew .countValue {
  color: hsl(var(--success));
}

.countChipDup .countValue {
  color: hsl(var(--muted-foreground));
}

.countDivider {
  width: 1px;
  height: 0.9rem;
  background: hsl(var(--border));
  display: inline-block;
}

/* ── Hints / errors ──────────────────────────────────────── */

.fileStatusHint {
  margin: 0;
}

.fileStatusError {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
}
</style>
