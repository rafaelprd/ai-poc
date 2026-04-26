<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { listInstallmentPlans } from "../../lib/api";
import type { InstallmentPlan, InstallmentEntry } from "../../lib/api";

const props = defineProps<{
    accountId: string;
}>();

// ── State ─────────────────────────────────────────────────────────────────────

const plans = ref<InstallmentPlan[]>([]);
const loading = ref(false);
const fetchError = ref<string | null>(null);

const currentPage = ref(1);
const pageSize = ref(20);
const totalItems = ref(0);
const totalPages = ref(0);

const expandedIds = ref<Set<number>>(new Set());

// ── Fetch ─────────────────────────────────────────────────────────────────────

async function fetchPlans(): Promise<void> {
    loading.value = true;
    fetchError.value = null;

    try {
        const result = await listInstallmentPlans({
            accountId: props.accountId,
            page: currentPage.value,
            pageSize: pageSize.value,
        });
        plans.value = result.items;
        totalItems.value = result.pagination.totalItems;
        totalPages.value = result.pagination.totalPages;
    } catch (err) {
        fetchError.value =
            err instanceof Error
                ? err.message
                : "Failed to load installment plans.";
    } finally {
        loading.value = false;
    }
}

function goToPage(page: number): void {
    if (page < 1 || page > totalPages.value) return;
    currentPage.value = page;
    fetchPlans();
}

// ── Expand / collapse ─────────────────────────────────────────────────────────

function toggleExpand(id: number): void {
    if (expandedIds.value.has(id)) {
        expandedIds.value.delete(id);
    } else {
        expandedIds.value.add(id);
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
    try {
        return new Intl.DateTimeFormat(undefined, {
            year: "numeric",
            month: "short",
            day: "2-digit",
        }).format(new Date(iso));
    } catch {
        return iso;
    }
}

function formatCurrency(value: number): string {
    return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: "BRL",
        minimumFractionDigits: 2,
    }).format(value);
}

function matchedCount(plan: InstallmentPlan): number {
    return plan.entries.filter((e) => e.status === "matched").length;
}

function entryStatusLabel(status: InstallmentEntry["status"]): string {
    switch (status) {
        case "pending":
            return "Pending";
        case "matched":
            return "Matched";
        case "skipped_duplicate":
            return "Skipped";
    }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
    if (props.accountId) fetchPlans();
});

watch(
    () => props.accountId,
    (newId) => {
        if (newId) {
            currentPage.value = 1;
            expandedIds.value = new Set();
            fetchPlans();
        }
    },
);
</script>

