<script setup lang="ts">
import Badge from '../ui/Badge.vue'
import Button from '../ui/Button.vue'
import type { FixedExpenseItem } from '../../lib/api'

const props = defineProps<{ expense: FixedExpenseItem }>()
const emit = defineEmits<{
  (e: 'edit'): void
  (e: 'delete'): void
  (e: 'toggle-entries'): void
}>()

const FREQUENCY_LABELS: Record<string, string> = {
  weekly: 'Weekly',
  biweekly: 'Every 2 weeks',
  monthly: 'Monthly',
  bimonthly: 'Every 2 months',
  quarterly: 'Quarterly',
  semiannual: 'Semiannual',
  annual: 'Annual',
}

function formatBRL(amount: string) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(amount))
}
</script>

<template>
  <tr>
    <td>
      <span class="truncate" style="max-width: 200px; display: inline-block;">{{ expense.name }}</span>
    </td>
    <td>{{ formatBRL(expense.amount) }}</td>
    <td>{{ FREQUENCY_LABELS[expense.frequency] ?? expense.frequency }}</td>
    <td>{{ expense.account_name }}</td>
    <td>
      <span v-if="expense.category_name" class="badge">{{ expense.category_name }}</span>
      <span v-else class="dim">—</span>
    </td>
    <td>
      <Badge :variant="expense.is_active ? 'success' : 'default'">
        {{ expense.is_active ? 'Active' : 'Inactive' }}
      </Badge>
    </td>
    <td class="tableActions">
      <Button size="icon" variant="ghost" title="View entries" @click="emit('toggle-entries')">📋</Button>
      <Button size="icon" variant="ghost" title="Edit" @click="emit('edit')">✏️</Button>
      <Button size="icon" variant="destructive" title="Deactivate" @click="emit('delete')">🗑</Button>
    </td>
  </tr>
</template>
