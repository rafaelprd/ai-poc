<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  ApiError,
  type Category,
  type Rule,
  createCategory,
  createRule,
  deleteCategory,
  deleteRule,
  listCategories,
  listRules,
  runCategorization,
  updateCategory,
  updateRule,
} from '../lib/api'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import Input from './ui/Input.vue'
import Select from './ui/Select.vue'

type RuleFormMode = 'create' | 'edit'
type CategoryFormMode = 'create' | 'edit'

const categories = ref<Category[]>([])
const categoriesLoading = ref(false)
const categoriesError = ref<string | null>(null)

const rules = ref<Rule[]>([])
const rulesTotal = ref(0)
const rulesLoading = ref(false)
const rulesError = ref<string | null>(null)

const categoryFormMode = ref<CategoryFormMode>('create')
const categoryFormId = ref<number | null>(null)
const categoryForm = reactive({
  name: '',
  color: '#6B7280',
  icon: '',
})

const ruleFormMode = ref<RuleFormMode>('create')
const ruleFormId = ref<number | null>(null)
const ruleForm = reactive({
  keyword: '',
  categoryId: null as number | null,
  matchType: 'contains' as Rule['match_type'],
  priority: 50,
})

const ruleFilter = reactive({
  categoryId: null as number | null,
  source: '' as '' | Rule['source'],
  isActive: '' as '' | 'true' | 'false',
  search: '',
  page: 1,
  pageSize: 25,
  sortBy: 'priority',
  sortOrder: 'desc' as 'asc' | 'desc',
})

const runScope = ref<'uncategorized' | 'all'>('uncategorized')
const runAccountId = ref('')
const runBusy = ref(false)
const runSummary = ref<string | null>(null)
const runError = ref<string | null>(null)

const categoryNotice = ref<string | null>(null)
const ruleNotice = ref<string | null>(null)

const selectedCategoryLookup = computed(() => {
  return new Map(categories.value.map((category) => [category.id, category]))
})

const isEditingSystemCategory = computed(() => {
  if (categoryFormId.value === null) return false
  const category = selectedCategoryLookup.value.get(categoryFormId.value)
  return Boolean(category?.is_system)
})

const categoryOptions = computed(() => categories.value.slice())

const rulePageCount = computed(() => {
  if (!rulesTotal.value) return 1
  return Math.max(1, Math.ceil(rulesTotal.value / ruleFilter.pageSize))
})

const categoryCount = computed(() => categories.value.length)

const activeRuleCount = computed(() => rules.value.filter((rule) => rule.is_active).length)

function toMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return `${error.code}: ${error.message}`
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

function resetCategoryForm() {
  categoryFormMode.value = 'create'
  categoryFormId.value = null
  categoryForm.name = ''
  categoryForm.color = '#6B7280'
  categoryForm.icon = ''
}

function editCategory(category: Category) {
  categoryFormMode.value = 'edit'
  categoryFormId.value = category.id
  categoryForm.name = category.name
  categoryForm.color = category.color || '#6B7280'
  categoryForm.icon = category.icon ?? ''
}

function resetRuleForm() {
  ruleFormMode.value = 'create'
  ruleFormId.value = null
  ruleForm.keyword = ''
  ruleForm.categoryId = categories.value.find((category) => !category.is_system)?.id ?? null
  ruleForm.matchType = 'contains'
  ruleForm.priority = 50
}

function editRule(rule: Rule) {
  ruleFormMode.value = 'edit'
  ruleFormId.value = rule.id
  ruleForm.keyword = rule.keyword
  ruleForm.categoryId = rule.category_id
  ruleForm.matchType = rule.match_type
  ruleForm.priority = rule.priority
}

async function loadCategories() {
  categoriesLoading.value = true
  categoriesError.value = null

  try {
    const response = await listCategories(true)
    categories.value = response.data
    if (ruleForm.categoryId === null) {
      ruleForm.categoryId = categories.value.find((category) => !category.is_system)?.id ?? null
    }
  } catch (error) {
    categoriesError.value = toMessage(error, 'Load categories fail.')
  } finally {
    categoriesLoading.value = false
  }
}

