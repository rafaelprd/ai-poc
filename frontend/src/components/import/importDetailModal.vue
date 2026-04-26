<script setup lang="ts">
import { ref, watch } from "vue";
import { getImportDetail } from "../../lib/api";
import type { ImportDetail } from "../../lib/api";
import importFileResultItem from "./importFileResultItem.vue";
import Badge from "../ui/Badge.vue";
import Button from "../ui/Button.vue";

const props = defineProps<{
    importId: number | null;
    visible: boolean;
}>();

const emit = defineEmits<{
    close: [];
}>();

// ── State ─────────────────────────────────────────────────────────────────────

const detail = ref<ImportDetail | null>(null);
const loading = ref(false);
const fetchError = ref<string | null>(null);

// ── Helpers ───────────────────────────────────────────────────────────────────

type BadgeVariant =
    | "default"
    | "secondary"
    | "success"
    | "warning"
    | "destructive";

function statusVariant(status: string): BadgeVariant {
    switch (status) {
        case "completed":
            return "success";
        case "completed_with_errors":
            return "warning";
        case "failed":
            return "destructive";
        case "processing":
            return "warning";
        default:
            return "secondary";
    }
}

function statusLabel(status: string): string {
    switch (status) {
        case "pending":
            return "Pending";
        case "processing":
            return "Processing";
        case "completed":
            return "Completed";
        case "completed_with_errors":
            return "Completed with errors";
        case "failed":
            return "Failed";
        default:
            return status;
    }
}

function formatDate(iso: string): string {
    try {
        return new Intl.DateTimeFormat(undefined, {
            year: "numeric",
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        }).format(new Date(iso));
    } catch {
        return iso;
    }
}

// ── Data fetching ─────────────────────────────────────────────────────────────

async function fetchDetail(): Promise<void> {
    if (props.importId === null) return;

    loading.value = true;
    fetchError.value = null;
    detail.value = null;

    try {
        detail.value = await getImportDetail(props.importId);
    } catch (err) {
        fetchError.value =
            err instanceof Error
                ? err.message
                : "Failed to load import details.";
    } finally {
        loading.value = false;
    }
}

watch(
    () => props.visible,
    (isVisible) => {
        if (isVisible && props.importId !== null) {
            fetchDetail();
        } else if (!isVisible) {
            detail.value = null;
            fetchError.value = null;
        }
    },
);

watch(
    () => props.importId,
    (id) => {
        if (props.visible && id !== null) {
            fetchDetail();
        }
    },
);

// ── Keyboard / backdrop close ─────────────────────────────────────────────────

function onBackdropClick(e: MouseEvent): void {
    if ((e.target as HTMLElement).classList.contains("modalBackdrop")) {
        emit("close");
    }
}

function onKeydown(e: KeyboardEvent): void {
    if (e.key === "Escape") emit("close");
}
</script>

