<script setup lang="ts">
import { ref, computed } from 'vue'
import Button from '../ui/Button.vue'

const props = withDefaults(
  defineProps<{
    acceptedTypes?: string[]
    maxFiles?: number
    maxFileSizeMb?: number
  }>(),
  {
    acceptedTypes: () => ['.csv', '.pdf'],
    maxFiles: 20,
    maxFileSizeMb: 10,
  },
)

const emit = defineEmits<{
  filesSelected: [files: File[]]
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const isDragOver = ref(false)
const selectedFiles = ref<File[]>([])
const rejections = ref<{ name: string; reason: string }[]>([])

const acceptAttr = computed(() => props.acceptedTypes.join(','))

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getExtension(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

function validateAndAdd(incoming: File[]): void {
  rejections.value = []
  const maxBytes = props.maxFileSizeMb * 1024 * 1024
  const toAdd: File[] = []

  for (const file of incoming) {
    const ext = getExtension(file.name)
    if (!props.acceptedTypes.map((t) => t.toLowerCase()).includes(ext)) {
      rejections.value.push({ name: file.name, reason: `Type not allowed (${ext || 'no extension'})` })
      continue
    }
    if (file.size > maxBytes) {
      rejections.value.push({ name: file.name, reason: `Exceeds ${props.maxFileSizeMb} MB limit` })
      continue
    }
    if (selectedFiles.value.some((f) => f.name === file.name && f.size === file.size)) {
      continue // silently skip duplicate
    }
    toAdd.push(file)
  }

  const combined = [...selectedFiles.value, ...toAdd]
  if (combined.length > props.maxFiles) {
    const overflow = combined.slice(props.maxFiles)
    overflow.forEach((f) => {
      if (toAdd.includes(f)) {
        rejections.value.push({ name: f.name, reason: `Exceeds max ${props.maxFiles} files` })
      }
    })
    selectedFiles.value = combined.slice(0, props.maxFiles)
  } else {
    selectedFiles.value = combined
  }

  emit('filesSelected', [...selectedFiles.value])
}

function handleInputChange(e: Event): void {
  const input = e.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    validateAndAdd(Array.from(input.files))
  }
  // reset so same file can be re-added after remove
  input.value = ''
}

function handleDrop(e: DragEvent): void {
  isDragOver.value = false
  if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
    validateAndAdd(Array.from(e.dataTransfer.files))
  }
}

function handleDragOver(e: DragEvent): void {
  e.preventDefault()
  isDragOver.value = true
}

function handleDragLeave(): void {
  isDragOver.value = false
}

function openBrowser(): void {
  fileInput.value?.click()
}

function removeFile(index: number): void {
  selectedFiles.value.splice(index, 1)
  emit('filesSelected', [...selectedFiles.value])
}
</script>

<template>
  <div class="dropZoneWrapper">
    <!-- Hidden file input -->
    <input
      ref="fileInput"
      type="file"
      multiple
      :accept="acceptAttr"
      class="hiddenInput"
      @change="handleInputChange"
    />

    <!-- Drop zone -->
    <div
      class="dropZone"
      :class="{ dropZoneActive: isDragOver }"
      role="button"
      tabindex="0"
      :aria-label="`Drop files here or click to browse. Accepted: ${acceptedTypes.join(', ')}`"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop.prevent="handleDrop"
      @click="openBrowser"
      @keydown.enter.space="openBrowser"
    >
      <div class="dropZoneInner">
        <div class="dropIcon" aria-hidden="true">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
            <polyline points="7 9 12 4 17 9" />
            <line x1="12" y1="4" x2="12" y2="16" />
          </svg>
        </div>
        <p class="dropTitle">Drop files here or <span class="dropLink">browse</span></p>
        <p class="helperText">
          Accepted: {{ acceptedTypes.join(', ') }} · Max {{ maxFileSizeMb }} MB per file · Up to {{ maxFiles }} files
        </p>
      </div>
    </div>

    <!-- Rejection errors -->
    <div v-if="rejections.length" class="stackSm">
      <p
        v-for="rejection in rejections"
        :key="rejection.name"
        class="errorText"
      >
        <strong>{{ rejection.name }}</strong> — {{ rejection.reason }}
      </p>
    </div>

    <!-- Selected file list -->
    <div v-if="selectedFiles.length" class="fileList">
      <div
        v-for="(file, index) in selectedFiles"
        :key="`${file.name}-${file.size}`"
        class="fileRow"
      >
        <div class="fileRowInfo">
          <svg class="fileIcon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span class="fileName truncate">{{ file.name }}</span>
          <span class="fileSize muted">{{ formatBytes(file.size) }}</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          type="button"
          :aria-label="`Remove ${file.name}`"
          @click.stop="removeFile(index)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dropZoneWrapper {
  display: grid;
  gap: var(--space-3);
}

.hiddenInput {
  display: none;
}

.dropZone {
  border: 2px dashed hsl(var(--border));
  border-radius: var(--radius-lg);
  background: linear-gradient(
    180deg,
    rgb(255 255 255 / 0.03),
    rgb(255 255 255 / 0.01)
  ),
  hsl(var(--card));
  padding: var(--space-8) var(--space-6);
  text-align: center;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease;
  outline: none;
}

.dropZone:hover,
.dropZone:focus-visible {
  border-color: hsl(var(--primary) / 0.55);
  background: hsl(var(--accent) / 0.18);
}

.dropZoneActive {
  border-color: hsl(var(--primary));
  background: hsl(var(--primary) / 0.06) !important;
}

.dropZoneInner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  pointer-events: none;
}

.dropIcon {
  color: hsl(var(--muted-foreground));
  margin-bottom: var(--space-1);
}

.dropZoneActive .dropIcon {
  color: hsl(var(--primary));
}

.dropTitle {
  margin: 0;
  font-weight: 700;
  font-size: 0.95rem;
}

.dropLink {
  color: hsl(var(--primary));
  text-decoration: underline;
  text-underline-offset: 3px;
}

.fileList {
  display: grid;
  gap: var(--space-2);
}

.fileRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius);
  background: hsl(var(--secondary));
}

.fileRowInfo {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  flex: 1;
}

.fileIcon {
  flex-shrink: 0;
  color: hsl(var(--muted-foreground));
}

.fileName {
  font-size: 0.88rem;
  font-weight: 600;
  min-width: 0;
  flex: 1;
}

.fileSize {
  font-size: 0.8rem;
  color: hsl(var(--muted-foreground));
  white-space: nowrap;
  flex-shrink: 0;
}
</style>