async function loadRules() {
  rulesLoading.value = true
  rulesError.value = null

  try {
    const response = await listRules({
      categoryId: ruleFilter.categoryId,
      source: ruleFilter.source || null,
      isActive:
        ruleFilter.isActive === ''
          ? null
          : ruleFilter.isActive === 'true'
            ? true
            : false,
      search: ruleFilter.search || null,
      page: ruleFilter.page,
      pageSize: ruleFilter.pageSize,
      sortBy: ruleFilter.sortBy,
      sortOrder: ruleFilter.sortOrder,
    })

    rules.value = response.data
    rulesTotal.value = response.total
    ruleFilter.page = response.page
    ruleFilter.pageSize = response.page_size
  } catch (error) {
    rulesError.value = toMessage(error, 'Load rules fail.')
  } finally {
    rulesLoading.value = false
  }
}

async function saveCategory() {
  categoriesError.value = null
  categoryNotice.value = null

  const name = categoryForm.name.trim()
  const color = categoryForm.color.trim() || '#6B7280'
  const icon = categoryForm.icon.trim()

  try {
    if (categoryFormMode.value === 'create') {
      await createCategory({
        name,
        color,
        icon: icon || null,
      })
      categoryNotice.value = `Category "${name}" created.`
    } else if (categoryFormId.value !== null) {
      await updateCategory(categoryFormId.value, {
        name,
        color,
        icon: icon || null,
      })
      categoryNotice.value = `Category "${name}" updated.`
    }

    resetCategoryForm()
    await loadCategories()
    await loadRules()
  } catch (error) {
    categoryNotice.value = toMessage(error, 'Save category fail.')
  }
}

async function removeCategory(category: Category) {
  const promptText = category.is_system
    ? 'System category locked.'
    : `Delete category "${category.name}"?`

  if (category.is_system) {
    window.alert(promptText)
    return
  }

  if (!window.confirm(promptText)) return

  try {
    await deleteCategory(category.id)
    categoryNotice.value = `Category "${category.name}" deleted.`
    if (categoryFormId.value === category.id) {
      resetCategoryForm()
    }
    await loadCategories()
    await loadRules()
  } catch (error) {
    categoryNotice.value = toMessage(error, 'Delete category fail.')
  }
}

async function saveRule() {
  rulesError.value = null
  ruleNotice.value = null

  const keyword = ruleForm.keyword.trim()
  const categoryId = ruleForm.categoryId

  if (categoryId === null) {
    ruleNotice.value = 'Pick category first.'
    return
  }

  try {
    if (ruleFormMode.value === 'create') {
      await createRule({
        keyword,
        category_id: categoryId,
        match_type: ruleForm.matchType,
        priority: ruleForm.priority,
      })
      ruleNotice.value = `Rule "${keyword}" created.`
    } else if (ruleFormId.value !== null) {
      await updateRule(ruleFormId.value, {
        keyword,
        category_id: categoryId,
        match_type: ruleForm.matchType,
        priority: ruleForm.priority,
      })
      ruleNotice.value = `Rule "${keyword}" updated.`
    }

    resetRuleForm()
    await loadRules()
  } catch (error) {
    ruleNotice.value = toMessage(error, 'Save rule fail.')
  }
}

async function removeRule(rule: Rule) {
  if (!window.confirm(`Delete rule "${rule.keyword}"?`)) return

  try {
    await deleteRule(rule.id)
    ruleNotice.value = `Rule "${rule.keyword}" deleted.`
    if (ruleFormId.value === rule.id) {
      resetRuleForm()
    }
    await loadRules()
  } catch (error) {
    ruleNotice.value = toMessage(error, 'Delete rule fail.')
  }
}

async function toggleRuleActive(rule: Rule) {
  try {
    await updateRule(rule.id, {
      is_active: !rule.is_active,
    })
    ruleNotice.value = `Rule "${rule.keyword}" ${rule.is_active ? 'disabled' : 'enabled'}.`
    await loadRules()
  } catch (error) {
    ruleNotice.value = toMessage(error, 'Toggle rule fail.')
  }
}

