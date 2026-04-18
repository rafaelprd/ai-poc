<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import type { Category, TransactionItem } from '../../lib/api'
import { patchTransactionCategory } from '../../lib/api'

const props = defineProps<{
  transactionId: number
  currentCategoryId: number | null
  categories: Category[]
}>()

const emit = defineEmits<{
  (e: 'saved', tx: TransactionItem): void
  (e: 'cancel'): void
}>()

const saving = ref(false)
const errorMsg = ref<string | null>(null)
const selectedId = ref<number | null>(props.currentCategoryId)

async function save() {
  saving.value = true
  errorMsg.value = null
  try {
    const updated = await patchTransactionCategory(props.transactionId, selectedId.value)
    emit('saved', updated)
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : 'Failed to save'
  } finally {
    saving.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cancel')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 4px; min-width: 180px;">
    <select
      class="select"
      :disabled="saving"
      :value="selectedId === null ? '' : String(selectedId)"
      @change="selectedId = ($event.target as HTMLSelectElement).value === '' ? null : Number(($event.target as HTMLSelectElement).value)"
    >
      <option value="">Uncategorized</option>
      <option v-for="cat in categories" :key="cat.id" :value="String(cat.id)">
        {{ cat.name }}
      </option>
    </select>

    <div class="row" style="gap: 4px;">
      <button class="button buttonPrimary buttonCompact" :disabled="saving" @click="save">
        {{ saving ? '…' : 'Save' }}
      </button>
      <button class="button buttonGhost buttonCompact" :disabled="saving" @click="emit('cancel')">
        Cancel
      </button>
    </div>

    <p v-if="errorMsg" class="errorText small">{{ errorMsg }}</p>
  </div>
</template>