<template>
    <Teleport to="body">
        <Transition name="modalFade">
            <div
                v-if="visible"
                class="modalBackdrop"
                role="dialog"
                aria-modal="true"
                :aria-label="
                    detail ? `Import #${detail.id} details` : 'Import details'
                "
                @click="onBackdropClick"
                @keydown="onKeydown"
            >
                <div class="modal importDetailModal">
                    <!-- ── Modal header ── -->
                    <div class="modalHeader">
                        <div class="stackSm">
                            <h2 class="modalTitle">
                                Import #{{ importId }}
                                <Badge
                                    v-if="detail"
                                    :variant="statusVariant(detail.status)"
                                    style="
                                        margin-left: 0.5rem;
                                        vertical-align: middle;
                                    "
                                >
                                    {{ statusLabel(detail.status) }}
                                </Badge>
                            </h2>
                            <p v-if="detail" class="helperText">
                                Created {{ formatDate(detail.createdAt) }}
                            </p>
                        </div>
                        <Button
                            variant="ghost"
                            size="icon"
                            type="button"
                            aria-label="Close"
                            @click="emit('close')"
                        >
                            <svg
                                width="16"
                                height="16"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2.5"
                                stroke-linecap="round"
                                aria-hidden="true"
                            >
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </Button>
                    </div>

                    <!-- ── Modal body ── -->
                    <div class="modalBody stack">
                        <!-- Loading -->
                        <div v-if="loading" class="importDetailLoading">
                            <svg
                                class="spinner"
                                width="22"
                                height="22"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2.5"
                                stroke-linecap="round"
                                aria-label="Loading…"
                            >
                                <circle
                                    cx="12"
                                    cy="12"
                                    r="10"
                                    stroke-opacity="0.2"
                                />
                                <path d="M12 2a10 10 0 0 1 10 10" />
                            </svg>
                            <span class="helperText"
                                >Loading import details…</span
                            >
                        </div>

                        <!-- Fetch error -->
                        <div
                            v-else-if="fetchError"
                            class="banner"
                            style="
                                border-color: hsl(var(--destructive) / 0.22);
                                background: hsl(var(--destructive) / 0.07);
                            "
                            role="alert"
                        >
                            <div>
                                <p class="bannerTitle">Failed to load</p>
                                <p class="bannerText">{{ fetchError }}</p>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                type="button"
                                @click="fetchDetail"
                            >
                                Retry
                            </Button>
                        </div>

                        <!-- Content -->
                        <template v-else-if="detail">
                            <!-- Summary KPI cards -->
                            <div class="kpiRow">
                                <article class="kpiCard">
                                    <p class="kpiValue">
                                        {{ detail.totalFiles }}
                                    </p>
                                    <p class="kpiLabel">Files</p>
                                </article>
                                <article class="kpiCard">
                                    <p class="kpiValue">
                                        {{ detail.newTransactions }}
                                    </p>
                                    <p class="kpiLabel">New txns</p>
                                </article>
                                <article class="kpiCard">
                                    <p class="kpiValue">
                                        {{ detail.duplicateTransactions }}
                                    </p>
                                    <p class="kpiLabel">Duplicates</p>
                                </article>
                                <article
                                    v-if="detail.installmentSkipped > 0"
                                    class="kpiCard kpiCardWarning"
                                >
                                    <p class="kpiValue">
                                        {{ detail.installmentSkipped }}
                                    </p>
                                    <p class="kpiLabel">Inst. skipped</p>
                                </article>
                                <article
                                    class="kpiCard"
                                    :class="{
                                        kpiCardAlert: detail.failedFiles > 0,
                                    }"
                                >
                                    <p class="kpiValue">
                                        {{ detail.failedFiles }}
                                    </p>
                                    <p class="kpiLabel">Failed files</p>
                                </article>
                            </div>

                            <!-- Meta info row -->
                            <div class="importDetailMeta">
                                <div class="importDetailMetaItem">
                                    <span class="importDetailMetaLabel"
                                        >Account</span
                                    >
                                    <span class="importDetailMetaValue">
                                        {{ detail.accountId || "—" }}
                                    </span>
                                </div>
                                <div class="importDetailMetaItem">
                                    <span class="importDetailMetaLabel"
                                        >Created</span
                                    >
                                    <span class="importDetailMetaValue">{{
                                        formatDate(detail.createdAt)
                                    }}</span>
                                </div>
                                <div class="importDetailMetaItem">
                                    <span class="importDetailMetaLabel"
                                        >Last updated</span
                                    >
                                    <span class="importDetailMetaValue">{{
                                        formatDate(
                                            detail.completedAt ??
                                                detail.createdAt,
                                        )
                                    }}</span>
                                </div>
                                <div class="importDetailMetaItem">
                                    <span class="importDetailMetaLabel"
                                        >Completed files</span
                                    >
                                    <span class="importDetailMetaValue">{{
                                        detail.totalFiles - detail.failedFiles
                                    }}</span>
                                </div>
                            </div>

                            <!-- File list -->
                            <div class="stackSm">
                                <p class="fieldLabel">
                                    Files ({{ detail.files.length }})
                                </p>
                                <div v-if="detail.files.length" class="list">
                                    <importFileResultItem
                                        v-for="file in detail.files"
                                        :key="file.id"
                                        :file="{
                                            id: file.id,
                                            filename: file.filename,
                                            status: file.status,
                                            transactionsCount:
                                                file.transactionsCount,
                                            newCount: file.newCount,
                                            duplicateCount: file.duplicateCount,
                                            installmentSkipped:
                                                file.installmentSkipped,
                                            errorMessage: file.errorMessage,
                                        }"
                                    />
                                </div>
                                <div v-else class="emptyState">
                                    <p class="emptyStateTitle">No files</p>
                                    <p class="emptyStateText">
                                        This import has no associated files.
                                    </p>
                                </div>
                            </div>
                        </template>
                    </div>

                    <!-- ── Modal footer ── -->
                    <div class="modalFooter">
                        <Button
                            type="button"
                            variant="outline"
                            @click="emit('close')"
                        >
                            Close
                        </Button>
                    </div>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
/* ── Modal sizing override ────────────────────────────────── */
.importDetailModal {
    width: min(780px, 100%);
}

/* ── Header ──────────────────────────────────────────────── */
.modalTitle {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 900;
    letter-spacing: -0.02em;
}

/* ── Loading state ───────────────────────────────────────── */
.importDetailLoading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
    padding: var(--space-8);
    color: hsl(var(--muted-foreground));
}

/* ── KPI alert state ─────────────────────────────────────── */
.kpiCardAlert .kpiValue {
    color: hsl(var(--destructive));
}

/* ── KPI warning state ───────────────────────────────────── */
.kpiCardWarning .kpiValue {
    color: hsl(var(--warning));
}

/* ── Meta info grid ──────────────────────────────────────── */
.importDetailMeta {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--space-3);
    padding: var(--space-4);
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius-lg);
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.03),
            rgb(255 255 255 / 0.01)
        ),
        hsl(var(--card));
}

.importDetailMetaItem {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.importDetailMetaLabel {
    font-size: 0.78rem;
    font-weight: 700;
    color: hsl(var(--muted-foreground));
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.importDetailMetaValue {
    font-size: 0.88rem;
    font-weight: 600;
    word-break: break-all;
}

/* ── Spinner ─────────────────────────────────────────────── */
.spinner {
    color: hsl(var(--warning));
    animation: spin 0.9s linear infinite;
    transform-origin: center;
    flex-shrink: 0;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

/* ── Transition ──────────────────────────────────────────── */
.modalFade-enter-active,
.modalFade-leave-active {
    transition: opacity 0.18s ease;
}

.modalFade-enter-active .modal,
.modalFade-leave-active .modal {
    transition:
        transform 0.18s ease,
        opacity 0.18s ease;
}

.modalFade-enter-from,
.modalFade-leave-to {
    opacity: 0;
}

.modalFade-enter-from .modal,
.modalFade-leave-to .modal {
    transform: translateY(12px) scale(0.98);
    opacity: 0;
}
</style>
