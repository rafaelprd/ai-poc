<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  ApiError,
  categorizeBulkTransactions,
  categorizeTransaction,
  listCategories,
  listTransactions,
  runCategorization,
  type Category,
  type CategorizationRunResponse,
  type TransactionItem,
} from '../lib/api'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import Input from './ui/Input.vue'
import Select from './ui/Select.vue'

const categories = ref<Category[]>([])
const transactions = ref<TransactionItem[]>([])
const loadingCategories = ref(false)
const loadingTransactions = ref(false)
const savingTransactionId = ref<number | null>(null)
const applyingBulk = ref(false)
const runningCategorization = ref(false)

const flashType = ref<'success' | 'error' | null>(null)
const flashMessage = ref<string | null>(null)

const pagination = reactive({
  page: 1,
  page_size: 50,
  total_items: 0,
  total_pages: 1,
})

const filters = reactive({
  search: '',
  dateFrom: '',
  dateTo: '',
  categoryId: '',
  accountId: '',
  sortBy: 'date',
  sortOrder: 'desc' as 'asc' | 'desc',
})

const runScope = ref<'uncategorized' | 'all'>('uncategorized')
const runAccountId = ref('')
const runSummary = ref<CategorizationRunResponse | null>(null)

const bulkCategoryId = ref('')
const bulkLearnRule = ref(false)
const selectedIds = ref<number[]>([])
const rowLearnRule = reactive<Record<number, boolean>>({})

const allSelected = computed(() => {
  if (transactions.value.length === 0) return false
  return transactions.value.every((tx) => selectedIds.value.includes(tx.id))
})

const flashClass = computed(() =>
  flashType.value === 'error' ? 'pillDanger' : 'pillSuccess',
)