<template>
    <div class="panelRoot">
        <!-- ── Panel header ── -->
        <div class="panelHeader">
            <div class="panelHeaderText">
                <h2 class="panelTitle">Installment Plans</h2>
                <p class="panelDescription">
                    Recurring installment sequences tracked for this account.
                </p>
            </div>
            <button
                class="refreshBtn"
                type="button"
                :disabled="loading"
                aria-label="Refresh installment plans"
                @click="fetchPlans"
            >
                <svg
                    :class="['refreshIcon', { refreshIconSpin: loading }]"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.5"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                >
                    <polyline points="23 4 23 10 17 10" />
                    <polyline points="1 20 1 14 7 14" />
                    <path
                        d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"
                    />
                </svg>
            </button>
        </div>

        <div class="panelBody">
            <!-- ── Loading state ── -->
            <div v-if="loading && plans.length === 0" class="loadingState">
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
                    <circle cx="12" cy="12" r="10" stroke-opacity="0.2" />
                    <path d="M12 2a10 10 0 0 1 10 10" />
                </svg>
                <span class="helperText">Loading installment plans…</span>
            </div>

            <!-- ── Error state ── -->
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
                <button
                    class="retryBtn"
                    type="button"
                    @click="fetchPlans"
                >
                    Retry
                </button>
            </div>

            <!-- ── Empty state ── -->
            <div
                v-else-if="!loading && plans.length === 0"
                class="emptyState"
            >
                <div class="emptyStateIcon" aria-hidden="true">
                    <svg
                        width="32"
                        height="32"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.5"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                    >
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                        <line x1="16" y1="2" x2="16" y2="6" />
                        <line x1="8" y1="2" x2="8" y2="6" />
                        <line x1="3" y1="10" x2="21" y2="10" />
                    </svg>
                </div>
                <p class="emptyStateTitle">No installment plans</p>
                <p class="emptyStateText">
                    Installment sequences (e.g. "AMAZON 2/12") will appear here
                    after they are detected during file import.
                </p>
            </div>

            <!-- ── Plans table ── -->
            <template v-else>
                <div class="tableWrap">
                    <table class="table">
                        <thead>
                            <tr>
                                <th class="thExpand" aria-label="Expand" />
                                <th class="th">Description</th>
                                <th class="th thRight">Amount / inst.</th>
                                <th class="th thRight">Installments</th>
                                <th class="th">First date</th>
                                <th class="th thRight">Progress</th>
                            </tr>
                        </thead>
                        <tbody>
                            <template
                                v-for="plan in plans"
                                :key="plan.id"
                            >
                                <!-- ── Plan row ── -->
                                <tr
                                    class="planRow"
                                    :class="{
                                        planRowExpanded: expandedIds.has(
                                            plan.id,
                                        ),
                                    }"
                                    @click="toggleExpand(plan.id)"
                                >
                                    <td class="tdExpand">
                                        <span
                                            class="expandChevron"
                                            :class="{
                                                expandChevronOpen:
                                                    expandedIds.has(plan.id),
                                            }"
                                            aria-hidden="true"
                                        >
                                            <svg
                                                width="14"
                                                height="14"
                                                viewBox="0 0 24 24"
                                                fill="none"
                                                stroke="currentColor"
                                                stroke-width="2.5"
                                                stroke-linecap="round"
                                                stroke-linejoin="round"
                                            >
                                                <polyline
                                                    points="9 18 15 12 9 6"
                                                />
                                            </svg>
                                        </span>
                                    </td>
                                    <td class="td tdDesc">
                                        {{ plan.baseDescription }}
                                    </td>
                                    <td class="td tdRight">
                                        {{
                                            formatCurrency(
                                                plan.installmentAmount,
                                            )
                                        }}
                                    </td>
                                    <td class="td tdRight">
                                        {{ plan.totalInstallments }}
                                    </td>
                                    <td class="td">
                                        {{ formatDate(plan.firstDate) }}
                                    </td>
                                    <td class="td tdRight">
                                        <span
                                            class="progressChip"
                                            :class="{
                                                progressChipDone:
                                                    matchedCount(plan) ===
                                                    plan.totalInstallments,
                                                progressChipPartial:
                                                    matchedCount(plan) > 0 &&
                                                    matchedCount(plan) <
                                                        plan.totalInstallments,
                                            }"
                                        >
                                            {{ matchedCount(plan) }} /
                                            {{ plan.totalInstallments }}
                                            matched
                                        </span>
                                    </td>
                                </tr>

                                <!-- ── Expanded entries ── -->
                                <tr
                                    v-if="expandedIds.has(plan.id)"
                                    class="entriesRow"
                                >
                                    <td colspan="6" class="entriesTd">
                                        <div class="entriesWrap">
                                            <p class="entriesTitle">
                                                Installment entries
                                            </p>
                                            <div class="entriesTableWrap">
                                                <table class="entriesTable">
                                                    <thead>
                                                        <tr>
                                                            <th
                                                                class="eth ethRight"
                                                            >
                                                                #
                                                            </th>
                                                            <th class="eth">
                                                                Expected date
                                                            </th>
                                                            <th class="eth">
                                                                Status
                                                            </th>
                                                            <th
                                                                class="eth ethRight"
                                                            >
                                                                Transaction ID
                                                            </th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <tr
                                                            v-for="entry in plan.entries"
                                                            :key="entry.installmentNumber"
                                                            class="entryRow"
                                                        >
                                                            <td
                                                                class="etd etdRight etdNum"
                                                            >
                                                                {{
                                                                    entry.installmentNumber
                                                                }}
                                                            </td>
                                                            <td class="etd">
                                                                {{
                                                                    formatDate(
                                                                        entry.expectedDate,
                                                                    )
                                                                }}
                                                            </td>
                                                            <td class="etd">
                                                                <span
                                                                    class="statusBadge"
                                                                    :class="`statusBadge--${entry.status}`"
                                                                >
                                                                    {{
                                                                        entryStatusLabel(
                                                                            entry.status,
                                                                        )
                                                                    }}
                                                                </span>
                                                            </td>
                                                            <td
                                                                class="etd etdRight etdMuted"
                                                            >
                                                                {{
                                                                    entry.transactionId ??
                                                                    "—"
                                                                }}
                                                            </td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </div>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>

                <!-- ── Pagination ── -->
                <div v-if="totalPages > 1" class="pagination">
                    <span class="paginationInfo helperText">
                        {{ totalItems }} plan{{ totalItems !== 1 ? "s" : "" }}
                        &nbsp;·&nbsp; Page {{ currentPage }} of
                        {{ totalPages }}
                    </span>
                    <div class="paginationControls">
                        <button
                            class="pageBtn"
                            type="button"
                            :disabled="currentPage <= 1"
                            aria-label="Previous page"
                            @click="goToPage(currentPage - 1)"
                        >
                            <svg
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2.5"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                aria-hidden="true"
                            >
                                <polyline points="15 18 9 12 15 6" />
                            </svg>
                        </button>
                        <button
                            class="pageBtn"
                            type="button"
                            :disabled="currentPage >= totalPages"
                            aria-label="Next page"
                            @click="goToPage(currentPage + 1)"
                        >
                            <svg
                                width="14"
                                height="14"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2.5"
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                aria-hidden="true"
                            >
                                <polyline points="9 18 15 12 9 6" />
                            </svg>
                        </button>
                    </div>
                </div>

                <!-- Total hint when on single page -->
                <p
                    v-else-if="totalItems > 0"
                    class="helperText paginationSingle"
                >
                    {{ totalItems }} plan{{ totalItems !== 1 ? "s" : "" }}
                </p>
            </template>
        </div>
    </div>
