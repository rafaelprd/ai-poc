import { ref, readonly } from 'vue'
import { listAccounts, type AccountItem } from '../lib/api'

export function useAccounts() {
  const accounts = ref<AccountItem[]>([])
  const loading = ref(false)
  let fetched = false

  async function fetchAccounts(force = false) {
    if (fetched && !force) return
    loading.value = true
    try {
      const res = await listAccounts()
      accounts.value = res.items
      fetched = true
    } catch {
      // silently fail
    } finally {
      loading.value = false
    }
  }

  return {
    accounts: readonly(accounts),
    loading: readonly(loading),
    fetchAccounts,
  }
}
