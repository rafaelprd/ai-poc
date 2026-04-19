<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

type Granularity = 'daily' | 'monthly'

type TimeSeriesPoint = {
  date: string
  total_expenses: number
  total_income: number
}

const props = defineProps<{
  dailyDataPoints?: TimeSeriesPoint[]
  monthlyDataPoints?: TimeSeriesPoint[]
  initialGranularity?: Granularity
  ariaLabelPrefix?: string
}>()

const mode = ref<Granularity>(props.initialGranularity ?? 'daily')

watch(
  () => props.initialGranularity,
  (v) => {
    if (v) mode.value = v
  },
)

const dailyAvailable = computed(
  () => Array.isArray(props.dailyDataPoints) && props.dailyDataPoints.length > 0,
)
const monthlyAvailable = computed(
  () => Array.isArray(props.monthlyDataPoints) && props.monthlyDataPoints.length > 0,
)

const toggleVisible = computed(() => dailyAvailable.value && monthlyAvailable.value)

function parseDateISO(d: string): Date {
  // date comes like YYYY-MM-DD
  const [y, m, day] = d.split('-').map((x) => Number(x))
  return new Date(y, (m ?? 1) - 1, day ?? 1)
}

const activePoints = computed<TimeSeriesPoint[]>(() => {
  const list =
    mode.value === 'daily' ? props.dailyDataPoints : props.monthlyDataPoints

  if (!Array.isArray(list)) return []
  return [...list]
    .filter((p) => p && typeof p.date === 'string')
    .sort((a, b) => parseDateISO(a.date).getTime() - parseDateISO(b.date).getTime())
})

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

function formatDateLabel(d: Date, g: Granularity) {
  const month = d.toLocaleString('pt-BR', { month: 'short' })
  const year = d.getFullYear()
  const day = d.getDate().toString().padStart(2, '0')
  return g === 'daily' ? `${day}/${month}` : `${month}/${year}`
}

// Chart geometry
const W = 900
const H = 280
const PAD_L = 60
const PAD_R = 20
const PAD_T = 20
const PAD_B = 45

const innerW = W - PAD_L - PAD_R
const innerH = H - PAD_T - PAD_B

const containerEl = ref<SVGSVGElement | null>(null)

const tooltip = ref<{
  visible: boolean
  x: number
  y: number
  date: string
  expenses: number
  income: number
}>({
  visible: false,
  x: 0,
  y: 0,
  date: '',
  expenses: 0,
  income: 0,
})

const yMax = computed(() => {
  const pts = activePoints.value
  if (!pts.length) return 0

  let maxV = 0
  for (const p of pts) {
    const e = Number(p.total_expenses) || 0
    const i = Number(p.total_income) || 0
    if (e > maxV) maxV = e
    if (i > maxV) maxV = i
  }
  return maxV
})

function niceCeil(value: number) {
  if (!Number.isFinite(value) || value <= 0) return 1
  const exp = Math.floor(Math.log10(value))
  const base = Math.pow(10, exp)
  const f = value / base
  let niceF = 1
  if (f <= 1) niceF = 1
  else if (f <= 2) niceF = 2
  else if (f <= 5) niceF = 5
  else niceF = 10
  return niceF * base
}

const yMaxNice = computed(() => niceCeil(yMax.value * 1.1))

function xForIndex(i: number, n: number) {
  if (n <= 1) return PAD_L
  return PAD_L + (i / (n - 1)) * innerW
}

function yForValue(v: number) {
  const max = yMaxNice.value || 1
  const clamped = Math.max(0, v)
  const t = clamped / max
  return PAD_T + (1 - t) * innerH
}

const expensesSeries = computed(() =>
  activePoints.value.map((p) => Number(p.total_expenses) || 0),
)
const incomeSeries = computed(() =>
  activePoints.value.map((p) => Number(p.total_income) || 0),
)

function buildPath(values: number[]) {
  const n = values.length
  if (n === 0) return ''
  let d = ''
  for (let i = 0; i < n; i++) {
    const x = xForIndex(i, n)
    const y = yForValue(values[i])
    if (i === 0) d += `M ${x} ${y}`
    else d += ` L ${x} ${y}`
  }
  return d
}

const expensesPath = computed(() => buildPath(expensesSeries.value))
const incomePath = computed(() => buildPath(incomeSeries.value))

function buildAreaPath(values: number[]) {
  const n = values.length
  if (n === 0) return ''
  const baseY = PAD_T + innerH
  let d = ''
  for (let i = 0; i < n; i++) {
    const x = xForIndex(i, n)
    const y = yForValue(values[i])
    if (i === 0) d += `M ${x} ${y}`
    else d += ` L ${x} ${y}`
  }
  // close to baseline
  const lastX = xForIndex(n - 1, n)
  const firstX = xForIndex(0, n)
  d += ` L ${lastX} ${baseY}`
  d += ` L ${firstX} ${baseY}`
  d += ' Z'
  return d
}

