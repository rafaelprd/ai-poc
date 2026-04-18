<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  modelValue: string
  debounceMs?: number
}>(), {
  debounceMs: 300,
})

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void
}>()

const localValue = ref(props.modelValue)
let timer: ReturnType<typeof setTimeout> | null = null

watch(() => props.modelValue, (v) => {
  if (v !== localValue.value) localValue.value = v
})

function onInput(e: Event) {
  localValue.value = (e.target as HTMLInputElement).value
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    emit('update:modelValue', localValue.value)
  }, props.debounceMs)
}
</script>

<template>
  <input
    type="text"
    class="input"
    :value="localValue"
    placeholder="Search descriptions..."
    @input="onInput"
  />
</template>
