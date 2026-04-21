<script setup lang="ts">
import { ref, computed } from 'vue'
import { createImport, ApiError } from '../../lib/api'
import fileDropZone from './fileDropZone.vue'
import importProgressTracker from './importProgressTracker.vue'
import Button from '../ui/Button.vue'

const props = defineProps<{
  accountId: string
}>()

const emit = defineEmits<{
  importCreated: [importId: number]
}>()

// ── State ────────────────────────────────────────────────────────────────────

const selectedFiles = ref<File[]>([])
const submitting = ref(false)
const submitError = ref<string | null>(null)
const activeImportId = ref<number | null>(null)
const finishedCount = ref(0)

const canSubmit = computed(
  () => selectedFiles.value.length > 0 && !submitting.value && activeImportId.value === null,
)

// ── Handlers ─────────────────────────────────────────────────────────────────

function onFilesSelected(files: File[]): void {
  selectedFiles.value = files
  submitError.value = null
}

async function submit(): Promise<void> {
  if (!canSubmit.value) return

  submitting.value = true
  submitError.value = null

  try {
    // API signature: createImport(files: File[], accountId: string)
    const result = await createImport(selectedFiles.value, props.accountId)
    activeImportId.value = result.id
    emit('importCreated', result.id)
    selectedFiles.value = []
  } catch (err) {
    if (err instanceof ApiError) {
      submitError.value = err.message
    } else if (err instanceof Error) {
      submitError.value = err.message
    } else {
      submitError.value = 'An unexpected error occurred. Please try again.'
    }
  } finally {
    submitting.value = false
  }
}

function onImportFinished(_detail: object): void {
  // Record completed import for this session, then allow a new upload
  finishedCount.value += 1
  activeImportId.value = null
}

function startAnother(): void {
  activeImportId.value = null
  submitError.value = null
  selectedFiles.value = []
}
</script>

<template>
  <div class="stack uploaderRoot">
    <!-- ── Upload form (shown when no active import in progress) ── -->
    <section v-if="activeImportId === null" class="panel">
      <div class="panelHeader">
        <div>
          <h2 class="panelTitle">Upload files</h2>
          <p class="panelDescription">
            Select one or more CSV or PDF files to import transactions.
          </p>
        </div>

        <Button
          type="button"
          :disabled="!canSubmit"
          @click="submit"
        >
          <template v-if="submitting">
            <svg
              class="btnSpinner"
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              stroke-linecap="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" stroke-opacity="0.2" />
              <path d="M12 2a10 10 0 0 1 10 10" />
            </svg>
            Uploading…
          </template>
          <template v-else>
            Upload {{ selectedFiles.length > 0 ? `${selectedFiles.length} file${selectedFiles.length === 1 ? '' : 's'}` : '' }}
          </template>
        </Button>
      </div>

      <div class="panelBody stack">
        <!-- Drop zone -->
        <fileDropZone
          :accepted-types="['.csv', '.pdf']"
          :max-files="20"
          :max-file-size-mb="10"
          @files-selected="onFilesSelected"
        />

        <!-- Account context hint -->
        <p v-if="accountId" class="helperText">
          Files will be imported into account <strong>{{ accountId }}</strong>.
        </p>

        <!-- Error banner -->
        <div
          v-if="submitError"
          class="banner"
          style="border-color: hsl(var(--destructive) / 0.22); background: hsl(var(--destructive) / 0.07);"
          role="alert"
        >
          <div>
            <p class="bannerTitle">Upload failed</p>
            <p class="bannerText">{{ submitError }}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            type="button"
            @click="submitError = null"
          >
            Dismiss
          </Button>
        </div>

        <!-- Helper when no files picked -->
        <p v-if="selectedFiles.length === 0 && !submitError" class="helperText uploaderHint">
          Pick files above, then click <strong>Upload</strong> to start the import.
        </p>
      </div>
    </section>

    <!-- ── Active import: progress tracker ── -->
    <section v-if="activeImportId !== null" class="panel">
      <div class="panelHeader">
        <div>
          <h2 class="panelTitle">Import in progress</h2>
          <p class="panelDescription">Processing your files… this may take a moment.</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          type="button"
          @click="startAnother"
        >
          Upload more files
        </Button>
      </div>

      <div class="panelBody">
        <importProgressTracker
          :import-id="activeImportId"
          @import-finished="onImportFinished"
        />
      </div>
    </section>

    <!-- ── Completed imports (this session) ── -->
    <section v-if="finishedCount > 0 && activeImportId === null" class="finishedSession">
      <div
        class="banner"
        style="border-color: hsl(var(--success) / 0.25); background: hsl(var(--success) / 0.06);"
      >
        <div>
          <p class="bannerTitle">
            {{ finishedCount === 1 ? '1 import completed' : `${finishedCount} imports completed` }} this session
          </p>
          <p class="bannerText">
            Check the Import History tab to review all imported transactions.
          </p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.uploaderRoot {
  display: grid;
  gap: var(--space-5);
}

/* ── Spinner inside the button ───────────────────────────── */
.btnSpinner {
  display: inline-block;
  vertical-align: middle;
  margin-right: var(--space-1);
  animation: spin 0.9s linear infinite;
  transform-origin: center;
  color: currentColor;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ── Helper hint text ────────────────────────────────────── */
.uploaderHint {
  text-align: center;
  padding: var(--space-2) 0;
}

/* ── Session summary ─────────────────────────────────────── */
.finishedSession {
  display: grid;
  gap: var(--space-3);
}
</style>
