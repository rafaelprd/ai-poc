<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useFixedExpenses } from '../../composables/useFixedExpenses'
import Button from '../ui/Button.vue'
import type { FixedExpenseItem, FixedExpenseFrequency, AccountItem, Category } from '../../lib/api'

const props = defineProps<{
  expense?: FixedExpenseItem | null
  accounts: AccountItem[]
  categories: Category[]
}>()

const emit = defineEmits<{
  (e: 'saved', expense: FixedExpenseItem): void
  (e: 'cancelled'): void
}>()

const { createExpense, updateExpense, error } = useFixedExpenses()

const isEdit = computed(() => !!props.expense)

const form = ref({
  name: props.expense?.name ?? '',
  amount: props.expense?.amount ?? '',
  frequency: (props.expense?.frequency ?? 'monthly') as FixedExpenseFrequency,
  day_of_month: props.expense?.day_of_month ?? 1,
  day_of_week: props.expense?.day_of_week ?? 0,
  account_id: props.expense?.account_id ?? (props.accounts[0]?.id ? String(props.accounts[0].id) : ''),
  category_id: props.expense?.category_id ?? null as number | null,
  start_date: props.expense?.start_date ?? '',
  end_date: props.expense?.end_date ?? '',
  description: props.expense?.description ?? '',
})

watch(() => props.expense, (exp) => {
  if (exp) {
    form.value = {
      name: exp.name,
      amount: exp.amount,
      frequency: exp.frequency,
      day_of_month: exp.day_of_month ?? 1,
      day_of_week: exp.day_of_week ?? 0,
      account_id: exp.account_id,
      category_id: exp.category_id,
      start_date: exp.start_date,
      end_date: exp.end_date ?? '',
      description: exp.description ?? '',
    }
  }
})

const isWeekly = computed(() => form.value.frequency === 'weekly' || form.value.frequency === 'biweekly')

const submitting = ref(false)
const formError = ref<string | null>(null)

const DAY_OF_WEEK_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

const FREQUENCY_LABELS: Record<FixedExpenseFrequency, string> = {
  weekly: 'Weekly',
  biweekly: 'Every 2 weeks',
  monthly: 'Monthly',
  bimonthly: 'Every 2 months',
  quarterly: 'Quarterly',
  semiannual: 'Semiannual',
  annual: 'Annual',
}

async function onSubmit() {
  formError.value = null
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      name: form.value.name,
      amount: form.value.amount,
      frequency: form.value.frequency,
      account_id: form.value.account_id,
      category_id: form.value.category_id || null,
      start_date: form.value.start_date,
      end_date: form.value.end_date || null,
      description: form.value.description || null,
    }
    if (isWeekly.value) {
      payload.day_of_week = Number(form.value.day_of_week)
      payload.day_of_month = null
    } else {
      payload.day_of_month = Number(form.value.day_of_month)
      payload.day_of_week = null
    }

    let result: FixedExpenseItem | null
    if (isEdit.value && props.expense) {
      const { account_id: _a, start_date: _s, ...updatePayload } = payload as any
      result = await updateExpense(props.expense.id, updatePayload)
    } else {
      result = await createExpense(payload as any)
    }

    if (result) {
      emit('saved', result)
    } else {
      formError.value = error.value ?? 'An error occurred'
    }
  } catch (e: unknown) {
    formError.value = e instanceof Error ? e.message : 'An error occurred'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="modalBackdrop" @click.self="emit('cancelled')">
    <div class="modal" style="max-width: 560px; width: 100%;">
      <div class="modalHeader">
        <h3 class="panelTitle">{{ isEdit ? 'Edit Fixed Expense' : 'New Fixed Expense' }}</h3>
        <button class="button buttonGhost buttonIconOnly" type="button" @click="emit('cancelled')">✕</button>
      </div>
      <form class="modalBody stack" @submit.prevent="onSubmit">
        <div v-if="formError" class="errorText small">{{ formError }}</div>

        <div class="grid2">
          <div class="field">
            <label class="fieldLabel">Name *</label>
            <input class="input" v-model="form.name" type="text" required placeholder="e.g. Rent" />
          </div>
          <div class="field">
            <label class="fieldLabel">Amount (BRL) *</label>
            <input class="input" v-model="form.amount" type="number" step="0.01" min="0.01" required placeholder="0.00" />
          </div>
        </div>

        <div class="grid2">
          <div class="field">
            <label class="fieldLabel">Frequency *</label>
            <select class="select" v-model="form.frequency">
              <option v-for="(label, key) in FREQUENCY_LABELS" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
          <div class="field" v-if="isWeekly">
            <label class="fieldLabel">Day of Week *</label>
            <select class="select" v-model="form.day_of_week">
              <option v-for="(label, idx) in DAY_OF_WEEK_LABELS" :key="idx" :value="idx">{{ label }}</option>
            </select>
          </div>
          <div class="field" v-else>
            <label class="fieldLabel">Day of Month *</label>
            <input class="input" v-model="form.day_of_month" type="number" min="1" max="31" required />
          </div>
        </div>

        <div class="grid2">
          <div class="field">
            <label class="fieldLabel">Account *</label>
            <select class="select" v-model="form.account_id" :disabled="isEdit">
              <option v-for="acc in accounts" :key="String(acc.id)" :value="String(acc.id)">{{ acc.name }}</option>
            </select>
          </div>
          <div class="field">
            <label class="fieldLabel">Category</label>
            <select class="select" v-model="form.category_id">
              <option :value="null">— None —</option>
              <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
            </select>
          </div>
        </div>

        <div class="grid2">
          <div class="field">
            <label class="fieldLabel">Start Date *</label>
            <input class="input" v-model="form.start_date" type="date" required :disabled="isEdit" />
          </div>
          <div class="field">
            <label class="fieldLabel">End Date</label>
            <input class="input" v-model="form.end_date" type="date" />
          </div>
        </div>

        <div class="field">
          <label class="fieldLabel">Description</label>
          <textarea class="textarea" v-model="form.description" rows="2" placeholder="Optional notes…" />
        </div>

        <div class="modalFooter">
          <Button type="button" variant="ghost" @click="emit('cancelled')">Cancel</Button>
          <Button type="submit" :disabled="submitting">{{ submitting ? 'Saving…' : isEdit ? 'Save Changes' : 'Create' }}</Button>
        </div>
      </form>
    </div>
  </div>
</template>
