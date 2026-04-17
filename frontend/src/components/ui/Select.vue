<script setup lang="ts">
import { computed, useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false,
})

type SelectValue = string | number | null | undefined

interface SelectModifiers {
  number?: boolean
  trim?: boolean
}

const props = withDefaults(
  defineProps<{
    modelValue?: SelectValue
    modelModifiers?: SelectModifiers
  }>(),
  {
    modelValue: '',
  },
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: string | number | null): void
  (event: 'change', value: Event): void
}>()

const attrs = useAttrs()

const normalizedValue = computed(() =>
  props.modelValue === null || props.modelValue === undefined
    ? ''
    : String(props.modelValue),
)

function coerceValue(rawValue: string): string | number | null {
  const value = props.modelModifiers?.trim ? rawValue.trim() : rawValue

  if (props.modelModifiers?.number) {
    if (value === '') return null

    const parsed = Number(value)
    return Number.isNaN(parsed) ? null : parsed
  }

  return value
}

function handleChange(event: Event): void {
  const target = event.target as HTMLSelectElement
  emit('update:modelValue', coerceValue(target.value))
  emit('change', event)
}
</script>

<template>
  <select
    v-bind="attrs"
    :value="normalizedValue"
    class="select"
    @change="handleChange"
  >
    <slot />
  </select>
</template>
