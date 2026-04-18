<script setup lang="ts">
import { ref } from 'vue'
import type { Category } from '../../lib/api'

const props = defineProps<{
  selectedCount: number
  categories: Category[]
}>()

const emit = defineEmits<{
  (e: 'bulk-update', payload: { categoryId: number | null }): void
  (e: 'clear-selection'): void
}>()

const selectedCategoryId = ref<number | null>(null)
const showConfirm = ref(false)

function onApplyClick() {
  if (props.selectedCount > 20) {
    showConfirm.value = true
  } else {
    doApply()
  }
}

function doApply() {
  showConfirm.value = false
  emit('bulk-update', { categoryId: selectedCategoryId.value })
}
</script>

<template>
  <div v-if="selectedCount > 0" class="bulkBar">
    <span class="muted">{{ selectedCount }} selected</span>

    <select
      class="select"
      :value="selectedCategoryId === null ? '' : String(selectedCategoryId)"
      @change="selectedCategoryId = ($event.target as HTMLSelectElement).value === '' ? null : Number(($event.target as HTMLSelectElement).value)"
    >
      <option value="">Uncategorized</option>
      <option v-for="cat in categories" :key="cat.id" :value="String(cat.id)">
        {{ cat.name }}
      </option>
    </select>

    <button class="button buttonPrimary buttonCompact" type="button" @click="onApplyClick">
      Apply to {{ selectedCount }}
    </button>

    <button class="button buttonGhost buttonCompact" type="button" @click="emit('clear-selection')">
      Clear selection
    </button>

    <!-- Confirmation modal -->
    <div v-if="showConfirm" class="modalBackdrop" @click.self="showConfirm = false">
      <div class="modal">
        <div class="modalHeader">
          <h3>Confirm bulk update</h3>
        </div>
        <div class="modalBody">
          <p>You are about to update <strong>{{ selectedCount }}</strong> transactions. Continue?</p>
        </div>
        <div class="modalFooter">
          <button class="button buttonPrimary buttonCompact" @click="doApply">Confirm</button>
          <button class="button buttonGhost buttonCompact" @click="showConfirm = false">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>
