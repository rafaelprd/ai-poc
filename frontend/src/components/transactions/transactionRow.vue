<script setup lang="ts">
import { ref } from 'vue'
import type { Category, TransactionItem } from '../../lib/api'
import CategoryInlineEditor from './categoryInlineEditor.vue'

const props = defineProps<{
  transaction: TransactionItem
  selected: boolean
  categories: Category[]
}>()

const emit = defineEmits<{
  (e: 'toggle-select'): void
  (e: 'category-updated', tx: TransactionItem): void
}>()

const editing = ref(false)

function formatDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR')
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 2,
  }).format(value)
}

function categoryColor(categoryId: number | null): string {
  if (categoryId === null) return '#94a3b8'
  const cat = props.categories.find((c) => c.id === categoryId)
  return cat?.color ?? '#94a3b8'
}

function onSaved(tx: TransactionItem) {
  editing.value = false
  emit('category-updated', tx)
}
</script>

<template>
  <tr>
    <td>
      <label class="checkboxRow">
        <input type="checkbox" :checked="selected" @change="emit('toggle-select')" />
      </label>
    </td>
    <td class="codeLike" style="white-space: nowrap;">{{ formatDate(transaction.date) }}</td>
    <td class="wrap" style="max-width: 280px;">
      <div class="stackSm">
        <span class="truncate">{{ transaction.description }}</span>
        <span class="muted small codeLike">#{{ transaction.id }}</span>
      </div>
    </td>
    <td class="right codeLike" style="white-space: nowrap;">
      <span :class="transaction.amount < 0 ? 'errorText' : 'successText'">
        {{ formatCurrency(transaction.amount) }}
      </span>
    </td>
    <td>
      <template v-if="!editing">
        <button
          class="chip"
          :style="{ borderColor: categoryColor(transaction.category_id), color: categoryColor(transaction.category_id) }"
          style="cursor: pointer; background: transparent;"
          @click="editing = true"
          :title="'Click to edit category'"
        >
          <span
            class="dot"
            :style="{ backgroundColor: categoryColor(transaction.category_id) }"
          />
          {{ transaction.category_name ?? 'Uncategorized' }}
        </button>
      </template>
      <template v-else>
        <CategoryInlineEditor
          :transaction-id="transaction.id"
          :current-category-id="transaction.category_id"
          :categories="categories"
          @saved="onSaved"
          @cancel="editing = false"
        />
      </template>
    </td>
    <td class="muted small" style="white-space: nowrap;">
      {{ transaction.account_name ?? transaction.account_id ?? '—' }}
    </td>
  </tr>
</template>
