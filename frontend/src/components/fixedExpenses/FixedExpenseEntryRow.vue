<script setup lang="ts">
import { ref } from 'vue'
import Badge from '../ui/Badge.vue'
import type { FixedExpenseEntryItem, FixedExpenseEntryStatus } from '../../lib/api'

const props = defineProps<{ entry: FixedExpenseEntryItem }>()
const emit = defineEmits<{
  (e: 'status-changed', payload: { entryId: string; newStatus: FixedExpenseEntryStatus }): void
}>()

const statusVariant: Record<string, 'warning' | 'success' | 'default' | 'destructive'> = {
  pending: 'warning',
  paid: 'success',
  skipped: 'default',
  cancelled: 'destructive',
}

function formatDate(d: string) {
  const [y, m, day] = d.split('-')
  return `${day}/${m}/${y}`
}

function formatBRL(amount: string) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(amount))
}

const localStatus = ref<FixedExpenseEntryStatus>(props.entry.status)

function onStatusChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value as FixedExpenseEntryStatus
  localStatus.value = val
  emit('status-changed', { entryId: props.entry.id, newStatus: val })
}
</script>

<template>
  <tr>
    <td>{{ formatDate(entry.due_date) }}</td>
    <td>{{ formatBRL(entry.amount) }}</td>
    <td>
      <Badge :variant="statusVariant[entry.status]">{{ entry.status }}</Badge>
    </td>
    <td>
      <select class="select inputSmall" :value="localStatus" @change="onStatusChange">
        <option value="pending">Pending</option>
        <option value="paid">Paid</option>
        <option value="skipped">Skipped</option>
        <option value="cancelled">Cancelled</option>
      </select>
    </td>
    <td>
      <span v-if="entry.transaction_id" class="muted small">#{{ entry.transaction_id }}</span>
      <span v-else class="dim">—</span>
    </td>
  </tr>
</template>