</template>

<style scoped>
/* ── Panel shell ─────────────────────────────────────────── */
.panelRoot {
    display: grid;
    gap: 0;
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius-lg);
    background: hsl(var(--card));
    overflow: hidden;
}

/* ── Panel header ────────────────────────────────────────── */
.panelHeader {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-4);
    padding: var(--space-4) var(--space-5);
    border-bottom: 1px solid hsl(var(--border));
    background: linear-gradient(
        180deg,
        rgb(255 255 255 / 0.04),
        rgb(255 255 255 / 0.01)
    );
}

.panelHeaderText {
    display: grid;
    gap: var(--space-1);
}

.panelTitle {
    margin: 0;
    font-size: 1rem;
    font-weight: 800;
    letter-spacing: -0.02em;
}

.panelDescription {
    margin: 0;
    font-size: 0.84rem;
    color: hsl(var(--muted-foreground));
}

/* ── Refresh button ──────────────────────────────────────── */
.refreshBtn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius);
    background: transparent;
    color: hsl(var(--muted-foreground));
    cursor: pointer;
    transition:
        color 0.15s ease,
        border-color 0.15s ease,
        background 0.15s ease;
}

.refreshBtn:hover:not(:disabled) {
    color: hsl(var(--foreground));
    border-color: hsl(var(--ring));
    background: hsl(var(--ring) / 0.08);
}

.refreshBtn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
}

.refreshIcon {
    transition: transform 0.15s ease;
}

.refreshIconSpin {
    animation: spin 0.9s linear infinite;
    transform-origin: center;
}

/* ── Panel body ──────────────────────────────────────────── */
.panelBody {
    padding: var(--space-4) var(--space-5);
    display: grid;
    gap: var(--space-4);
}

/* ── Loading ─────────────────────────────────────────────── */
.loadingState {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
    padding: var(--space-8);
    color: hsl(var(--muted-foreground));
}

/* ── Retry button ────────────────────────────────────────── */
.retryBtn {
    flex-shrink: 0;
    padding: 0.25rem 0.75rem;
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius);
    background: transparent;
    color: hsl(var(--foreground));
    font-size: 0.84rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s ease;
}

.retryBtn:hover {
    background: hsl(var(--muted) / 0.5);
}

/* ── Empty state ─────────────────────────────────────────── */
.emptyState {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-10) var(--space-4);
    text-align: center;
}

.emptyStateIcon {
    color: hsl(var(--muted-foreground) / 0.5);
}

.emptyStateTitle {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 700;
}

.emptyStateText {
    margin: 0;
    font-size: 0.84rem;
    color: hsl(var(--muted-foreground));
    max-width: 36ch;
}

/* ── Table ───────────────────────────────────────────────── */
.tableWrap {
    overflow-x: auto;
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius-lg);
}

.table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}

.th,
.thExpand {
    padding: var(--space-2) var(--space-3);
    text-align: left;
    font-size: 0.75rem;
    font-weight: 700;
    color: hsl(var(--muted-foreground));
    text-transform: uppercase;
    letter-spacing: 0.04em;
    white-space: nowrap;
    border-bottom: 1px solid hsl(var(--border));
    background: linear-gradient(
        180deg,
        rgb(255 255 255 / 0.03),
        transparent
    );
}

