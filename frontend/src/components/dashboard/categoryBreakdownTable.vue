<script setup lang="ts">
import { computed, ref } from 'vue'

type CategorySummaryRow = {
  category_id: number | null
  category_name: string
  total: number
  percentage: number
  transaction_count: number
  color?: string
}

const props = defineProps<{
  categories: CategorySummaryRow[]
  ariaLabel?: string
}>()

const emit = defineEmits<{
  (e: 'row-click', row: CategorySummaryRow): void
}>()

type SortKey = 'category_name' | 'total' | 'percentage' | 'transaction_count'
type SortDir = 'asc' | 'desc'

const sortBy = ref<SortKey>('total')
const sortDir = ref<SortDir>('desc')

function toggleSort(key: SortKey) {
  if (sortBy.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortBy.value = key
  sortDir.value = 'desc'
}

function getSortIndicator(key: SortKey) {
  if (sortBy.value !== key) return ''
  return sortDir.value === 'asc' ? '▲' : '▼'
}

const sortedCategories = computed(() => {
  const rows = [...(props.categories ?? [])]
  const dir = sortDir.value === 'asc' ? 1 : -1

  rows.sort((a, b) => {
    const va = a?.[sortBy.value]
    const vb = b?.[sortBy.value]

    if (sortBy.value === 'category_name') {
      const sa = String(va ?? '').toLowerCase()
      const sb = String(vb ?? '').toLowerCase()
      return sa.localeCompare(sb) * dir
    }

    const na = typeof va === 'number' ? va : Number(va ?? 0)
    const nb = typeof vb === 'number' ? vb : Number(vb ?? 0)
    return (na - nb) * dir
  })

  return rows
})

const brl = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function formatMoney(v: number) {
  if (!Number.isFinite(v)) return '—'
  return brl.format(v)
}

function formatPct(v: number) {
  if (!Number.isFinite(v)) return '—'
  return `${v.toFixed(2)}%`
}

function dotColor(row: CategorySummaryRow) {
  const c = row.color ?? '#9E9E9E'
  return c || '#9E9E9E'
}
</script>

<template>
  <div class="tableWrap">
    <table
      class="table"
      role="table"
      :aria-label="ariaLabel ?? 'Tabela de categorias por valor'"
    >
      <thead>
        <tr>
          <th class="thDot" scope="col" aria-label="Categoria">
            <span class="dotHeader" aria-hidden="true" />
          </th>

          <th scope="col">
            <button
              class="thBtn"
              type="button"
              @click="toggleSort('category_name')"
              :aria-label="`Ordenar por categoria (${sortBy === 'category_name' ? sortDir : 'desc'})`"
            >
              <span>Categoria</span>
              <span class="sortIndicator" aria-hidden="true">{{ getSortIndicator('category_name') }}</span>
            </button>
          </th>

          <th scope="col" class="numCol">
            <button
              class="thBtn"
              type="button"
              @click="toggleSort('total')"
              :aria-label="`Ordenar por total (${sortBy === 'total' ? sortDir : 'desc'})`"
            >
              <span>Total</span>
              <span class="sortIndicator" aria-hidden="true">{{ getSortIndicator('total') }}</span>
            </button>
          </th>

          <th scope="col" class="numCol">
            <button
              class="thBtn"
              type="button"
              @click="toggleSort('percentage')"
              :aria-label="`Ordenar por percentual (${sortBy === 'percentage' ? sortDir : 'desc'})`"
            >
              <span>%</span>
              <span class="sortIndicator" aria-hidden="true">{{ getSortIndicator('percentage') }}</span>
            </button>
          </th>

          <th scope="col" class="numCol">
            <button
              class="thBtn"
              type="button"
              @click="toggleSort('transaction_count')"
              :aria-label="`Ordenar por quantidade de transações (${sortBy === 'transaction_count' ? sortDir : 'desc'})`"
            >
              <span>#</span>
              <span class="sortIndicator" aria-hidden="true">{{ getSortIndicator('transaction_count') }}</span>
            </button>
          </th>
        </tr>
      </thead>

      <tbody>
        <tr v-if="sortedCategories.length === 0">
          <td class="emptyCell" colspan="5">
            Nenhuma categoria encontrada.
          </td>
        </tr>

        <tr
          v-for="row in sortedCategories"
          :key="row.category_id ?? 'uncategorized'"
          class="row"
          role="row"
          @click="emit('row-click', row)"
        >
          <td class="thDot">
            <span class="dot" :style="{ backgroundColor: dotColor(row) }" aria-hidden="true" />
          </td>

          <td class="catCell">
            {{ row.category_name ?? 'Sem Categoria' }}
          </td>

          <td class="numCol">{{ formatMoney(row.total) }}</td>

          <td class="numCol">{{ formatPct(row.percentage) }}</td>

          <td class="numCol">{{ row.transaction_count ?? 0 }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.tableWrap {
  width: 100%;
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  min-width: 520px;
}

thead th {
  position: sticky;
  top: 0;
  background: rgb(255 255 255 / 0.92);
  z-index: 1;
  border-bottom: 1px solid hsl(var(--border));
  padding: 0.85rem 0.75rem;
  text-align: left;
  font-size: 0.92rem;
  color: hsl(var(--muted-foreground));
  font-weight: 750;
}

.thDot {
  width: 44px;
  padding-right: 0;
  padding-left: 0.65rem;
}

.dotHeader {
  display: inline-block;
  width: 12px;
  height: 12px;
}

.thBtn {
  appearance: none;
  background: transparent;
  border: none;
  padding: 0;
  margin: 0;
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0.55rem;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.sortIndicator {
  color: hsl(var(--muted-foreground));
  font-weight: 900;
  font-size: 0.85rem;
}

tbody td {
  padding: 0.85rem 0.75rem;
  border-bottom: 1px solid hsl(var(--border));
  font-size: 0.98rem;
  vertical-align: middle;
}

tbody tr.row {
  cursor: pointer;
  transition: background-color 120ms ease;
}

tbody tr.row:hover {
  background: hsl(var(--accent) / 0.10);
}

.numCol {
  text-align: right;
  white-space: nowrap;
}

.catCell {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 360px;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  display: inline-block;
  box-shadow: 0 0 0 2px rgb(255 255 255 / 0.85);
}

.emptyCell {
  text-align: center;
  padding: 1.25rem 0.75rem;
  color: hsl(var(--muted-foreground));
  border-bottom: 1px solid hsl(var(--border));
}
</style>
