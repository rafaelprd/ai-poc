<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useFixedExpenses } from '../../composables/useFixedExpenses'
import FixedExpenseEntryRow from './FixedExpenseEntryRow.vue'
import type { FixedExpenseEntryItem, FixedExpenseEntryStatus } from '../../lib/api'

const props = defineProps<{ fixedExpenseId: string }>()

const { fetchEntries, updateEntryStatus, error } = useFixedExpenses()

const entries = ref<FixedExpenseEntryItem[]>([])
const total = ref(0)
const loading = ref(false)
const statusFilter = ref('')
const fromDate = ref('')
const toDate = ref('')
const page = ref(1)
const totalPages = ref(1)

async function load() {
  loading.value = true
  const res = await fetchEntries(props.fixedExpenseId, {
    status: statusFilter.value || null,
    from_date: fromDate.value || null,
    to_date: toDate.value || null,
    page: page.value,
  })
  if (res) {
    entries.value = res.items
    total.value = res.total
    totalPages.value = res.totalPages
  }
  loading.value = false
}

onMounted(load)
watch([statusFilter, fromDate, toDate], () => { page.value = 1; load() })

async function onStatusChanged(payload: { entryId: string; newStatus: FixedExpenseEntryStatus }) {
  await updateEntryStatus(payload.entryId, payload.newStatus)
  await load()
}
</script>

<template>
  <div class="stack">
    <div class="row" style="gap: 8px; flex-wrap: wrap;">
      <select class="select inputSmall" v-model="statusFilter">
        <option value="">All statuses</option>
        <option value="pending">Pending</option>
        <option value="paid">Paid</option>
        <option value="skipped">Skipped</option>
        <option value="cancelled">Cancelled</option>
      </select>
      <input class="input inputSmall" type="date" v-model="fromDate" placeholder="From date" />
      <input class="input inputSmall" type="date" v-model="toDate" placeholder="To date" />
    </div>

    <div v-if="loading" class="muted small">Loading entries…</div>
    <div v-else-if="error" class="errorText small">{{ error }}</div>
    <div v-else-if="entries.length === 0" class="emptyState">
      <p class="emptyStateTitle">No entries found</p>
      <p class="emptyStateText">Generate entries using the button above.</p>
    </div>
    <div v-else class="tableWrap">
      <table class="table tableCompact">
        <thead>
          <tr>
            <th>Due Date</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Change Status</th>
            <th>Transaction</th>
          </tr>
        </thead>
        <tbody>
          <FixedExpenseEntryRow
            v-for="entry in entries"
            :key="entry.id"
            :entry="entry"
            @status-changed="onStatusChanged"
          />
        </tbody>
      </table>
    </div>

    <div v-if="totalPages > 1" class="row" style="gap: 8px; justify-content: center;">
      <button class="button buttonGhost buttonCompact" :disabled="page <= 1" @click="page--; load()">‹ Prev</button>
      <span class="muted small">{{ page }} / {{ totalPages }}</span>
      <button class="button buttonGhost buttonCompact" :disabled="page >= totalPages" @click="page++; load()">Next ›</button>
    </div>
  </div>
</template>
