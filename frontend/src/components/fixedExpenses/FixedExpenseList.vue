<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useFixedExpenses } from '../../composables/useFixedExpenses'
import FixedExpenseListItem from './FixedExpenseListItem.vue'
import FixedExpenseEntries from './FixedExpenseEntries.vue'
import FixedExpenseForm from './FixedExpenseForm.vue'
import FixedExpenseGenerateButton from './FixedExpenseGenerateButton.vue'
import Button from '../ui/Button.vue'
import type { FixedExpenseItem, AccountItem, Category } from '../../lib/api'

const props = defineProps<{
  accounts: AccountItem[]
  categories: Category[]
}>()

const emit = defineEmits<{
  (e: 'toast', payload: { type: 'success' | 'error'; title: string; body: string }): void
}>()

const { expenses, isLoading, error, total, totalPages, currentPage, fetchExpenses, removeExpense } = useFixedExpenses()

const filterAccountId = ref<string>('')
const filterIsActive = ref<string>('true')
const page = ref(1)
const pageSize = ref(20)

const expandedId = ref<string | null>(null)
const showForm = ref(false)
const editingExpense = ref<FixedExpenseItem | null>(null)

async function load() {
  await fetchExpenses({
    account_id: filterAccountId.value || null,
    is_active: filterIsActive.value === '' ? undefined : filterIsActive.value === 'true',
    page: page.value,
    page_size: pageSize.value,
  })
}

onMounted(load)
watch([filterAccountId, filterIsActive], () => { page.value = 1; load() })

function onToggleEntries(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function onEdit(expense: FixedExpenseItem) {
  editingExpense.value = expense
  showForm.value = true
}

function onNew() {
  editingExpense.value = null
  showForm.value = true
}

async function onDelete(expense: FixedExpenseItem) {
  if (!confirm(`Deactivate "${expense.name}"? This will soft-delete the expense.`)) return
  const ok = await removeExpense(expense.id)
  if (ok) {
    emit('toast', { type: 'success', title: 'Deactivated', body: `"${expense.name}" has been deactivated.` })
    await load()
  } else {
    emit('toast', { type: 'error', title: 'Error', body: error.value ?? 'Failed to deactivate.' })
  }
}

function onSaved(expense: FixedExpenseItem) {
  showForm.value = false
  editingExpense.value = null
  emit('toast', { type: 'success', title: 'Saved', body: `"${expense.name}" saved successfully.` })
  load()
}

function onGenerated() {
  if (expandedId.value) {
    // force re-render of entries by toggling
    const id = expandedId.value
    expandedId.value = null
    setTimeout(() => { expandedId.value = id }, 50)
  }
}
</script>

<template>
  <div class="stack">
    <!-- Toolbar -->
    <div class="rowBetween" style="flex-wrap: wrap; gap: 8px;">
      <div class="row" style="gap: 8px; flex-wrap: wrap;">
        <select class="select inputSmall" v-model="filterAccountId">
          <option value="">All accounts</option>
          <option v-for="acc in accounts" :key="String(acc.id)" :value="String(acc.id)">{{ acc.name }}</option>
        </select>
        <select class="select inputSmall" v-model="filterIsActive">
          <option value="true">Active</option>
          <option value="false">Inactive</option>
          <option value="">All</option>
        </select>
      </div>
      <div class="row" style="gap: 8px;">
        <FixedExpenseGenerateButton @generated="onGenerated" />
        <Button size="sm" @click="onNew">+ New Expense</Button>
      </div>
    </div>

    <!-- Loading / Error / Empty -->
    <div v-if="isLoading" class="muted small">Loading…</div>
    <div v-else-if="error" class="errorText small">{{ error }}</div>
    <div v-else-if="expenses.length === 0" class="emptyState">
      <p class="emptyStateTitle">No fixed expenses yet</p>
      <p class="emptyStateText">Click "+ New Expense" to create your first recurring expense.</p>
    </div>

    <!-- Table -->
    <div v-else class="tableWrap">
      <table class="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Amount</th>
            <th>Frequency</th>
            <th>Account</th>
            <th>Category</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="expense in expenses" :key="expense.id">
            <FixedExpenseListItem
              :expense="expense"
              @toggle-entries="onToggleEntries(expense.id)"
              @edit="onEdit(expense)"
              @delete="onDelete(expense)"
            />
            <tr v-if="expandedId === expense.id">
              <td colspan="7" style="padding: 16px; background: var(--surface-2, #f9fafb);">
                <FixedExpenseEntries :fixed-expense-id="expense.id" />
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="row" style="gap: 8px; justify-content: center;">
      <button class="button buttonGhost buttonCompact" :disabled="page <= 1" @click="page--; load()">‹ Prev</button>
      <span class="muted small">{{ page }} / {{ totalPages }} ({{ total }} total)</span>
      <button class="button buttonGhost buttonCompact" :disabled="page >= totalPages" @click="page++; load()">Next ›</button>
    </div>

    <!-- Form Modal -->
    <FixedExpenseForm
      v-if="showForm"
      :expense="editingExpense"
      :accounts="accounts"
      :categories="categories"
      @saved="onSaved"
      @cancelled="showForm = false; editingExpense = null"
    />
  </div>
</template>
