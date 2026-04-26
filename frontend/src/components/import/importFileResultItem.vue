<script setup lang="ts">
import { computed } from "vue";
import Badge from "../ui/Badge.vue";

const props = defineProps<{
    file: {
        id: number;
        filename: string;
        status: string;
        transactionsCount: number;
        newCount: number;
        duplicateCount: number;
        installmentSkipped: number;
        errorMessage: string | null;
    };
}>();

type BadgeVariant =
    | "default"
    | "secondary"
    | "success"
    | "warning"
    | "destructive";

const statusVariant = computed((): BadgeVariant => {
    switch (props.file.status) {
        case "completed":
            return "success";
        case "failed":
            return "destructive";
        case "processing":
            return "warning";
        default:
            return "secondary";
    }
});

const statusLabel = computed(() => {
    switch (props.file.status) {
        case "pending":
            return "Pending";
        case "processing":
            return "Processing";
        case "completed":
            return "Completed";
        case "failed":
            return "Failed";
        default:
            return props.file.status;
    }
});

const isFailed = computed(() => props.file.status === "failed");
const isCompleted = computed(() => props.file.status === "completed");
</script>

<template>
    <div
        class="resultItem"
        :class="{
            resultItemCompleted: isCompleted,
            resultItemFailed: isFailed,
        }"
    >
        <!-- Leading file icon -->
        <div class="resultItemIcon" aria-hidden="true">
            <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
            >
                <path
                    d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                />
                <polyline points="14 2 14 8 20 8" />
            </svg>
        </div>

        <!-- Main body -->
        <div class="resultItemBody">
            <!-- Top row: filename + badge -->
            <div class="resultItemHeader">
                <span class="resultItemName truncate">{{ file.filename }}</span>
                <Badge :variant="statusVariant">{{ statusLabel }}</Badge>
            </div>

            <!-- Count row — always rendered for completed; omitted when pending with no data -->
            <div class="resultItemCounts">
                <span class="countGroup">
                    <span class="countValue">{{ file.transactionsCount }}</span>
                    <span class="countLabel">total</span>
                </span>

                <span class="countDivider" aria-hidden="true" />

                <span class="countGroup countGroupNew">
                    <span class="countValue">{{ file.newCount }}</span>
                    <span class="countLabel">new</span>
                </span>

                <span class="countDivider" aria-hidden="true" />

                <span class="countGroup countGroupDup">
                    <span class="countValue">{{ file.duplicateCount }}</span>
                    <span class="countLabel">duplicate</span>
                </span>

                <template v-if="file.installmentSkipped > 0">
                    <span class="countDivider" aria-hidden="true" />
                    <span class="countGroup countGroupInstSkipped">
                        <span class="countValue">{{
                            file.installmentSkipped
                        }}</span>
                        <span class="countLabel">installment skipped</span>
                    </span>
                </template>
            </div>

            <!-- Error message -->
            <p
                v-if="isFailed && file.errorMessage"
                class="resultItemError errorText"
            >
                {{ file.errorMessage }}
            </p>
        </div>
    </div>
</template>

<style scoped>
/* ── Shell ───────────────────────────────────────────────── */
.resultItem {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
    padding: var(--space-3) var(--space-4);
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius-lg);
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.04),
            rgb(255 255 255 / 0.01)
        ),
        hsl(var(--card));
    transition: border-color 0.16s ease;
}

.resultItemCompleted {
    border-color: hsl(var(--success) / 0.28);
}

.resultItemFailed {
    border-color: hsl(var(--destructive) / 0.28);
}

/* ── Leading icon ────────────────────────────────────────── */
.resultItemIcon {
    flex-shrink: 0;
    margin-top: 0.15rem;
    color: hsl(var(--muted-foreground));
}

/* ── Body ────────────────────────────────────────────────── */
.resultItemBody {
    flex: 1;
    min-width: 0;
    display: grid;
    gap: var(--space-2);
}

/* ── Header row ──────────────────────────────────────────── */
.resultItemHeader {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
}

.resultItemName {
    font-size: 0.9rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    min-width: 0;
}

/* ── Count chips ─────────────────────────────────────────── */
.resultItemCounts {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
}

.countGroup {
    display: inline-flex;
    align-items: baseline;
    gap: 0.3rem;
    font-size: 0.82rem;
}

.countValue {
    font-weight: 800;
    font-size: 0.9rem;
    letter-spacing: -0.02em;
}

.countLabel {
    color: hsl(var(--muted-foreground));
}

.countGroupNew .countValue {
    color: hsl(var(--success));
}

.countGroupDup .countValue {
    color: hsl(var(--muted-foreground));
}

.countGroupInstSkipped .countValue {
    color: hsl(var(--warning));
}

.countDivider {
    display: inline-block;
    width: 1px;
    height: 0.85rem;
    background: hsl(var(--border));
    flex-shrink: 0;
}

/* ── Error text ──────────────────────────────────────────── */
.resultItemError {
    margin: 0;
    font-size: 0.84rem;
    line-height: 1.5;
}
</style>
