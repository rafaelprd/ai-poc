<template>
  <input
    v-bind="attrs"
    :id="id"
    :name="name"
    :type="type"
    :value="displayValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :readonly="readonly"
    :required="required"
    :autocomplete="autocomplete"
    :min="min"
    :max="max"
    :step="step"
    :minlength="minlength"
    :maxlength="maxlength"
    class="input"
    @input="handleInput"
  />
</template>

<script setup lang="ts">
import { computed, useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false,
})

type ModelValue = string | number | null | undefined

interface ModelModifiers {
  trim?: boolean
  number?: boolean
}

interface Props {
  modelValue?: ModelValue
  modelModifiers?: ModelModifiers
  type?: string
  placeholder?: string
  disabled?: boolean
  readonly?: boolean
  required?: boolean
  autocomplete?: string
  id?: string
  name?: string
  min?: string | number
  max?: string | number
  step?: string | number
  minlength?: number
  maxlength?: number
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  placeholder: '',
  disabled: false,
  readonly: false,
  required: false,
})

const emit = defineEmits<{
  (event: 'update:modelValue', value: ModelValue): void
}>()

const attrs = useAttrs()

const displayValue = computed(() => props.modelValue ?? '')

function normalizeValue(rawValue: string): ModelValue {
  const nextValue = props.modelModifiers?.trim ? rawValue.trim() : rawValue

  if (props.modelModifiers?.number) {
    if (nextValue === '') return null

    const parsed = Number(nextValue)
    return Number.isNaN(parsed) ? null : parsed
  }

  return nextValue
}

function handleInput(event: Event): void {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', normalizeValue(target.value))
}
</script>