const expensesAreaPath = computed(() => buildAreaPath(expensesSeries.value))
const incomeAreaPath = computed(() => buildAreaPath(incomeSeries.value))

const gridTicks = computed(() => {
  // 4 horizontal lines + baseline
  const max = yMaxNice.value || 1
  const ticks = 4
  const out: Array<{ value: number; y: number }> = []
  for (let k = 0; k <= ticks; k++) {
    const t = k / ticks
    const v = max * (1 - t)
    out.push({ value: v, y: PAD_T + t * innerH })
  }
  return out
})

// X labels: keep it readable
const xTicks = computed(() => {
  const pts = activePoints.value
  const n = pts.length
  if (!n) return []

  const step = mode.value === 'daily' ? Math.ceil(n / 6) : Math.ceil(n / 6)
  const idxs: number[] = []
  for (let i = 0; i < n; i += step) idxs.push(i)
  if (idxs[idxs.length - 1] !== n - 1) idxs.push(n - 1)

  return idxs.map((i) => ({
    i,
    x: xForIndex(i, n),
    label: formatDateLabel(parseDateISO(pts[i].date), mode.value),
  }))
})

function hideTooltip() {
  tooltip.value.visible = false
}

let raf: number | null = null
function onMouseMove(e: MouseEvent) {
  if (!containerEl.value) return
  const svg = containerEl.value
  const rect = svg.getBoundingClientRect()
  const px = e.clientX - rect.left
  const py = e.clientY - rect.top

  const n = activePoints.value.length
  if (n === 0) {
    hideTooltip()
    return
  }

  // Convert px within innerW to index
  const xInInner = px - PAD_L
  const t = innerW > 0 ? xInInner / innerW : 0
  const idx = Math.max(0, Math.min(n - 1, Math.round(t * (n - 1))))

  const p = activePoints.value[idx]
  const expenses = Number(p?.total_expenses ?? 0) || 0
  const income = Number(p?.total_income ?? 0) || 0

  const x = xForIndex(idx, n)
  const yE = yForValue(expenses)
  const yI = yForValue(income)
  const y = Math.min(yE, yI)

  if (raf) cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => {
    tooltip.value = {
      visible: true,
      x,
      y,
      date: p.date,
      expenses,
      income,
    }
  })

  // Cursor-follow tooltip positioning stays stable
  void py
}

onMounted(() => {
  if (!containerEl.value) return
  // tooltip updates in handler only
})

onBeforeUnmount(() => {
  if (raf) cancelAnimationFrame(raf)
})

// aria label
const aria = computed(() => {
  const prefix = props.ariaLabelPrefix ?? 'Gráfico de gastos e receitas'
  return `${prefix} (${mode.value === 'daily' ? 'diário' : 'mensal'}).`
})

function onToggle(next: Granularity) {
  mode.value = next
  hideTooltip()
}
</script>

