<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAccounts } from '../../composables/useAccounts'
import { useCategories } from '../../composables/useCategories'
import FixedExpenseList from './FixedExpenseList.vue'

const { accounts, fetchAccounts } = useAccounts()
const { categories, fetchCategories } = useCategories()

onMounted(async () => {
  await Promise.all([fetchAccounts(), fetchCategories()])
})

// Toast system
interface Toast {
  id: number
  type: 'success' | 'error'
  title: string
  body: string
}
let _seq = 0
const toasts = ref<Toast[]>([])

function showToast(payload: { type: 'success' | 'error'; title: string; body: string }) {
  const id = ++_seq
  toasts.value.push({ id, ...payload })
  setTimeout(() => { toasts.value = toasts.value.filter((t) => t.id !== id) }, 5000)
}
</script>

<template>
  <div>
    <FixedExpenseList
      :accounts="accounts as any[]"
      :categories="categories as any[]"
      @toast="showToast"
    />

    <!-- Toast stack -->
    <div class="toastStack">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast"
        :class="toast.type === 'success' ? 'toastSuccess' : 'toastError'"
      >
        <div class="toastTitle">{{ toast.title }}</div>
        <div class="toastBody">{{ toast.body }}</div>
      </div>
    </div>
  </div>
</template>