async function executeCategorization() {
  runBusy.value = true
  runError.value = null
  runSummary.value = null

  try {
    const accountId = runAccountId.value.trim() || null
    const result = await runCategorization({
      scope: runScope.value,
      accountId,
    })
    runSummary.value = `Processed ${result.processed}. Categorized ${result.categorized}. Uncategorized ${result.uncategorized}. Duration ${result.duration_ms}ms.`
    await loadRules()
  } catch (error) {
    runError.value = toMessage(error, 'Run categorization fail.')
  } finally {
    runBusy.value = false
  }
}

function changeRulePage(delta: number) {
  const nextPage = ruleFilter.page + delta
  if (nextPage < 1 || nextPage > rulePageCount.value) return
  ruleFilter.page = nextPage
}

watch(
  () => [
    ruleFilter.categoryId,
    ruleFilter.source,
    ruleFilter.isActive,
    ruleFilter.search,
    ruleFilter.page,
    ruleFilter.pageSize,
    ruleFilter.sortBy,
    ruleFilter.sortOrder,
  ],
  () => {
    void loadRules()
  },
)

onMounted(async () => {
  await Promise.all([loadCategories(), loadRules()])
  resetCategoryForm()
  resetRuleForm()
})
</script>

<template>
  <section class="sectionGrid sectionGridTwo">
    <Card as="section">
      <div class="panelHeader">
        <div>
          <h2 class="panelTitle">Categories</h2>
          <p class="panelDescription">
            Manage system and custom categories. System category locked.
          </p>
        </div>

        <div class="row">
          <Badge variant="secondary">Total {{ categoryCount }}</Badge>
          <Button variant="outline" size="sm" type="button" @click="loadCategories">
            Refresh
          </Button>
        </div>
      </div>

      <div class="panelBody stack">
        <div v-if="categoriesError" class="banner">
          <div>
            <p class="bannerTitle">Load fail</p>
            <p class="bannerText">{{ categoriesError }}</p>
          </div>
        </div>

        <div v-if="categoryNotice" class="banner">
          <div>
            <p class="bannerTitle">Notice</p>
            <p class="bannerText">{{ categoryNotice }}</p>
          </div>
        </div>

        <form class="stack" @submit.prevent="saveCategory">
          <div class="grid2">
            <label class="field">
              <span class="fieldLabel">Name</span>
              <Input
                v-model="categoryForm.name"
                :disabled="isEditingSystemCategory"
                maxlength="100"
                placeholder="Groceries"
                required
              />
            </label>

            <label class="field">
              <span class="fieldLabel">Color</span>
              <Input
                v-model="categoryForm.color"
                maxlength="7"
                placeholder="#6B7280"
              />
            </label>
          </div>

          <label class="field">
            <span class="fieldLabel">Icon</span>
            <Input
              v-model="categoryForm.icon"
              maxlength="50"
              placeholder="shopping-cart"
            />
          </label>

          <div class="row">
            <Button type="submit">
              {{ categoryFormMode === 'create' ? 'Create category' : 'Save category' }}
            </Button>
            <Button variant="outline" type="button" @click="resetCategoryForm">
              Clear
            </Button>
          </div>
        </form>

        <div class="tableWrap">
          <table class="table tableCompact">
            <thead>
              <tr>
                <th>Color</th>
                <th>Name</th>
                <th>Status</th>
                <th class="right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="category in categories" :key="category.id">
                <td>
                  <div class="row">
                    <span class="swatch" :style="{ backgroundColor: category.color }" />
                    <span class="codeLike">{{ category.color }}</span>
                  </div>
                </td>
                <td>
                  <div class="stackSm">
                    <strong>{{ category.name }}</strong>
                    <span class="helperText">
                      Icon: {{ category.icon || 'none' }}
                    </span>
                  </div>
                </td>
                <td>
                  <Badge :variant="category.is_system ? 'warning' : 'secondary'">
                    {{ category.is_system ? 'System' : 'Custom' }}
                  </Badge>
                </td>
                <td class="right">
                  <div class="tableActions">
                    <Button
                      variant="secondary"
                      size="sm"
                      type="button"
                      :disabled="category.is_system"
                      @click="editCategory(category)"
                    >
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      type="button"
                      :disabled="category.is_system"
                      @click="removeCategory(category)"
                    >
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>

              <tr v-if="!categoriesLoading && categories.length === 0">
                <td colspan="4">
                  <div class="emptyState">
                    <p class="emptyStateTitle">No categories</p>
                    <p class="emptyStateText">Create first category now.</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="categoriesLoading" class="helperText">Loading categories...</div>
      </div>
    </Card>

    <Card as="section">
      <div class="panelHeader">
        <div>
          <h2 class="panelTitle">Rules</h2>
          <p class="panelDescription">
            Keyword rules. Priority order. Learned rules stay auditable.
          </p>
        </div>

        <div class="row">
          <Badge variant="success">Active {{ activeRuleCount }}</Badge>
          <Button variant="outline" size="sm" type="button" @click="loadRules">
            Refresh
          </Button>
        </div>
      </div>

      <div class="panelBody stack">
        <div class="grid2">
          <label class="field">
            <span class="fieldLabel">Search</span>
            <Input
              v-model="ruleFilter.search"
              placeholder="uber, market, banco..."
            />
          </label>

          <label class="field">
            <span class="fieldLabel">Category filter</span>
            <Select v-model.number="ruleFilter.categoryId">
              <option :value="null">All categories</option>
              <option v-for="category in categoryOptions" :key="category.id" :value="category.id">
                {{ category.name }}
              </option>
            </Select>
          </label>

          <label class="field">
            <span class="fieldLabel">Source</span>
            <Select v-model="ruleFilter.source">
              <option value="">All sources</option>
              <option value="manual">manual</option>
              <option value="learned">learned</option>
              <option value="system">system</option>
            </Select>
          </label>

          <label class="field">
            <span class="fieldLabel">Active</span>
            <Select v-model="ruleFilter.isActive">
              <option value="">All</option>
              <option value="true">Active only</option>
              <option value="false">Inactive only</option>
            </Select>
          </label>

          <label class="field">
            <span class="fieldLabel">Sort</span>
            <div class="grid2">
              <Select v-model="ruleFilter.sortBy">
                <option value="priority">priority</option>
                <option value="keyword">keyword</option>
                <option value="created_at">created_at</option>
              </Select>

              <Select v-model="ruleFilter.sortOrder">
                <option value="desc">desc</option>
                <option value="asc">asc</option>
              </Select>
            </div>
          </label>

          <label class="field">
            <span class="fieldLabel">Page size</span>
            <Select v-model.number="ruleFilter.pageSize">
              <option :value="10">10</option>
              <option :value="25">25</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
              <option :value="200">200</option>
            </Select>
          </label>
        </div>

        <div class="banner">
          <div class="stackSm">
            <p class="bannerTitle">Auto run</p>
            <div class="row">
              <Select v-model="runScope" class="inputSmall" style="max-width: 220px">
                <option value="uncategorized">uncategorized</option>
                <option value="all">all</option>
              </Select>
              <Input
                v-model="runAccountId"
                class="inputSmall"
                style="max-width: 260px"
                placeholder="account id optional"
              />
              <Button
                type="button"
                size="sm"
                :disabled="runBusy"
                @click="executeCategorization"
              >
                {{ runBusy ? 'Running...' : 'Run engine' }}
              </Button>
            </div>
            <p class="bannerText">
              {{ runSummary || 'Run engine on batch. Manual edits stay safe.' }}
            </p>
            <p v-if="runError" class="errorText">{{ runError }}</p>
          </div>
        </div>

        <form class="stack" @submit.prevent="saveRule">
          <div class="grid2">
            <label class="field">
              <span class="fieldLabel">Keyword</span>
              <Input
                v-model="ruleForm.keyword"
                maxlength="255"
                placeholder="supermercado extra"
                required
              />
            </label>

            <label class="field">
              <span class="fieldLabel">Category</span>
              <Select v-model.number="ruleForm.categoryId" required>
                <option :value="null" disabled>Select category</option>
                <option v-for="category in categoryOptions" :key="category.id" :value="category.id">
                  {{ category.name }}
                </option>
              </Select>
            </label>

            <label class="field">
              <span class="fieldLabel">Match type</span>
              <Select v-model="ruleForm.matchType">
                <option value="exact">exact</option>
                <option value="contains">contains</option>
                <option value="starts_with">starts_with</option>
                <option value="ends_with">ends_with</option>
              </Select>
            </label>

            <label class="field">
              <span class="fieldLabel">Priority</span>
              <Input v-model.number="ruleForm.priority" type="number" min="0" />
            </label>
          </div>

          <div class="row">
            <Button type="submit">
              {{ ruleFormMode === 'create' ? 'Create rule' : 'Save rule' }}
            </Button>
            <Button variant="outline" type="button" @click="resetRuleForm">
              Clear
            </Button>
          </div>
        </form>

        <div v-if="rulesError" class="banner">
          <div>
            <p class="bannerTitle">Rule load fail</p>
            <p class="bannerText">{{ rulesError }}</p>
          </div>
        </div>

        <div v-if="ruleNotice" class="banner">
          <div>
            <p class="bannerTitle">Notice</p>
            <p class="bannerText">{{ ruleNotice }}</p>
          </div>
        </div>

        <div class="tableWrap">
          <table class="table tableCompact">
            <thead>
              <tr>
                <th>Keyword</th>
                <th>Match</th>
                <th>Category</th>
                <th>Priority</th>
                <th>Source</th>
                <th>Active</th>
                <th class="right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rule in rules" :key="rule.id">
                <td>
                  <strong>{{ rule.keyword }}</strong>
                </td>
                <td>
                  <Badge>{{ rule.match_type }}</Badge>
                </td>
                <td>
                  <Badge
                    :variant="
                      rule.source === 'learned'
                        ? 'secondary'
                        : rule.source === 'system'
                          ? 'warning'
                          : 'default'
                    "
                  >
                    {{ rule.category_name || `#${rule.category_id}` }}
                  </Badge>
                </td>
                <td>{{ rule.priority }}</td>
                <td>
                  <Badge
                    :variant="
                      rule.source === 'manual'
                        ? 'warning'
                        : rule.source === 'learned'
                          ? 'secondary'
                          : 'default'
                    "
                  >
                    {{ rule.source }}
                  </Badge>
                </td>
                <td>
                  <label class="checkboxRow">
                    <input
                      type="checkbox"
                      :checked="rule.is_active"
                      @change="toggleRuleActive(rule)"
                    />
                    <span>{{ rule.is_active ? 'Yes' : 'No' }}</span>
                  </label>
                </td>
                <td class="right">
                  <div class="tableActions">
                    <Button
                      variant="secondary"
                      size="sm"
                      type="button"
                      @click="editRule(rule)"
                    >
                      Edit
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      type="button"
                      @click="removeRule(rule)"
                    >
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>

              <tr v-if="!rulesLoading && rules.length === 0">
                <td colspan="7">
                  <div class="emptyState">
                    <p class="emptyStateTitle">No rules</p>
                    <p class="emptyStateText">Create rule now or auto-learn from transaction edit.</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="rowBetween">
          <div class="helperText">
            Page {{ ruleFilter.page }} of {{ rulePageCount }} · {{ rulesTotal }} total
          </div>

          <div class="row">
            <Button
              variant="outline"
              size="sm"
              type="button"
              :disabled="ruleFilter.page <= 1"
              @click="changeRulePage(-1)"
            >
              Prev
            </Button>
            <Button
              variant="outline"
              size="sm"
              type="button"
              :disabled="ruleFilter.page >= rulePageCount"
              @click="changeRulePage(1)"
            >
              Next
            </Button>
          </div>
        </div>

        <div v-if="rulesLoading" class="helperText">Loading rules...</div>
      </div>
    </Card>
  </section>
</template>