<template>
  <section class="chartWrap" aria-label="Tempo gastos e receitas">
    <div class="headerRow">
      <div class="titleBlock">
        <div class="chartTitle">Gastos e receitas</div>
        <div class="chartSubtitle">
          Toggle: {{ mode === 'daily' ? 'Diário' : 'Mensal' }}
        </div>
      </div>

      <div v-if="toggleVisible" class="segmented" role="tablist" aria-label="Alternar granularidade">
        <button
          type="button"
          class="segBtn"
          :class="{ segBtnActive: mode === 'daily' }"
          role="tab"
          aria-selected="mode === 'daily'"
          @click="onToggle('daily')"
        >
          Diário
        </button>
        <button
          type="button"
          class="segBtn"
          :class="{ segBtnActive: mode === 'monthly' }"
          role="tab"
          aria-selected="mode === 'monthly'"
          @click="onToggle('monthly')"
        >
          Mensal
        </button>
      </div>

      <div v-else class="segmentedPlaceholder" aria-hidden="true" />
    </div>

    <div class="svgShell">
      <svg
        ref="containerEl"
        class="chartSvg"
        :viewBox="`0 0 ${W} ${H}`"
        role="img"
        :aria-label="aria"
        @mousemove="onMouseMove"
        @mouseleave="hideTooltip"
      >
        <!-- Grid -->
        <g class="grid">
          <line
            v-for="t in gridTicks"
            :key="t.value"
            :x1="PAD_L"
            :x2="W - PAD_R"
            :y1="t.y"
            :y2="t.y"
            stroke="hsl(var(--border))"
            stroke-width="1"
            opacity="0.55"
          />
        </g>

        <!-- Y labels (left) -->
        <g class="yLabels">
          <text
            v-for="t in gridTicks"
            :key="`y-${t.value}`"
            :x="PAD_L - 10"
            :y="t.y + 4"
            text-anchor="end"
            font-size="12"
            font-weight="750"
            fill="hsl(var(--muted-foreground))"
          >
            {{ Math.round(t.value) }}
          </text>
        </g>

        <!-- Areas -->
        <g v-if="activePoints.length > 0">
          <path :d="incomeAreaPath" fill="hsl(var(--success) / 0.10)" stroke="none" />
          <path :d="expensesAreaPath" fill="hsl(var(--destructive) / 0.10)" stroke="none" />
        </g>

        <!-- Lines -->
        <g v-if="activePoints.length > 0">
          <path
            :d="incomePath"
            fill="none"
            stroke="hsl(var(--success))"
            stroke-width="3"
            stroke-linecap="round"
            opacity="0.95"
          />
          <path
            :d="expensesPath"
            fill="none"
            stroke="hsl(var(--destructive))"
            stroke-width="3"
            stroke-linecap="round"
            opacity="0.95"
          />
        </g>

        <!-- X labels -->
        <g class="xLabels">
          <text
            v-for="xt in xTicks"
            :key="`x-${xt.i}`"
            :x="xt.x"
            :y="H - 18"
            text-anchor="middle"
            font-size="12"
            font-weight="800"
            fill="hsl(var(--muted-foreground))"
          >
            {{ xt.label }}
          </text>
        </g>

        <!-- Point hover targets -->
        <g v-if="activePoints.length > 0">
          <g v-for="(p, idx) in activePoints" :key="p.date">
            <circle
              :cx="xForIndex(idx, activePoints.length)"
              :cy="yForValue(Number(p.total_expenses) || 0)"
              r="4"
              fill="hsl(var(--destructive))"
              opacity="0.15"
            />
            <circle
              :cx="xForIndex(idx, activePoints.length)"
              :cy="yForValue(Number(p.total_income) || 0)"
              r="4"
              fill="hsl(var(--success))"
              opacity="0.15"
            />
          </g>
        </g>

        <!-- Tooltip anchors / vertical guideline -->
        <g v-if="tooltip.visible && activePoints.length > 0">
          <line
            :x1="tooltip.x"
            :x2="tooltip.x"
            :y1="PAD_T"
            :y2="PAD_T + innerH"
            stroke="hsl(var(--border))"
            stroke-width="1"
            opacity="0.8"
            stroke-dasharray="4 4"
          />
        </g>
      </svg>

      <div
        v-if="tooltip.visible"
        class="tooltip"
        role="tooltip"
        :style="{
          left: `${Math.max(10, tooltip.x)}px`,
          top: `${Math.max(10, tooltip.y)}px`,
        }"
      >
        <div class="ttDate">{{ tooltip.date }}</div>
        <div class="ttRow">
          <span class="sw expense" aria-hidden="true" />
          <span class="ttLabel">Despesas</span>
          <span class="ttValue">{{ formatMoney(tooltip.expenses) }}</span>
        </div>
        <div class="ttRow">
          <span class="sw income" aria-hidden="true" />
          <span class="ttLabel">Receitas</span>
          <span class="ttValue">{{ formatMoney(tooltip.income) }}</span>
        </div>
      </div>
    </div>

    <div class="srOnly" aria-live="polite">
      {{
        activePoints.length
          ? `Pontos: ${activePoints.length}. Último: ${activePoints[activePoints.length - 1].date}.`
          : 'Sem dados.'
      }}
    </div>
  </section>
</template>

<style scoped>
.chartWrap {
  display: grid;
  gap: 0.75rem;
}

.headerRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.titleBlock {
  display: grid;
  gap: 0.15rem;
}

.chartTitle {
  font-weight: 900;
  letter-spacing: -0.02em;
  font-size: 1rem;
}

.chartSubtitle {
  color: hsl(var(--muted-foreground));
  font-weight: 750;
  font-size: 0.9rem;
}

.segmented {
  display: inline-flex;
  border-radius: 999px;
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.72);
  overflow: hidden;
}

.segBtn {
  appearance: none;
  border: none;
  background: transparent;
  padding: 0.6rem 0.9rem;
  font-weight: 900;
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  transition: background-color 160ms ease, color 160ms ease;
}

.segBtnActive {
  background: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
}

.segmentedPlaceholder {
  width: 1px;
  height: 1px;
}

.svgShell {
  position: relative;
  width: 100%;
  border-radius: var(--radius-xl);
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.7);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.chartSvg {
  width: 100%;
  height: auto;
  display: block;
}

.tooltip {
  position: absolute;
  z-index: 5;
  transform: translate(10px, -10px);
  pointer-events: none;
  min-width: 200px;
  max-width: 260px;
  padding: 0.65rem 0.75rem;
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid hsl(var(--border));
  box-shadow: var(--shadow-md);
}

.ttDate {
  font-weight: 950;
  letter-spacing: -0.02em;
  margin-bottom: 0.35rem;
}

.ttRow {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.35rem;
}

.sw {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.sw.expense {
  background: hsl(var(--destructive));
  box-shadow: 0 0 0 2px rgb(255 255 255 / 0.7);
}

.sw.income {
  background: hsl(var(--success));
  box-shadow: 0 0 0 2px rgb(255 255 255 / 0.7);
}

.ttLabel {
  color: hsl(var(--muted-foreground));
  font-weight: 800;
}

.ttValue {
  margin-left: auto;
  font-weight: 950;
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
