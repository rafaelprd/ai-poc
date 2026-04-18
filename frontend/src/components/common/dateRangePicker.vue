<script setup lang="ts">
const props = defineProps<{
  dateFrom: string
  dateTo: string
}>()

const emit = defineEmits<{
  (e: 'update:dateFrom', v: string): void
  (e: 'update:dateTo', v: string): void
}>()

function onFromChange(e: Event) {
  const val = (e.target as HTMLInputElement).value
  emit('update:dateFrom', val)
  // if dateTo is set and val > dateTo, clear dateTo
  if (props.dateTo && val > props.dateTo) {
    emit('update:dateTo', '')
  }
}

function onToChange(e: Event) {
  const val = (e.target as HTMLInputElement).value
  emit('update:dateTo', val)
  if (props.dateFrom && val < props.dateFrom) {
    emit('update:dateFrom', '')
  }
}
</script>

<template>
  <div class="grid2">
    <label class="field">
      <span class="fieldLabel">From</span>
      <input
        type="date"
        class="input"
        :value="dateFrom"
        :max="dateTo || undefined"
        @change="onFromChange"
      />
    </label>
    <label class="field">
      <span class="fieldLabel">To</span>
      <input
        type="date"
        class="input"
        :value="dateTo"
        :min="dateFrom || undefined"
        @change="onToChange"
      />
    </label>
  </div>
</template>
