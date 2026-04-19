<script setup lang="ts">
import { computed, ref } from 'vue'

type PieSlice = {
  category_id: number | null
  category_name: string
  total: number
  percentage: number
  color: string
}

const props = defineProps<{
  slices: PieSlice[]
  uncategorizedTotal: number
  uncategorizedPercentage: number
  ariaLabel?: string
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

function formatPct(v: number) {
  if (!Number.isFinite(v)) return '—'
  return `${v.toFixed(2)}%`
}

const containerEl = ref<HTMLElement | null>(null)
const tooltip = ref<{
  visible: boolean
  x: number
  y: number
  title: string
  body: string
}>({
  visible: false,
  x: 0,
  y: 0,
  title: '',
  body: '',
})

const DEFAULT_UNC_COLOR = '#9E9E9E'

type Segment = {
  key: string
  label: string
  total: number
  percentage: number
  color: string
}

const segments = computed<Segment[]>(() => {
  const base = Array.isArray(props.slices) ? props.slices : []

  const safeSlices: Segment[] = base
    .filter((s) => s && typeof s.percentage === 'number')
    .map((s) => ({
      key: String(s.category_id ?? 'uncategorized'),
      label: s.category_name ?? 'Sem Categoria',
      total: Number(s.total ?? 0),
      percentage: Number(s.percentage ?? 0),
      color: s.color || '#9E9E9E',
    }))

  const uncTotal = Number(props.uncategorizedTotal ?? 0)
  const uncPct = Number(props.uncategorizedPercentage ?? 0)

  if (uncTotal > 0 || uncPct > 0) {
    safeSlices.push({
      key: 'uncategorized',
      label: 'Sem Categoria',
      total: uncTotal,
      percentage: uncPct,
      color: DEFAULT_UNC_COLOR,
    })
  }

  return safeSlices
})

const totalPercentage = computed(() => {
  const sum = segments.value.reduce((acc, s) => acc + (Number(s.percentage) || 0), 0)
  return sum
})

const hasData = computed(() => {
  return segments.value.some((s) => (s.total ?? 0) > 0 || (s.percentage ?? 0) > 0)
})

// Donut geometry
const size = 260
const cx = size / 2
const cy = size / 2
const outerRadius = 92
const innerRadius = 62

function polarToCartesian(r: number, angleRad: number) {
  return {
    x: cx + r * Math.cos(angleRad),
    y: cy + r * Math.sin(angleRad),
  }
}

/**
 * Create a donut ring sector path using two arcs (outer then inner reversed).
 * Angles are radians, where 0 starts at 3 o'clock (east).
 */
function ringSectorPath(startAngle: number, endAngle: number) {
  const startOuter = polarToCartesian(outerRadius, startAngle)
  const endOuter = polarToCartesian(outerRadius, endAngle)

  const startInner = polarToCartesian(innerRadius, endAngle)
  const endInner = polarToCartesian(innerRadius, startAngle)

  const delta = endAngle - startAngle
  const largeArcFlag = delta >= Math.PI ? 1 : 0

  // Outer arc: start -> end
  // Inner arc: end -> start (reverse direction)
  return [
    `M ${startOuter.x} ${startOuter.y}`,
    `A ${outerRadius} ${outerRadius} 0 ${largeArcFlag} 1 ${endOuter.x} ${endOuter.y}`,
    `L ${startInner.x} ${startInner.y}`,
    `A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 0 ${endInner.x} ${endInner.y}`,
    'Z',
  ].join(' ')
}

function showTooltip(seg: Segment, clientX: number, clientY: number) {
  const el = containerEl.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  tooltip.value = {
    visible: true,
    x: clientX - rect.left,
    y: clientY - rect.top,
    title: seg.label,
    body: `${formatMoney(seg.total)} • ${formatPct(seg.percentage)}`,
  }
}

function hideTooltip() {
  tooltip.value.visible = false
}

const aria = computed(() => {
  return props.ariaLabel ?? 'Gráfico de distribuição por categoria'
})

const paths = computed(() => {
  if (!hasData.value.valueOf()) return []

  const totalPerc = totalPercentage.value
  // If percentages are all zero or missing, avoid division by zero.
  if (!totalPerc || totalPerc <= 0) return []

  const full = Math.PI * 2
  let cursor = -Math.PI / 2 // start at top

  // Build in the order provided
  return segments.value.map((seg) => {
    const perc = Number(seg.percentage) || 0
    const sweep = (perc / totalPerc) * full

    // If sweep is too tiny, skip (avoids degenerate arcs)
    if (sweep <= 0) {
      return {
        key: seg.key,
        path: '',
        seg,
        visible: false,
      }
    }

    const start = cursor
    const end = cursor + sweep
    cursor = end

    return {
      key: seg.key,
      path: ringSectorPath(start, end),
      seg,
      visible: true,
    }
  })
})

// If we have no data, show a neutral ring segment.
const emptyRingPath = computed(() => {
  const start = -Math.PI / 2
  const end = start + Math.PI * 2
  return ringSectorPath(start, end)
})
</script>

<template>
  <div class="chartShell" ref="containerEl" :aria-label="aria">
    <div class="chartAndCenter">
      <svg
        :width="size"
        :height="size"
        :viewBox="`0 0 ${size} ${size}`"
        role="img"
        :aria-label="aria"
      >
        <!-- Track (background ring) -->
        <path
          :d="emptyRingPath"
          fill="none"
          stroke="hsl(var(--border))"
          stroke-width="28"
          stroke-linecap="round"
          opacity="0.55"
          v-if="!hasData"
        />

        <!-- Segments -->
        <g v-if="hasData">
          <path
            v-for="p in paths"
            :key="p.key"
            v-if="p.visible"
            :d="p.path"
            :fill="p.seg.color || '#9E9E9E'"
            stroke="rgb(255 255 255 / 0.75)"
            stroke-width="1.5"
            @mouseenter="(e) => showTooltip(p.seg, (e as MouseEvent).clientX, (e as MouseEvent).clientY)"
            @mousemove="(e) => showTooltip(p.seg, (e as MouseEvent).clientX, (e as MouseEvent).clientY)"
            @mouseleave="hideTooltip"
          >
            <title>
              {{ p.seg.label }}
              — {{ formatMoney(p.seg.total) }} ({{ formatPct(p.seg.percentage) }})
            </title>
          </path>
        </g>

        <!-- Center label -->
        <circle :cx="cx" :cy="cy" :r="innerRadius - 10" fill="rgb(255 255 255 / 0.95)" />
        <text
          :x="cx"
          :y="cy - 6"
          text-anchor="middle"
          font-size="14"
          font-weight="800"
          fill="hsl(var(--foreground))"
        >
          Categorias
        </text>
        <text
          :x="cx"
          :y="cy + 16"
          text-anchor="middle"
          font-size="12"
          font-weight="700"
          fill="hsl(var(--muted-foreground))"
        >
          {{ hasData ? formatPct(totalPercentage) : '0.00%' }}
        </text>
      </svg>

      <div
        v-if="tooltip.visible"
        class="tooltip"
        :style="{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }"
        role="tooltip"
        aria-live="polite"
      >
        <div class="ttTitle">{{ tooltip.title }}</div>
        <div class="ttBody">{{ tooltip.body }}</div>
      </div>
    </div>

    <div class="legend" aria-label="Legenda do gráfico de categorias">
      <div class="legendRow" v-for="seg in segments" :key="seg.key" v-show="(seg.total ?? 0) > 0 || (seg.percentage ?? 0) > 0">
        <span class="swatch" :style="{ backgroundColor: seg.color || DEFAULT_UNC_COLOR }" aria-hidden="true" />
        <div class="legendText">
          <div class="legendLabel">
            {{ seg.label }}
          </div>
          <div class="legendMeta">
            {{ formatMoney(seg.total) }} • {{ formatPct(seg.percentage) }}
          </div>
        </div>
      </div>

      <div v-if="!segments.length || !hasData" class="legendEmpty">
        Sem dados para este período.
      </div>
    </div>
  </div>
</template>

<style scoped>
.chartShell {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  align-items: center;
}

.chartAndCenter {
  position: relative;
  display: grid;
  place-items: center;
}

.tooltip {
  position: absolute;
  transform: translate(10px, -10px);
  z-index: 5;
  pointer-events: none;
  min-width: 180px;
  max-width: 240px;
  padding: 0.6rem 0.75rem;
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid hsl(var(--border));
  box-shadow: var(--shadow-md);
}

.ttTitle {
  font-weight: 900;
  letter-spacing: -0.02em;
  margin-bottom: 0.15rem;
}

.ttBody {
  color: hsl(var(--muted-foreground));
  font-weight: 750;
}

.legend {
  display: grid;
  gap: 0.65rem;
  padding-top: 0.2rem;
}

.legendRow {
  display: flex;
  gap: 0.7rem;
  align-items: flex-start;
}

.swatch {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  margin-top: 0.45rem;
  box-shadow: 0 0 0 2px rgb(255 255 255 / 0.8);
  flex: 0 0 auto;
}

.legendText {
  display: grid;
  gap: 0.2rem;
  min-width: 0;
}

.legendLabel {
  font-weight: 850;
  letter-spacing: -0.02em;
  font-size: 0.95rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.legendMeta {
  color: hsl(var(--muted-foreground));
  font-weight: 700;
  font-size: 0.88rem;
}

.legendEmpty {
  color: hsl(var(--muted-foreground));
  font-weight: 750;
  padding: 0.8rem 0;
}

/* Desktop: legend to the right, chart on the left */
@media (min-width: 1024px) {
  .chartShell {
    grid-template-columns: 360px 1fr;
    align-items: start;
  }
  .chartAndCenter {
    justify-content: center;
  }
  .legend {
    padding-top: 0.6rem;
  }
}
</style>
