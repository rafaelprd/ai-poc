<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listAccounts } from '../lib/api'
import importUploader from '../components/import/importUploader.vue'
import importHistory from '../components/import/importHistory.vue'

// ── Account selector ──────────────────────────────────────────────────────────

interface AccountOption {
  id: string
  name: string
}

const accounts = ref<AccountOption[]>([])
const selectedAccountId = ref<string>('')
const accountsLoading = ref(false)
const accountsError = ref<string | null>(null)

async function fetchAccounts(): Promise<void> {
  accountsLoading.value = true
  accountsError.value = null
  try {
    const result = await listAccounts()
    accounts.value = (result.accounts ?? []).map((a: { id: string; name: string }) => ({
      id: a.id,
      name: a.name,
    }))
    if (accounts.value.length > 0 && !selectedAccountId.value) {
      selectedAccountId.value = accounts.value[0].id
    }
  } catch (err) {
    accountsError.value = err instanceof Error ? err.message : 'Failed to load accounts.'
  } finally {
    accountsLoading.value = false
  }
}

// ── Import events ─────────────────────────────────────────────────────────────

const historyKey = ref(0)

function onImportCreated(_importId: number): void {
  // When an import finishes and progress tracker emits importFinished,
  // refresh history via key bump (handled inside importUploader → importProgressTracker)
  // We listen here to proactively increment when an import is created.
}

function refreshHistory(): void {
  historyKey.value += 1
}

// ── Init ──────────────────────────────────────────────────────────────────────

onMounted(() => {
  fetchAccounts()
})
</script>

<template>
  <div class="importPageRoot">

    <!-- ── Account selector row ─────────────────────────────────────────────── -->
    <div class="accountSelectorWrap">
      <label class="field accountField">
        <span class="fieldLabel">Target account</span>
        <select
          v-model="selectedAccountId"
          class="accountSelect"
          :disabled="accountsLoading"
          aria-label="Select target account"
        >
          <option value="" disabled>
            {{ accountsLoading ? 'Loading accounts…' : '— select an account —' }}
          </option>
          <option
            v-for="account in accounts"
            :key="account.id"
            :value="account.id"
          >
            {{ account.name }}
          </option>
        </select>
      </label>

      <p v-if="accountsError" class="errorText accountError">
        {{ accountsError }}
      </p>

      <p v-if="!accountsLoading && accounts.length === 0 && !accountsError" class="helperText">
        No accounts found. Create an account via the Ingestion or Transactions section first.
      </p>
    </div>

    <!-- ── Two-column layout: uploader + history ────────────────────────────── -->
    <div class="importPageGrid">

      <!-- Left: uploader -->
      <div class="importPageCol">
        <div v-if="!selectedAccountId" class="emptyState">
          <p class="emptyStateTitle">No account selected</p>
          <p class="emptyStateText">Choose a target account above to start uploading files.</p>
        </div>

        <importUploader
          v-else
          :account-id="selectedAccountId"
          @import-created="onImportCreated"
        />
      </div>

      <!-- Right: history -->
      <div class="importPageCol">
        <importHistory :key="historyKey" />

        <!-- Refresh history after an upload completes -->
        <button
          v-if="false"
          aria-hidden="true"
          style="display:none"
          @click="refreshHistory"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── Root ────────────────────────────────────────────────── */
.importPageRoot {
  display: grid;
  gap: var(--space-6, 1.5rem);
}

/* ── Account selector ────────────────────────────────────── */
.accountSelectorWrap {
  display: grid;
  gap: var(--space-2, 0.5rem);
}

.accountField {
  display: grid;
  gap: var(--space-1, 0.25rem);
  max-width: 28rem;
}

.accountSelect {
  width: 100%;
  height: 2.25rem;
  padding: 0 0.625rem;
  border-radius: var(--radius, 0.375rem);
  border: 1px solid hsl(var(--border, 220 13% 22%));
  background: hsl(var(--input, 220 13% 14%));
  color: hsl(var(--foreground, 210 40% 98%));
  font-size: 0.875rem;
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.accountSelect:focus {
  border-color: hsl(var(--ring, 217 91% 60%));
  box-shadow: 0 0 0 2px hsl(var(--ring, 217 91% 60%) / 0.25);
}

.accountSelect:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.accountError {
  max-width: 28rem;
}

/* ── Two-column grid ─────────────────────────────────────── */
.importPageGrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-6, 1.5rem);
  align-items: start;
}

.importPageCol {
  display: grid;
  gap: var(--space-5, 1.25rem);
  min-width: 0;
}

/* ── Responsive: stack on narrow viewports ───────────────── */
@media (max-width: 900px) {
  .importPageGrid {
    grid-template-columns: 1fr;
  }
}
</style>
