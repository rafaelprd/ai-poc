<script setup lang="ts">
import type { Category } from '../../lib/api'

const props = defineProps<{
  modelValue: number | null
  categories: Category[]
  allowNull?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: number | null): void
}>()

function onChange(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  emit('update:modelValue', val === '' ? null : Number(val))
}
</script>

<template>
  <select
    class="select"
    :value="modelValue === null ? '' : String(modelValue)"
    @change="onChange"
  >
    <option value="">{{ placeholder ?? (allowNull ? 'Uncategorized' : 'All categories') }}</option>
    <option
      v-for="cat in categories"
      :key="cat.id"
      :value="String(cat.id)"
    >
      {{ cat.name }}
    </option>
  </select>
</template>
