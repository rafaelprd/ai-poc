<script setup lang="ts">
import { computed } from 'vue'
import type { Category, TransactionItem } from '../../lib/api'
import TransactionRow from './transactionRow.vue'

const props = defineProps<{
  transactions: readonly TransactionItem[]
  selectedIds: Set<number>
  loading: boolean
  sortBy: string
  sortOrder: 'asc' | 'desc'
  categories: Category[]
}>()

const emit = defineEmits<{
  (e: 'update:selectedIds', v: Set<number>): void
  (e: 'update:sortBy', v: string): void
  (e: 'update:sortOrder', v: 'asc' | 'desc'): void
  (e: 'category-updated', tx: TransactionItem): void
}>()

const allSelected = computed(() =>
  props.transactions.length > 0 &&
  props.transactions.every((t) => props.selectedIds.has(t.id))
)

function toggleAll(e: Event) {
  const checked = (e.target as HTMLInputElement).checked
  const next = new Set(props.selectedIds)
  if (checked) {
    props.transactions.forEach((t) => next.add(t.id))
  } else {
    props.transactions.forEach((t) => next.delete(t.id))
  }
  emit('update:selectedIds', next)
}

function toggleOne(id: number) {
  const next = new Set(props.selectedIds)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  emit('update:selectedIds', next)
}

function sortColumn(col: string) {
  if (props.sortBy === col) {
    emit('update:sortOrder', props.sortOrder === 'asc' ? 'desc' : 'asc')
  } else {
    emit('update:sortBy', col)
    emit('update:sortOrder', 'desc')
  }
}

function sortIcon(col: string): string {
  if (props.sortBy !== col) return '↕'
  return props.sortOrder === 'asc' ? '↑' : '↓'
}
</script>

<template>
  <div class="tableWrap">
    <div v-if="loading" class="emptyState">
      <p class="emptyStateTitle">Loading…</p>
    </div>

    <div v-else-if="transactions.length === 0" class="emptyState">
      <p class="emptyStateTitle">No transactions found</p>
      <p class="emptyStateText">Adjust filters or import more files.</p>
    </div>

    <table v-else class="table tableCompact">
      <thead>
        <tr>
          <th style="width: 44px;">
            <label class="checkboxRow">
              <input type="checkbox" :checked="allSelected" @change="toggleAll" />
            </label>
          </th>
          <th style="cursor: pointer; white-space: nowrap;" @click="sortColumn('date')">
            Date {{ sortIcon('date') }}
          </th>
          <th style="cursor: pointer;" @click="sortColumn('description')">
            Description {{ sortIcon('description') }}
          </th>
          <th class="right" style="cursor: pointer; white-space: nowrap;" @click="sortColumn('amount')">
            Amount {{ sortIcon('amount') }}
          </th>
          <th>Category</th>
          <th>Account</th>
        </tr>
      </thead>
      <tbody>
        <TransactionRow
          v-for="tx in transactions"
          :key="tx.id"
          :transaction="tx"
          :selected="selectedIds.has(tx.id)"
          :categories="categories"
          @toggle-select="toggleOne(tx.id)"
          @category-updated="emit('category-updated', $event)"
        />
      </tbody>
    </table>
  </div>
</template>
