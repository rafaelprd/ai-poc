<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { Category, AccountItem } from '../../lib/api'
import { type TransactionFilters as FilterState } from '../../composables/useTransactions'
import DateRangePicker from '../common/dateRangePicker.vue'
import CategorySelect from '../common/categorySelect.vue'
import AccountSelect from '../common/accountSelect.vue'
import SearchInput from '../common/searchInput.vue'

export type { FilterState }

const props = defineProps<{
  currentFilters: FilterState
  categories: Category[]
  accounts: AccountItem[]
}>()

const emit = defineEmits<{
  (e: 'update:filters', v: FilterState): void
}>()

const local = reactive<FilterState>({ ...props.currentFilters })

watch(() => props.currentFilters, (v) => Object.assign(local, v), { deep: true })

function emitUpdate() {
  emit('update:filters', { ...local })
}

function clearAll() {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  local.dateFrom = `${y}-${m}-01`
  local.dateTo = `${y}-${m}-${String(new Date(y, now.getMonth() + 1, 0).getDate()).padStart(2, '0')}`
  local.categoryId = null
  local.accountId = null
  local.search = ''
  local.sortBy = 'date'
  local.sortOrder = 'desc'
  emitUpdate()
}
</script>

<template>
  <div class="stack">
    <DateRangePicker
      :date-from="local.dateFrom"
      :date-to="local.dateTo"
      @update:date-from="local.dateFrom = $event"
      @update:date-to="local.dateTo = $event"
    />

    <div class="grid3">
      <label class="field">
        <span class="fieldLabel">Category</span>
        <CategorySelect
          :model-value="local.categoryId"
          :categories="categories"
          :allow-null="true"
          placeholder="All categories"
          @update:model-value="local.categoryId = $event"
        />
      </label>

      <label class="field">
        <span class="fieldLabel">Account</span>
        <AccountSelect
          :model-value="local.accountId"
          :accounts="accounts"
          @update:model-value="local.accountId = $event"
        />
      </label>

      <label class="field">
        <span class="fieldLabel">Search</span>
        <SearchInput
          :model-value="local.search"
          @update:model-value="local.search = $event"
        />
      </label>
    </div>

    <div class="grid2">
      <label class="field">
        <span class="fieldLabel">Sort by</span>
        <select class="select" v-model="local.sortBy">
          <option value="date">Date</option>
          <option value="amount">Amount</option>
          <option value="description">Description</option>
        </select>
      </label>
      <label class="field">
        <span class="fieldLabel">Order</span>
        <select class="select" v-model="local.sortOrder">
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>
      </label>
    </div>

    <div class="row">
      <button class="button buttonPrimary buttonCompact" type="button" @click="emitUpdate">
        Apply filters
      </button>
      <button class="button buttonGhost buttonCompact" type="button" @click="clearAll">
        Reset
      </button>
    </div>
  </div>
</template>
