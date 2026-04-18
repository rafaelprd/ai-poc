import { ref, readonly } from 'vue'
import { listCategories, type Category } from '../lib/api'

export function useCategories() {
  const categories = ref<Category[]>([])
  const loading = ref(false)
  let fetched = false

  async function fetchCategories(force = false) {
    if (fetched && !force) return
    loading.value = true
    try {
      const res = await listCategories(true)
      categories.value = res.data
      fetched = true
    } catch {
      // silently fail; caller can show error
    } finally {
      loading.value = false
    }
  }

  return {
    categories: readonly(categories),
    loading: readonly(loading),
    fetchCategories,
  }
}
