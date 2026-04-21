<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type {
    MonthlySummaryResponse,
    CategoryBreakdownResponse,
    TimeSeriesResponse,
    CardTrackingResponse,
    PeriodParams,
} from "../../lib/api";

import monthYearSelector from "./monthYearSelector.vue";
import monthlySummaryCard from "./monthlySummaryCard.vue";
import categoryPieChart from "./categoryPieChart.vue";
import categoryBreakdownTable from "./categoryBreakdownTable.vue";
import spendingTimeSeriesChart from "./spendingTimeSeriesChart.vue";
import cardTrackingPanel from "./cardTrackingPanel.vue";
import upcomingPaymentsList from "./upcomingPaymentsList.vue";
import dashboardSkeleton from "./dashboardSkeleton.vue";
import dashboardEmptyState from "./dashboardEmptyState.vue";
import { dashboardApi } from "../../lib/api";

type MonthYear = { month: number; year: number };

const today = new Date();
const selected = ref<MonthYear>({
    month: today.getMonth() + 1,
    year: today.getFullYear(),
});

const loading = ref(false);
const error = ref<{ code?: string; message?: string } | null>(null);

const monthlySummary = ref<MonthlySummaryResponse | null>(null);
const categoryBreakdown = ref<CategoryBreakdownResponse | null>(null);
const dailyTimeSeries = ref<TimeSeriesResponse | null>(null);
const monthlyTimeSeries = ref<TimeSeriesResponse | null>(null);
const cardTracking = ref<CardTrackingResponse | null>(null);

let runId = 0;

function periodParams(): PeriodParams {
    return {
        month: selected.value.month,
        year: selected.value.year,
    };
}

async function fetchAll() {
    const myRun = ++runId;
    loading.value = true;
    error.value = null;

    const params = periodParams();

    try {
        const [m, c, daily, monthly, cards] = await Promise.all([
            dashboardApi.getMonthlySummary(params),
            dashboardApi.getCategoryBreakdown(params),
            dashboardApi.getTimeSeries({
                ...params,
                granularity: "daily",
            }),
            dashboardApi.getTimeSeries({
                ...params,
                granularity: "monthly",
                monthsBack: 12,
            }),
            dashboardApi.getCardTracking(params),
        ]);

        if (myRun !== runId) return;

        monthlySummary.value = m;
        categoryBreakdown.value = c;
        dailyTimeSeries.value = daily;
        monthlyTimeSeries.value = monthly;
        cardTracking.value = cards;
    } catch (e: any) {
        if (myRun !== runId) return;
        error.value = {
            code: e?.code,
            message: e?.message ?? "Falha ao carregar dashboard.",
        };
    } finally {
        if (myRun === runId) loading.value = false;
    }
}

watch(
    selected,
    () => {
        fetchAll();
    },
    { deep: true, immediate: true },
);

const dashboardIsEmpty = computed(() => {
    const m = monthlySummary.value;
    const c = categoryBreakdown.value;
    const d = dailyTimeSeries.value;
    const mo = monthlyTimeSeries.value;
    const cards = cardTracking.value;

    const noExpenses =
        !m ||
        (m.total_expenses === 0 &&
            (!m.categories || m.categories.length === 0));

    const noCategoryPie =
        !c ||
        ((c.slices?.length ?? 0) === 0 && (c.uncategorized_total ?? 0) === 0);

    const noTimeSeries =
        (!d || (d.cumulative_expenses ?? 0) === 0) &&
        (!mo ||
            ((mo.cumulative_income ?? 0) === 0 &&
                (mo.cumulative_expenses ?? 0) === 0));

    const noCards =
        !cards ||
        ((cards.cards?.length ?? 0) === 0 &&
            (cards.upcoming_payments?.length ?? 0) === 0 &&
            (cards.total_card_debt ?? 0) === 0);

    return noExpenses && noCategoryPie && noTimeSeries && noCards;
});