.thExpand {
    width: 2rem;
    padding: var(--space-2) var(--space-2) var(--space-2) var(--space-3);
}

.thRight {
    text-align: right;
}

/* ── Plan rows ───────────────────────────────────────────── */
.planRow {
    cursor: pointer;
    transition: background 0.12s ease;
}

.planRow:hover {
    background: hsl(var(--muted) / 0.35);
}

.planRowExpanded {
    background: hsl(var(--muted) / 0.2);
}

.planRow:not(:last-child) {
    border-bottom: 1px solid hsl(var(--border) / 0.6);
}

.tdExpand {
    padding: var(--space-2) var(--space-2) var(--space-2) var(--space-3);
    width: 2rem;
    color: hsl(var(--muted-foreground));
}

.td {
    padding: var(--space-3) var(--space-3);
    vertical-align: middle;
}

.tdRight {
    text-align: right;
}

.tdDesc {
    font-weight: 600;
    max-width: 20rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* ── Expand chevron ──────────────────────────────────────── */
.expandChevron {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.18s ease;
}

.expandChevronOpen {
    transform: rotate(90deg);
}

/* ── Progress chip ───────────────────────────────────────── */
.progressChip {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
    background: hsl(var(--muted) / 0.5);
    color: hsl(var(--muted-foreground));
    white-space: nowrap;
}

.progressChipPartial {
    background: hsl(var(--warning) / 0.15);
    color: hsl(var(--warning));
}

.progressChipDone {
    background: hsl(var(--success) / 0.15);
    color: hsl(var(--success));
}

/* ── Entries expanded row ────────────────────────────────── */
.entriesRow {
    border-bottom: 1px solid hsl(var(--border) / 0.6);
}

.entriesTd {
    padding: 0;
}

.entriesWrap {
    padding: var(--space-3) var(--space-4) var(--space-4);
    background: hsl(var(--muted) / 0.15);
    display: grid;
    gap: var(--space-2);
}

.entriesTitle {
    margin: 0;
    font-size: 0.75rem;
    font-weight: 700;
    color: hsl(var(--muted-foreground));
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

/* ── Entries inner table ─────────────────────────────────── */
.entriesTableWrap {
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius);
    overflow: hidden;
}

.entriesTable {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.83rem;
}

.eth {
    padding: var(--space-2) var(--space-3);
    text-align: left;
    font-size: 0.72rem;
    font-weight: 700;
    color: hsl(var(--muted-foreground));
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid hsl(var(--border));
    background: linear-gradient(
        180deg,
        rgb(255 255 255 / 0.025),
        transparent
    );
}

.ethRight {
    text-align: right;
}

.etd {
    padding: var(--space-2) var(--space-3);
    vertical-align: middle;
    border-bottom: 1px solid hsl(var(--border) / 0.5);
}

.entriesTable tbody tr:last-child .etd {
    border-bottom: none;
}

.etdRight {
    text-align: right;
}

.etdNum {
    font-variant-numeric: tabular-nums;
    color: hsl(var(--muted-foreground));
    font-weight: 700;
    font-size: 0.78rem;
}

.etdMuted {
    color: hsl(var(--muted-foreground));
    font-size: 0.82rem;
}

/* ── Status badges ───────────────────────────────────────── */
.statusBadge {
    display: inline-block;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 700;
    white-space: nowrap;
}

.statusBadge--pending {
    background: hsl(var(--muted) / 0.6);
    color: hsl(var(--muted-foreground));
}

.statusBadge--matched {
    background: hsl(var(--success) / 0.15);
    color: hsl(var(--success));
}

.statusBadge--skipped_duplicate {
    background: hsl(var(--warning) / 0.15);
    color: hsl(var(--warning));
}

/* ── Pagination ──────────────────────────────────────────── */
.pagination {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding-top: var(--space-2);
}

.paginationInfo {
    flex: 1;
}

.paginationControls {
    display: flex;
    gap: var(--space-1);
}

.pageBtn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius);
    background: transparent;
    color: hsl(var(--foreground));
    cursor: pointer;
    transition:
        background 0.12s ease,
        border-color 0.12s ease;
}

.pageBtn:hover:not(:disabled) {
    background: hsl(var(--muted) / 0.5);
    border-color: hsl(var(--ring));
}

.pageBtn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
}

.paginationSingle {
    padding-top: var(--space-1);
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
</style>
