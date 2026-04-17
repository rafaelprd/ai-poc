<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ApiError,
  getBatchErrors,
  getBatchStatus,
  listBatches,
  uploadIngestionFiles,
} from '../lib/api'
import Badge from './ui/Badge.vue'
import Button from './ui/Button.vue'
import Card from './ui/Card.vue'
import Input from './ui/Input.vue'

type BatchStatusResponse = Awaited<ReturnType<typeof getBatchStatus>>
type BatchErrorsResponse = Awaited<ReturnType<typeof getBatchErrors>>
type BatchListResponse = Awaited<ReturnType<typeof listBatches>>
type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'destructive'

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFiles = ref<File[]>([])
const accountId = ref('')
const uploadMessage = ref('')
const uploadError = ref('')
const uploadPending = ref(false)

const batches = ref<BatchListResponse['batches']>([])
const batchesTotal = ref(0)
const batchesPage = ref(1)
const batchesPageSize = 20
const batchesLoading = ref(false)
const batchesError = ref('')

const selectedBatchId = ref<string | null>(null)
const selectedBatch = ref<BatchStatusResponse | null>(null)
const selectedBatchLoading = ref(false)
const selectedBatchError = ref('')
const selectedErrors = ref<BatchErrorsResponse | null>(null)
const selectedErrorsLoading = ref(false)
const selectedErrorsPage = ref(1)
const selectedErrorsPageSize = 10
const selectedErrorsError = ref('')

let pollingTimer: number | null = null

const uploadSelectedCount = computed(() => selectedFiles.value.length)

const selectedBatchFiles = computed(() => selectedBatch.value?.files ?? [])

const selectedBatchSummary = computed(() => {
  if (!selectedBatch.value) return null

  return {
    status: selectedBatch.value.status,
    createdAt: selectedBatch.value.created_at,
    created: selectedBatch.value.total_transactions_created,
    skipped: selectedBatch.value.duplicates_skipped,
    files: selectedBatch.value.files.length,
  }
})

const selectedBatchErrors = computed(() => selectedErrors.value?.errors ?? [])
const selectedBatchErrorsTotal = computed(() => selectedErrors.value?.total ?? 0)
const selectedBatchErrorsPage = computed(
  () => selectedErrors.value?.page ?? selectedErrorsPage.value,
)
const selectedBatchErrorsPageSize = computed(
  () => selectedErrors.value?.page_size ?? selectedErrorsPageSize,
)
const selectedBatchHasMoreErrors = computed(() => {
  const total = selectedBatchErrorsTotal.value
  return selectedErrorsPage.value * selectedBatchErrorsPageSize.value < total
})

function batchStatusVariant(status: string): BadgeVariant {
  if (status === 'completed') return 'success'
  if (status === 'processing') return 'warning'
  if (status === 'failed') return 'destructive'
  return 'secondary'
}

function fileStatusVariant(status: string): BadgeVariant {
  if (status === 'completed') return 'success'
  if (status === 'processing') return 'warning'
  if (status === 'failed') return 'destructive'
  return 'secondary'
}

function formatBytes(sizeBytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB']
  let value = sizeBytes
  let unitIndex = 0

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }

  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const dateValue = new Date(value)
  if (Number.isNaN(dateValue.getTime())) return value
  return dateValue.toLocaleString()
}

function safeApiMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.code}: ${error.message}`
  }
  if (error instanceof Error) return error.message
  return 'Request failed.'
}

function clearUploadState() {
  uploadMessage.value = ''
  uploadError.value = ''
}

function clearSelectedBatchErrors() {
  selectedErrors.value = null
  selectedErrorsError.value = ''
}

function stopPolling() {
  if (pollingTimer !== null) {
    window.clearInterval(pollingTimer)
    pollingTimer = null
  }
}

async function loadBatches(selectLatest = false): Promise<void> {
  batchesLoading.value = true
  batchesError.value = ''

  try {
    const response = await listBatches({
      page: batchesPage.value,
      pageSize: batchesPageSize,
    })

    batches.value = response.batches
    batchesTotal.value = response.total

    if (selectLatest && response.batches.length > 0) {
      selectedBatchId.value = response.batches[0].batch_id
    } else if (!selectedBatchId.value && response.batches.length > 0) {
      selectedBatchId.value = response.batches[0].batch_id
    }
  } catch (error) {
    batchesError.value = safeApiMessage(error)
  } finally {
    batchesLoading.value = false
  }
}

async function loadSelectedBatch(): Promise<void> {
  if (!selectedBatchId.value) {
    selectedBatch.value = null
    clearSelectedBatchErrors()
    stopPolling()
    return
  }

  selectedBatchLoading.value = true
  selectedBatchError.value = ''
  selectedErrorsLoading.value = true
  selectedErrorsError.value = ''

  try {
    const [batchResponse, errorsResponse] = await Promise.all([
      getBatchStatus(selectedBatchId.value),
      getBatchErrors(selectedBatchId.value, {
        page: selectedErrorsPage.value,
        pageSize: selectedErrorsPageSize,
      }),
    ])

    selectedBatch.value = batchResponse
    selectedErrors.value = errorsResponse

    stopPolling()
    if (batchResponse.status === 'processing') {
      pollingTimer = window.setInterval(() => {
        void refreshSelectedBatch()
      }, 3000)
    }
  } catch (error) {
    const message = safeApiMessage(error)
    selectedBatchError.value = message
    selectedErrorsError.value = message
    selectedBatch.value = null
    selectedErrors.value = null
    stopPolling()
  } finally {
    selectedBatchLoading.value = false
    selectedErrorsLoading.value = false
  }
}

async function refreshSelectedBatch(): Promise<void> {
  if (!selectedBatchId.value) return

  try {
    const [batchResponse, errorsResponse] = await Promise.all([
      getBatchStatus(selectedBatchId.value),
      getBatchErrors(selectedBatchId.value, {
        page: selectedErrorsPage.value,
        pageSize: selectedErrorsPageSize,
      }),
    ])

    selectedBatch.value = batchResponse
    selectedErrors.value = errorsResponse

    if (batchResponse.status !== 'processing') {
      stopPolling()
    }
  } catch (error) {
    selectedBatchError.value = safeApiMessage(error)
    stopPolling()
  }
}

async function handleFilesPicked(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFiles.value = Array.from(input.files ?? [])
  clearUploadState()
}

async function uploadFiles() {
  if (selectedFiles.value.length === 0) {
    uploadError.value = 'Pick at least one file.'
    return
  }

  uploadPending.value = true
  clearUploadState()

  try {
    const response = await uploadIngestionFiles(
      selectedFiles.value,
      accountId.value.trim() || null,
    )

    uploadMessage.value = `Batch ${response.batch_id} created. ${response.files.length} file(s) queued.`
    selectedFiles.value = []
    if (fileInput.value) fileInput.value.value = ''
    batchesPage.value = 1
    await loadBatches(true)
    selectedBatchId.value = response.batch_id
  } catch (error) {
    uploadError.value = safeApiMessage(error)
  } finally {
    uploadPending.value = false
  }
}

async function selectBatch(batchId: string) {
  selectedBatchId.value = batchId
  selectedErrorsPage.value = 1
  await loadSelectedBatch()
}

async function changeErrorPage(delta: number) {
  const nextPage = selectedErrorsPage.value + delta
  if (nextPage < 1) return

  selectedErrorsPage.value = nextPage
  await loadSelectedBatch()
}

watch(selectedBatchId, () => {
  void loadSelectedBatch()
})

onMounted(() => {
  void loadBatches()
  if (selectedBatchId.value) {
    void loadSelectedBatch()
  }
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <section class="sectionGrid sectionGridTwo">
    <Card as="section">
      <div class="panelHeader">
        <div>
          <h2 class="panelTitle">Upload files</h2>
          <p class="panelDescription">CSV or PDF. One batch per upload action.</p>
        </div>

        <div class="row">
          <Button
            variant="outline"
            size="sm"
            type="button"
            :disabled="batchesLoading"
            @click="loadBatches(true)"
          >
            Refresh batches
          </Button>

          <Button
            size="sm"
            type="button"
            :disabled="uploadPending"
            @click="uploadFiles"
          >
            {{ uploadPending ? 'Uploading…' : 'Upload batch' }}
          </Button>
        </div>
      </div>

      <div class="panelBody stack">
        <div class="grid2">
          <label class="field">
            <span class="fieldLabel">Account ID</span>
            <Input
              v-model="accountId"
              type="text"
              placeholder="Optional UUID"
            />
          </label>

          <label class="field">
            <span class="fieldLabel">Files</span>
            <input
              ref="fileInput"
              class="input"
              type="file"
              multiple
              accept=".csv,.pdf,text/csv,application/pdf"
              @change="handleFilesPicked"
            />
          </label>
        </div>

        <div v-if="uploadMessage" class="banner">
          <div>
            <p class="bannerTitle">Upload queued</p>
            <p class="bannerText">{{ uploadMessage }}</p>
          </div>
        </div>

        <div
          v-if="uploadError"
          class="banner"
          style="border-color: hsl(var(--destructive) / 0.18); background: hsl(var(--destructive) / 0.06)"
        >
          <div>
            <p class="bannerTitle">Upload error</p>
            <p class="bannerText">{{ uploadError }}</p>
          </div>
        </div>

        <div class="kpiRow">
          <article class="kpiCard">
            <p class="kpiValue">{{ uploadSelectedCount }}</p>
            <p class="kpiLabel">Selected files</p>
          </article>
          <article class="kpiCard">
            <p class="kpiValue">{{ batchesTotal }}</p>
            <p class="kpiLabel">Total batches</p>
          </article>
          <article class="kpiCard">
            <p class="kpiValue">{{ selectedBatchSummary?.created ?? 0 }}</p>
            <p class="kpiLabel">Created tx</p>
          </article>
          <article class="kpiCard">
            <p class="kpiValue">{{ selectedBatchSummary?.skipped ?? 0 }}</p>
            <p class="kpiLabel">Skipped duplicates</p>
          </article>
        </div>

        <div v-if="selectedFiles.length" class="stackSm">
          <p class="helperText">Picked files</p>
          <div class="row">
            <Badge
              v-for="file in selectedFiles"
              :key="`${file.name}-${file.size}`"
              variant="secondary"
            >
              {{ file.name }} · {{ formatBytes(file.size) }}
            </Badge>
          </div>
        </div>

        <div v-if="batchesError" class="errorText">{{ batchesError }}</div>

        <div class="list">
          <div
            v-for="batch in batches"
            :key="batch.batch_id"
            class="listItem"
            :style="batch.batch_id === selectedBatchId ? 'border-color: hsl(var(--primary) / 0.35); box-shadow: 0 0 0 1px hsl(var(--primary) / 0.1) inset;' : ''"
          >
            <div class="listItemHeader">
              <div>
                <p class="listItemTitle">{{ batch.batch_id }}</p>
                <p class="listItemMeta">
                  {{ formatDateTime(batch.created_at) }} · {{ batch.file_count }} file(s)
                </p>
              </div>

              <Badge :variant="batchStatusVariant(batch.status)">
                {{ batch.status }}
              </Badge>
            </div>

            <div class="listItemFooter">
              <Badge variant="secondary">
                {{ batch.total_transactions_created }} created
              </Badge>
              <Button
                variant="outline"
                size="sm"
                type="button"
                @click="selectBatch(batch.batch_id)"
              >
                Open
              </Button>
            </div>
          </div>

          <div v-if="!batchesLoading && batches.length === 0" class="emptyState">
            <p class="emptyStateTitle">No batches yet</p>
            <p class="emptyStateText">Upload first file. Batch shows here.</p>
          </div>

          <p v-if="batchesLoading" class="helperText">Loading batches…</p>
        </div>
      </div>
    </Card>

    <Card as="section">
      <div class="panelHeader">
        <div>
          <h2 class="panelTitle">Batch detail</h2>
          <p class="panelDescription">Watch processing, file status, and parse errors.</p>
        </div>

        <div class="row">
          <Button
            variant="outline"
            size="sm"
            type="button"
            :disabled="!selectedBatchId || selectedBatchLoading"
            @click="refreshSelectedBatch"
          >
            Refresh
          </Button>
        </div>
      </div>

      <div class="panelBody stack">
        <div
          v-if="selectedBatchError"
          class="banner"
          style="border-color: hsl(var(--destructive) / 0.18); background: hsl(var(--destructive) / 0.06)"
        >
          <div>
            <p class="bannerTitle">Batch error</p>
            <p class="bannerText">{{ selectedBatchError }}</p>
          </div>
        </div>

        <div v-if="selectedBatchSummary" class="kpiRow">
          <article class="kpiCard">
            <p class="kpiValue">{{ selectedBatchSummary.status }}</p>
            <p class="kpiLabel">Status</p>
          </article>
          <article class="kpiCard">
            <p class="kpiValue">{{ selectedBatchSummary.files }}</p>
            <p class="kpiLabel">Files</p>
          </article>
          <article class="kpiCard">
            <p class="kpiValue">{{ selectedBatchSummary.created }}</p>
            <p class="kpiLabel">Created</p>
          </article>
          <article class="kpiCard">
            <p class="kpiValue">{{ selectedBatchSummary.skipped }}</p>
            <p class="kpiLabel">Skipped</p>
          </article>
        </div>

        <div v-if="selectedBatchSummary" class="banner">
          <div>
            <p class="bannerTitle">Selected batch</p>
            <p class="bannerText">
              {{ selectedBatchId }} · {{ formatDateTime(selectedBatchSummary.createdAt) }}
            </p>
          </div>
          <Badge :variant="batchStatusVariant(selectedBatchSummary.status)">
            {{ selectedBatchSummary.status }}
          </Badge>
        </div>

        <div v-if="selectedBatchLoading" class="emptyState">
          <p class="emptyStateTitle">Loading batch…</p>
          <p class="emptyStateText">Wait a second.</p>
        </div>

        <div v-if="selectedBatch">
          <h3 class="panelTitle" style="margin-bottom: 0.75rem">Files</h3>
          <div class="list">
            <div v-for="file in selectedBatchFiles" :key="file.file_id" class="fileCard">
              <div class="fileCardHeader">
                <div>
                  <p class="fileCardTitle">{{ file.original_filename }}</p>
                  <p class="fileCardMeta">
                    {{ file.file_id }} · extracted {{ file.rows_extracted }} · failed
                    {{ file.rows_failed }}
                  </p>
                </div>
                <Badge :variant="fileStatusVariant(file.status)">
                  {{ file.status }}
                </Badge>
              </div>

              <div v-if="file.error_message" class="errorText" style="margin-top: 0.75rem">
                {{ file.error_message }}
              </div>
            </div>
          </div>
        </div>

        <div v-if="selectedErrors" class="stack">
          <div class="rowBetween">
            <div>
              <h3 class="panelTitle" style="margin-bottom: 0.25rem">Parse errors</h3>
              <p class="panelDescription">
                {{ selectedBatchErrorsTotal }} error(s) total
              </p>
            </div>

            <div class="row">
              <Button
                variant="outline"
                size="sm"
                type="button"
                :disabled="selectedErrorsPage <= 1"
                @click="changeErrorPage(-1)"
              >
                Prev
              </Button>
              <Badge variant="secondary">
                Page {{ selectedBatchErrorsPage }}
              </Badge>
              <Button
                variant="outline"
                size="sm"
                type="button"
                :disabled="!selectedBatchHasMoreErrors"
                @click="changeErrorPage(1)"
              >
                Next
              </Button>
            </div>
          </div>

          <div class="tableWrap">
            <table class="table tableCompact">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Row</th>
                  <th>Type</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="error in selectedBatchErrors" :key="`${error.file_id}-${error.row_number}-${error.error_type}`">
                  <td>{{ error.original_filename ?? error.file_id }}</td>
                  <td>{{ error.row_number ?? '—' }}</td>
                  <td>{{ error.error_type }}</td>
                  <td class="wrap">{{ error.error_message }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="selectedErrorsLoading" class="helperText">Loading errors…</div>
          <div v-if="selectedErrorsError" class="errorText">{{ selectedErrorsError }}</div>
        </div>
      </div>
    </Card>
  </section>
</template>

<style scoped>
.panel {
  min-width: 0;
}
</style>
