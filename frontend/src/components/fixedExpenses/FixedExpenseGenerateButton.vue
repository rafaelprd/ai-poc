<script setup lang="ts">
import { ref } from 'vue'
import { useFixedExpenses } from '../../composables/useFixedExpenses'
import Button from '../ui/Button.vue'
import type { GenerationResult } from '../../lib/api'

const emit = defineEmits<{
  (e: 'generated', result: GenerationResult): void
}>()

const { generateEntries } = useFixedExpenses()

const showDialog = ref(false)
const targetDate = ref(new Date().toISOString().slice(0, 10))
const loading = ref(false)
const resultMsg = ref<string | null>(null)
const errorMsg = ref<string | null>(null)

async function onGenerate() {
  loading.value = true
  resultMsg.value = null
  errorMsg.value = null
  const result = await generateEntries(targetDate.value)
  loading.value = false
  if (result) {
    resultMsg.value = `Generated: ${result.generated_count} | Skipped: ${result.skipped_count}`
    emit('generated', result)
    setTimeout(() => { showDialog.value = false; resultMsg.value = null }, 2000)
  } else {
    errorMsg.value = 'Generation failed.'
  }
}
</script>

<template>
  <div style="display: inline-block;">
    <Button variant="secondary" size="sm" @click="showDialog = true">⚡ Generate Entries</Button>

    <div v-if="showDialog" class="modalBackdrop" @click.self="showDialog = false">
      <div class="modal" style="max-width: 360px; width: 100%;">
        <div class="modalHeader">
          <h3 class="panelTitle">Generate Entries</h3>
          <button class="button buttonGhost buttonIconOnly" @click="showDialog = false">✕</button>
        </div>
        <div class="modalBody stack">
          <div class="field">
            <label class="fieldLabel">Target Date</label>
            <input class="input" type="date" v-model="targetDate" />
            <p class="muted small" style="margin-top: 4px;">Entries will be generated for the period containing this date.</p>
          </div>
          <div v-if="resultMsg" class="successText small">{{ resultMsg }}</div>
          <div v-if="errorMsg" class="errorText small">{{ errorMsg }}</div>
        </div>
        <div class="modalFooter">
          <Button variant="ghost" @click="showDialog = false">Cancel</Button>
          <Button :disabled="loading" @click="onGenerate">{{ loading ? 'Generating…' : 'Generate' }}</Button>
        </div>
      </div>
    </div>
  </div>
</template>
