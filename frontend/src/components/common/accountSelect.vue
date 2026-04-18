<script setup lang="ts">
import type { AccountItem } from '../../lib/api'

const props = defineProps<{
  modelValue: string | number | null
  accounts: AccountItem[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: string | number | null): void
}>()

function onChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  emit('update:modelValue', val === '' ? null : val)
}
</script>

<template>
  <select
    class="select"
    :value="modelValue === null ? '' : String(modelValue)"
    @change="onChange"
  >
    <option value="">All accounts</option>
    <option
      v-for="acc in accounts"
      :key="acc.id"
      :value="String(acc.id)"
    >
      {{ acc.name }}
    </option>
  </select>
</template>