const tableCategories = computed(() => {
    const c = categoryBreakdown.value;
    if (!c) return [];

    const rows: Array<{
        category_id: number | null;
        category_name: string;
        total: number;
        percentage: number;
        transaction_count?: number;
        color: string;
    }> = [];

    for (const s of c.slices ?? []) {
        rows.push({
            category_id: s.category_id,
            category_name: s.category_name ?? "Sem Categoria",
            total: s.total ?? 0,
            percentage: s.percentage ?? 0,
            color: s.color ?? "#9E9E9E",
            // SPEC5 table wants transaction_count; our category-breakdown response doesn't provide it.
            // Keep it undefined; UI will fallback to 0.
        });
    }

    if (
        (c.uncategorized_total ?? 0) > 0 ||
        (c.uncategorized_percentage ?? 0) > 0
    ) {
        rows.push({
            category_id: null,
            category_name: "Sem Categoria",
            total: c.uncategorized_total ?? 0,
            percentage: c.uncategorized_percentage ?? 0,
            color: "#9E9E9E",
        });
    }

    return rows;
});
</script>

<template>
    <section class="dashboardSection" aria-label="Dashboard (SPEC5)">
        <div class="topControls">
            <monthYearSelector v-model="selected" />
        </div>

        <dashboardSkeleton v-if="loading" />

        <div v-else-if="dashboardIsEmpty" class="emptyWrap">
            <dashboardEmptyState />
        </div>

        <div v-else class="grid">
            <div class="metricsRow">
                <monthlySummaryCard
                    :total-expenses="monthlySummary?.total_expenses ?? 0"
                    :total-income="monthlySummary?.total_income ?? 0"
                    :net="monthlySummary?.net ?? 0"
                />
            </div>

            <div class="row2">
                <div class="panel">
                    <categoryPieChart
                        :slices="categoryBreakdown?.slices ?? []"
                        :uncategorized-total="
                            categoryBreakdown?.uncategorized_total ?? 0
                        "
                        :uncategorized-percentage="
                            categoryBreakdown?.uncategorized_percentage ?? 0
                        "
                    />
                </div>

                <div class="panel">
                    <categoryBreakdownTable
                        :categories="tableCategories"
                        aria-label="Tabela de distribuição por categoria"
                    />
                </div>
            </div>

            <div class="rowFull">
                <spendingTimeSeriesChart
                    :daily-data-points="
                        (dailyTimeSeries?.data_points ?? []) as any
                    "
                    :monthly-data-points="
                        (monthlyTimeSeries?.data_points ?? []) as any
                    "
                    initial-granularity="daily"
                    aria-label-prefix="Gastos e receitas"
                />
            </div>

            <div class="rowBottom">
                <cardTrackingPanel :cards="cardTracking?.cards ?? []" />
                <upcomingPaymentsList
                    :payments="cardTracking?.upcoming_payments ?? []"
                />
            </div>

            <div
                v-if="error"
                class="errorBar"
                role="alert"
                aria-live="assertive"
            >
                <strong>Erro:</strong>
                {{ error.message }}
            </div>
        </div>
    </section>
</template>

<style scoped>
.dashboardSection {
    display: grid;
    gap: 1rem;
}

.topControls {
    display: flex;
    justify-content: flex-start;
    align-items: center;
}

.grid {
    display: grid;
    gap: 1.25rem;
}

.metricsRow {
    display: grid;
    gap: 1rem;
}

.row2 {
    display: grid;
    gap: 1.25rem;
    grid-template-columns: 1fr 1fr;
    align-items: start;
}

.rowFull {
    min-width: 0;
}

.rowBottom {
    display: grid;
    gap: 1.25rem;
    grid-template-columns: 1fr 1fr;
    align-items: start;
}

.panel {
    min-width: 0;
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.05),
            rgb(255 255 255 / 0.02)
        ),
        hsl(var(--card));
    backdrop-filter: blur(16px);
    border: 1px solid rgb(255 255 255 / 0.06);
    border-radius: var(--radius-xl);
    box-shadow:
        0 20px 60px rgb(0 0 0 / 0.28),
        inset 0 1px 0 rgb(255 255 255 / 0.03);
    overflow: clip;
}

.emptyWrap {
    display: grid;
    place-items: center;
}

.errorBar {
    border: 1px solid hsl(var(--destructive) / 0.25);
    background: hsl(var(--destructive) / 0.1);
    padding: 0.9rem 1rem;
    border-radius: var(--radius-xl);
    font-weight: 800;
    color: hsl(var(--destructive));
    backdrop-filter: blur(10px);
}

@media (max-width: 1023px) {
    .row2 {
        grid-template-columns: 1fr;
    }
    .rowBottom {
        grid-template-columns: 1fr;
    }
}
</style>
