<script setup lang="ts">
import { computed } from 'vue'

type MonthYear = { month: number; year: number }

const props = defineProps<{
  modelValue: MonthYear
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: MonthYear): void
}>()

const currentYear = new Date().getFullYear()
const minYear = 2000
const maxYear = currentYear + 1

const monthOptions = [
  { value: 1, label: 'Jan' },
  { value: 2, label: 'Fev' },
  { value: 3, label: 'Mar' },
  { value: 4, label: 'Abr' },
  { value: 5, label: 'Mai' },
  { value: 6, label: 'Jun' },
  { value: 7, label: 'Jul' },
  { value: 8, label: 'Ago' },
  { value: 9, label: 'Set' },
  { value: 10, label: 'Out' },
  { value: 11, label: 'Nov' },
  { value: 12, label: 'Dez' },
] as const

const yearOptions = computed(() => {
  const years: number[] = []
  for (let y = minYear; y <= maxYear; y++) years.push(y)
  return years
})

function shiftMonth(delta: number) {
  const curMonth = props.modelValue.month
  const curYear = props.modelValue.year

  const m0 = curMonth - 1 + delta
  const y = curYear + Math.floor(m0 / 12)
  const m = (m0 % 12) + 1

  const yearClamped = Math.max(minYear, Math.min(maxYear, y))
  // If clamping year caused overflow, keep month within 1..12 already guaranteed by formula.
  emit('update:modelValue', { month: m, year: yearClamped })
}

function onMonthChange(e: Event) {
  const val = Number((e.target as HTMLSelectElement).value)
  if (!Number.isFinite(val)) return
  emit('update:modelValue', { ...props.modelValue, month: val })
}

function onYearChange(e: Event) {
  const val = Number((e.target as HTMLSelectElement).value)
  if (!Number.isFinite(val)) return
  const clamped = Math.max(minYear, Math.min(maxYear, val))
  emit('update:modelValue', { ...props.modelValue, year: clamped })
}
</script>

<template>
  <div class="monthYearSelector" aria-label="Selecionar mês e ano">
    <div class="row">
      <button class="navBtn" type="button" @click="shiftMonth(-1)" aria-label="Mês anterior">
        ←
      </button>

      <div class="selectors">
        <div class="field">
          <label class="srOnly" for="monthSelect">Mês</label>
          <select
            id="monthSelect"
            class="select"
            :value="modelValue.month"
            @change="onMonthChange"
            aria-label="Mês"
          >
            <option v-for="m in monthOptions" :key="m.value" :value="m.value">
              {{ m.label }}
            </option>
          </select>
        </div>

        <div class="divider" aria-hidden="true">/</div>

        <div class="field">
          <label class="srOnly" for="yearSelect">Ano</label>
          <select
            id="yearSelect"
            class="select"
            :value="modelValue.year"
            @change="onYearChange"
            aria-label="Ano"
          >
            <option v-for="y in yearOptions" :key="y" :value="y">
              {{ y }}
            </option>
          </select>
        </div>
      </div>

      <button class="navBtn" type="button" @click="shiftMonth(1)" aria-label="Próximo mês">
        →
      </button>
    </div>
  </div>
</template>

<style scoped>
.monthYearSelector {
  display: block;
}

.row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.selectors {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.72);
}

.field {
  display: flex;
  align-items: center;
}

.select {
  border: none;
  outline: none;
  background: transparent;
  color: inherit;
  font-size: 0.98rem;
  padding: 0.2rem 0;
}

.divider {
  color: hsl(var(--muted-foreground));
  font-weight: 600;
}

.navBtn {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 999px;
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.72);
  color: hsl(var(--foreground));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: transform 160ms ease, background-color 160ms ease;
}

.navBtn:hover {
  transform: translateY(-1px);
  background: hsl(var(--accent) / 0.25);
}

.srOnly {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
