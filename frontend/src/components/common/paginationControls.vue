<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  page: number
  pageSize: number
  totalItems: number
  totalPages: number
}>()

const emit = defineEmits<{
  (e: 'update:page', v: number): void
  (e: 'update:pageSize', v: number): void
}>()

const pageSizes = [25, 50, 100, 200]

const pageNumbers = computed(() => {
  const total = props.totalPages
  const current = props.page
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages: (number | '...')[] = []
  pages.push(1)
  if (current > 3) pages.push('...')
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    pages.push(i)
  }
  if (current < total - 2) pages.push('...')
  pages.push(total)
  return pages
})

function onPageSizeChange(e: Event) {
  const val = Number((e.target as HTMLSelectElement).value)
  emit('update:pageSize', val)
  emit('update:page', 1)
}
</script>

<template>
  <div class="rowBetween" style="align-items: center; flex-wrap: wrap; gap: 8px;">
    <p class="muted small">
      {{ totalItems }} transactions · Page {{ page }} of {{ totalPages }}
    </p>

    <div class="row" style="gap: 4px; align-items: center; flex-wrap: wrap;">
      <button
        class="button buttonGhost buttonCompact"
        :disabled="page <= 1"
        @click="emit('update:page', page - 1)"
      >
        ‹ Prev
      </button>

      <template v-for="p in pageNumbers" :key="String(p)">
        <span v-if="p === '...'" class="muted" style="padding: 0 4px;">…</span>
        <button
          v-else
          class="button buttonCompact"
          :class="p === page ? 'buttonPrimary' : 'buttonGhost'"
          @click="emit('update:page', p as number)"
        >
          {{ p }}
        </button>
      </template>

      <button
        class="button buttonGhost buttonCompact"
        :disabled="page >= totalPages"
        @click="emit('update:page', page + 1)"
      >
        Next ›
      </button>

      <select class="select" style="width: auto;" :value="pageSize" @change="onPageSizeChange">
        <option v-for="s in pageSizes" :key="s" :value="s">{{ s }} / page</option>
      </select>
    </div>
  </div>
</template>
