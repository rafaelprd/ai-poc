<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  totalExpenses: number
  totalIncome: number
  net: number
}>()

const brl = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function formatMoney(v: number) {
  if (!Number.isFinite(v)) return '—'
  return brl.format(v)
}

const netVariant = computed(() => (props.net >= 0 ? 'positive' : 'negative'))
const netLabel = computed(() => (props.net >= 0 ? 'Saldo Líquido' : 'Saldo Líquido (negativo)'))
</script>

<template>
  <section class="monthlySummary" aria-label="Resumo mensal">
    <div class="metric" aria-label="Total de despesas">
      <div class="metricLabel">Despesas</div>
      <div class="metricValue dangerText">{{ formatMoney(totalExpenses) }}</div>
    </div>

    <div class="metric" aria-label="Total de receitas">
      <div class="metricLabel">Receitas</div>
      <div class="metricValue successText">{{ formatMoney(totalIncome) }}</div>
    </div>

    <div class="metric" aria-label="Saldo líquido">
      <div class="metricLabel">{{ netLabel }}</div>
      <div class="metricValue" :class="netVariant === 'positive' ? 'positiveText' : 'negativeText'">
        {{ formatMoney(net) }}
      </div>
    </div>
  </section>
</template>

<style scoped>
.monthlySummary {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: stretch;
}

.metric {
  padding: 1rem 1.05rem;
  border-radius: var(--radius-xl);
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.9);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.metricLabel {
  color: hsl(var(--muted-foreground));
  font-size: 0.9rem;
  margin-bottom: 0.35rem;
  font-weight: 650;
}

.metricValue {
  font-size: 1.35rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.dangerText {
  color: hsl(var(--destructive));
}

.successText {
  color: hsl(var(--success));
}

.positiveText {
  color: hsl(var(--success));
}

.negativeText {
  color: hsl(var(--destructive));
}

@media (max-width: 1023px) {
  .monthlySummary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .monthlySummary {
    grid-template-columns: 1fr;
  }
}
</style>