const flashTitle = computed(() =>
  flashType.value === 'error' ? 'Operation failed' : 'Operation complete',
)

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.code}: ${error.message}`
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Unknown error.'
}

function showFlash(type: 'success' | 'error', message: string): void {
  flashType.value = type
  flashMessage.value = message
  window.setTimeout(() => {
    if (flashMessage.value === message) {
      flashMessage.value = null
      flashType.value = null
    }
  }, 4000)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 2,
  }).format(value)
}

function formatDate(value: string): string {
  return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR')
}

function badgeVariantForSource(source?: string | null): 'default' | 'secondary' | 'success' | 'warning' | 'destructive' {
  switch (source) {
    case 'auto':
      return 'success'
    case 'manual':
      return 'warning'
    case 'bulk':
      return 'secondary'
    default:
      return 'default'
  }
}

function badgeVariantForStatus(status?: string | null): 'default' | 'secondary' | 'success' | 'warning' | 'destructive' {
  switch (status) {
    case 'completed':
      return 'success'
    case 'processing':
      return 'warning'
    case 'failed':
      return 'destructive'
    default:
      return 'secondary'
  }
}

function categoryColor(categoryId: number | null): string {
  if (categoryId === null) return '#94a3b8'
  const category = categories.value.find((item) => item.id === categoryId)
  return category?.color ?? '#94a3b8'
}

async function loadCategories(): Promise<void> {
  loadingCategories.value = true
  try {
    const response = await listCategories(true)
    categories.value = response.data
  } catch (error) {
    showFlash('error', formatError(error))
  } finally {
    loadingCategories.value = false
  }
}

function normalizeCategoryFilter(value: string): number | null {
  if (value === '') return null
  return Number(value)
}

async function loadTransactions(): Promise<void> {
  loadingTransactions.value = true
  try {
    const response = await listTransactions({
      page: pagination.page,
      pageSize: pagination.page_size,
      dateFrom: filters.dateFrom || null,
      dateTo: filters.dateTo || null,
      categoryId: filters.categoryId === '' ? null : normalizeCategoryFilter(filters.categoryId),
      accountId: filters.accountId || null,
      search: filters.search || null,
      sortBy: filters.sortBy,
      sortOrder: filters.sortOrder,
    })

    transactions.value = response.items
    pagination.page = response.pagination.page
    pagination.page_size = response.pagination.page_size
    pagination.total_items = response.pagination.total_items
    pagination.total_pages = response.pagination.total_pages

    const loadedIds = new Set(response.items.map((item) => item.id))
    selectedIds.value = selectedIds.value.filter((id) => loadedIds.has(id))

    response.items.forEach((tx) => {
      if (!(tx.id in rowLearnRule)) {
        rowLearnRule[tx.id] = true
      }
    })
  } catch (error) {
    showFlash('error', formatError(error))
  } finally {
    loadingTransactions.value = false
  }
}

async function applyFilters(): Promise<void> {
  pagination.page = 1
  await loadTransactions()
}

async function clearFilters(): Promise<void> {
  filters.search = ''
  filters.dateFrom = ''
  filters.dateTo = ''
  filters.categoryId = ''
  filters.accountId = ''
  filters.sortBy = 'date'
  filters.sortOrder = 'desc'
  pagination.page = 1
  await loadTransactions()
}

async function goToPage(page: number): Promise<void> {
  if (page < 1 || page > pagination.total_pages) return
  pagination.page = page
  await loadTransactions()
}

function toggleOne(transactionId: number, checked: boolean): void {
  if (checked) {
    if (!selectedIds.value.includes(transactionId)) {
      selectedIds.value = [...selectedIds.value, transactionId]
    }
    return
  }

  selectedIds.value = selectedIds.value.filter((id) => id !== transactionId)
}

function toggleAll(checked: boolean): void {
  if (checked) {
    selectedIds.value = transactions.value.map((item) => item.id)
    return
  }

  selectedIds.value = []
}

function clearSelection(): void {
  selectedIds.value = []
}

function handleSelectAllChange(event: Event): void {
  const target = event.target as HTMLInputElement
  toggleAll(target.checked)
}

function handleSelectOneChange(transactionId: number, event: Event): void {
  const target = event.target as HTMLInputElement
  toggleOne(transactionId, target.checked)
}

async function updateTransactionCategory(
  transaction: TransactionItem,
  event: Event,
): Promise<void> {
  const target = event.target as HTMLSelectElement
  const value = target.value
  const categoryId = value === '' ? null : Number(value)
  const learnRule = rowLearnRule[transaction.id] ?? true

  savingTransactionId.value = transaction.id
  try {
    const response = await categorizeTransaction(transaction.id, categoryId, learnRule)
    showFlash(
      'success',
      response.learned_rule
        ? 'Category updated. Rule learned.'
        : 'Category updated.',
    )
    await loadTransactions()
    await loadCategories()
  } catch (error) {
    showFlash('error', formatError(error))
    await loadTransactions()
  } finally {
    savingTransactionId.value = null
  }
}

async function applyBulkCategory(): Promise<void> {
  if (selectedIds.value.length === 0) return

  const categoryId = bulkCategoryId.value === '' ? null : Number(bulkCategoryId.value)
  applyingBulk.value = true
  try {
    const response = await categorizeBulkTransactions(
      selectedIds.value,
      categoryId,
      bulkLearnRule.value,
    )
    showFlash(
      'success',
      `Bulk updated ${response.updated_count} transaction(s).`,
    )
    selectedIds.value = []
    await loadTransactions()
  } catch (error) {
    showFlash('error', formatError(error))
  } finally {
    applyingBulk.value = false
  }
}

async function runEngine(): Promise<void> {
  runningCategorization.value = true
  try {
    const response = await runCategorization({
      scope: runScope.value,
      accountId: runAccountId.value || null,
    })
    runSummary.value = response
    showFlash(
      'success',
      `Categorized ${response.categorized} of ${response.processed}.`,
    )
    await loadTransactions()
  } catch (error) {
    showFlash('error', formatError(error))
  } finally {
    runningCategorization.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadCategories(), loadTransactions()])
})
</script>

<template>
  <section class="sectionGrid sectionGridTwo">
    <Card as="section">
      <div class="panelHeader">
        <div>
          <h2 class="panelTitle">Transactions</h2>
          <p class="panelDescription">
            Filter, edit category, bulk apply, and re-run categorization.
          </p>
        </div>

        <div class="row">
          <Button variant="outline" size="sm" type="button" :disabled="loadingTransactions" @click="loadTransactions">
            Refresh
          </Button>
        </div>
      </div>

      <div class="panelBody stack">
        <div class="kpiRow">
          <div class="kpiCard">
            <p class="kpiValue">{{ pagination.total_items }}</p>
            <p class="kpiLabel">Transactions</p>
          </div>
          <div class="kpiCard">
            <p class="kpiValue">{{ pagination.total_pages }}</p>
            <p class="kpiLabel">Pages</p>
          </div>
          <div class="kpiCard">
            <p class="kpiValue">{{ selectedIds.length }}</p>
            <p class="kpiLabel">Selected</p>
          </div>
          <div class="kpiCard">
            <p class="kpiValue">{{ categories.length }}</p>
            <p class="kpiLabel">Categories</p>
          </div>
        </div>

        <div v-if="flashMessage" class="banner" :class="flashClass">
          <div>
            <p class="bannerTitle">{{ flashTitle }}</p>
            <p class="bannerText">{{ flashMessage }}</p>
          </div>
        </div>

        <div class="grid3">
          <label class="field">
            <span class="fieldLabel">Search</span>
            <Input
              v-model="filters.search"
              type="text"
              placeholder="SUPERMERCADO, UBER, SALÁRIO..."
            />
          </label>

          <label class="field">
            <span class="fieldLabel">Date from</span>
            <Input v-model="filters.dateFrom" type="date" />
          </label>

          <label class="field">
            <span class="fieldLabel">Date to</span>
            <Input v-model="filters.dateTo" type="date" />
          </label>

          <label class="field">
            <span class="fieldLabel">Category filter</span>
            <Select v-model="filters.categoryId">
              <option value="">All categories</option>
              <option value="0">Uncategorized</option>
              <option
                v-for="category in categories"
                :key="category.id"
                :value="String(category.id)"
              >
                {{ category.name }}
              </option>
            </Select>
          </label>

          <label class="field">
            <span class="fieldLabel">Account ID</span>
            <Input
              v-model="filters.accountId"
              type="text"
              placeholder="Optional"
            />
          </label>

          <label class="field">
            <span class="fieldLabel">Sort</span>
            <div class="grid2">
              <Select v-model="filters.sortBy">
                <option value="date">Date</option>
                <option value="amount">Amount</option>
                <option value="description">Description</option>
              </Select>
              <Select v-model="filters.sortOrder">
                <option value="desc">Desc</option>
                <option value="asc">Asc</option>
              </Select>
            </div>
          </label>
        </div>

        <div class="row">
          <Button type="button" @click="applyFilters">
            Apply filters
          </Button>
          <Button variant="outline" type="button" :disabled="loadingTransactions" @click="clearFilters">
            Clear
          </Button>
        </div>

        <div v-if="loadingTransactions" class="emptyState">
          <p class="emptyStateTitle">Loading transactions...</p>
          <p class="emptyStateText">Batch fetch in progress.</p>
        </div>

        <div v-else-if="transactions.length === 0" class="emptyState">
          <p class="emptyStateTitle">No transactions found</p>
          <p class="emptyStateText">Change filters or import more files.</p>
        </div>

        <div v-else class="tableWrap">
          <table class="table tableCompact">
            <thead>
              <tr>
                <th style="width: 44px">
                  <label class="checkboxRow">
                    <input
                      type="checkbox"
                      :checked="allSelected"
                      @change="handleSelectAllChange"
                    />
                  </label>
                </th>
                <th>Date</th>
                <th>Description</th>
                <th class="right">Amount</th>
                <th>Category</th>
                <th>Change</th>
                <th>Learn</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="tx in transactions" :key="tx.id">
                <td>
                  <label class="checkboxRow">
                    <input
                      type="checkbox"
                      :checked="selectedIds.includes(tx.id)"
                      @change="handleSelectOneChange(tx.id, $event)"
                    />
                  </label>
                </td>
                <td class="codeLike">{{ formatDate(tx.date) }}</td>
                <td class="wrap">
                  <div class="stackSm">
                    <strong>{{ tx.description }}</strong>
                    <span class="muted small codeLike">#{{ tx.id }}</span>
                  </div>
                </td>
                <td class="right codeLike">
                  <span :class="tx.amount < 0 ? 'errorText' : 'successText'">
                    {{ formatCurrency(tx.amount) }}
                  </span>
                </td>
                <td>
                  <Badge v-if="tx.category_name" variant="default">
                    <span class="dot" :style="{ backgroundColor: categoryColor(tx.category_id) }" />
                    {{ tx.category_name }}
                  </Badge>
                  <Badge v-else variant="secondary">
                    Uncategorized
                  </Badge>
                </td>
                <td>
                  <Select
                    class="inputSmall"
                    :disabled="savingTransactionId === tx.id"
                    :model-value="tx.category_id === null ? '' : String(tx.category_id)"
                    @change="updateTransactionCategory(tx, $event)"
                  >
                    <option value="">Uncategorized</option>
                    <option
                      v-for="category in categories"
                      :key="category.id"
                      :value="String(category.id)"
                    >
                      {{ category.name }}
                    </option>
                  </Select>
                </td>
                <td>
                  <label class="checkboxRow small">
                    <input
                      v-model="rowLearnRule[tx.id]"
                      type="checkbox"
                    />
                    Learn rule
                  </label>
                </td>
                <td>
                  <Badge :variant="badgeVariantForSource(tx.categorization_source)">
                    {{ tx.categorization_source ?? 'none' }}
                  </Badge>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="rowBetween">
          <p class="helperText">
            Page {{ pagination.page }} / {{ pagination.total_pages }} ·
            {{ pagination.total_items }} total
          </p>

          <div class="row">
            <Button
              variant="outline"
              size="sm"
              type="button"
              :disabled="pagination.page <= 1 || loadingTransactions"
              @click="goToPage(pagination.page - 1)"
            >
              Prev
            </Button>
            <Button
              variant="outline"
              size="sm"
              type="button"
              :disabled="pagination.page >= pagination.total_pages || loadingTransactions"
              @click="goToPage(pagination.page + 1)"
            >
              Next
            </Button>
          </div>
        </div>
      </div>
    </Card>

    <Card as="aside">
      <div class="panelHeader">
        <div>
          <h2 class="panelTitle">Auto categorize</h2>
          <p class="panelDescription">
            Run engine for uncategorized rows or whole set.
          </p>
        </div>
      </div>

      <div class="panelBody stack">
        <div class="grid2">
          <label class="field">
            <span class="fieldLabel">Scope</span>
            <Select v-model="runScope">
              <option value="uncategorized">Uncategorized only</option>
              <option value="all">All transactions</option>
            </Select>
          </label>

          <label class="field">
            <span class="fieldLabel">Account ID</span>
            <Input
              v-model="runAccountId"
              type="text"
              placeholder="Optional"
            />
          </label>
        </div>

        <div class="row">
          <Button
            type="button"
            :disabled="runningCategorization"
            @click="runEngine"
          >
            {{ runningCategorization ? 'Running...' : 'Run categorization' }}
          </Button>
          <span class="helperText">
            Manual overrides stay safe on full run.
          </span>
        </div>

        <div v-if="runSummary" class="banner">
          <div>
            <p class="bannerTitle">Run complete</p>
            <p class="bannerText">
              Processed {{ runSummary.processed }}, categorized
              {{ runSummary.categorized }}, uncategorized
              {{ runSummary.uncategorized }}, in
              {{ runSummary.duration_ms }} ms.
            </p>
          </div>
        </div>

        <div class="divider" />

        <h3 class="panelTitle">Bulk apply</h3>

        <div class="grid2">
          <label class="field">
            <span class="fieldLabel">Category</span>
            <Select v-model="bulkCategoryId">
              <option value="">Uncategorized</option>
              <option
                v-for="category in categories"
                :key="category.id"
                :value="String(category.id)"
              >
                {{ category.name }}
              </option>
            </Select>
          </label>

          <label class="field">
            <span class="fieldLabel">Learn rule</span>
            <label class="checkboxRow">
              <input v-model="bulkLearnRule" type="checkbox" />
              Learn future matches
            </label>
          </label>
        </div>

        <div class="row">
          <Button
            type="button"
            :disabled="selectedIds.length === 0 || applyingBulk"
            @click="applyBulkCategory"
          >
            {{ applyingBulk ? 'Applying...' : `Apply to ${selectedIds.length}` }}
          </Button>
          <Button
            variant="outline"
            type="button"
            :disabled="selectedIds.length === 0"
            @click="clearSelection"
          >
            Clear selection
          </Button>
        </div>

        <div class="banner">
          <div>
            <p class="bannerTitle">Selected rows</p>
            <p class="bannerText">
              {{ selectedIds.length }} transaction(s) picked for bulk edit.
            </p>
          </div>
        </div>
      </div>
    </Card>

    <div
      v-if="selectedIds.length > 0"
      class="bulkBar"
      role="region"
      aria-label="Bulk categorize bar"
    >
      <div>
        <strong>{{ selectedIds.length }} selected</strong>
        <p class="muted small">
          Bulk apply uses `POST /api/v1/transactions/categorize-bulk`.
        </p>
      </div>

      <div class="row">
        <Select v-model="bulkCategoryId">
          <option value="">Uncategorized</option>
          <option
            v-for="category in categories"
            :key="category.id"
            :value="String(category.id)"
          >
            {{ category.name }}
          </option>
        </Select>

        <label class="checkboxRow">
          <input v-model="bulkLearnRule" type="checkbox" />
          Learn rule
        </label>

        <Button
          type="button"
          :disabled="applyingBulk"
          @click="applyBulkCategory"
        >
          {{ applyingBulk ? 'Applying...' : 'Apply' }}
        </Button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel {
  min-width: 0;
}
</style>
