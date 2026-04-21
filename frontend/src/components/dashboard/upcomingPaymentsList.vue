<script setup lang="ts">
import { computed } from "vue";
import type { UpcomingPayment } from "../../lib/api";

const props = defineProps<{
    payments: UpcomingPayment[];
    ariaLabel?: string;
}>();

const paymentsSorted = computed(() => {
    const list = Array.isArray(props.payments) ? props.payments : [];
    return [...list].sort((a, b) => {
        const da = String(a?.due_date ?? "");
        const db = String(b?.due_date ?? "");
        if (da < db) return -1;
        if (da > db) return 1;
        return 0;
    });
});

const panelAria = computed(
    () => props.ariaLabel ?? "Lista de pagamentos futuros de cartões",
);

const brl = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

function formatMoney(v: number) {
    if (!Number.isFinite(v)) return "—";
    return brl.format(v);
}

function pad2(n: number) {
    return String(n).padStart(2, "0");
}

function formatDate(iso: string) {
    if (!iso || typeof iso !== "string") return "—";
    const [y, m, d] = iso.split("-").map((x) => Number(x));
    if (!y || !m || !d) return iso;
    return `${pad2(d)}/${pad2(m)}/${y}`;
}

function daysLabel(daysUntilDue: number) {
    const n = Number(daysUntilDue);
    if (!Number.isFinite(n)) return "—";
    if (n === 0) return "vence hoje";
    if (n < 0) {
        const k = Math.abs(n);
        return `vencido há ${k} dia${k === 1 ? "" : "s"}`;
    }
    return `em ${n} dia${n === 1 ? "" : "s"}`;
}
</script>

<template>
    <section class="panel" :aria-label="panelAria">
        <header class="panelHeader">
            <div>
                <h2 class="panelTitle">Próximos vencimentos</h2>
                <p class="panelDescription">
                    Ordenado por data. Alertas em vermelho.
                </p>
            </div>

            <div class="panelHeaderRight" aria-hidden="true">
                {{ paymentsSorted.length }} item{{
                    paymentsSorted.length === 1 ? "" : "s"
                }}
            </div>
        </header>

        <div class="panelBody">
            <div
                v-if="paymentsSorted.length === 0"
                class="empty"
                role="status"
                aria-live="polite"
            >
                <div class="emptyTitle">Sem pagamentos próximos</div>
                <div class="emptySub">
                    Nada para vencer no período selecionado.
                </div>
            </div>

            <ul v-else class="list" aria-label="Lista de pagamentos">
                <li
                    v-for="p in paymentsSorted"
                    :key="String(p.account_id) + ':' + String(p.due_date)"
                    class="row"
                    :class="{ rowUrgent: !!p.is_urgent }"
                    role="listitem"
                    :aria-label="`Cartão ${p.account_name}. Vence em ${formatDate(p.due_date)}. Valor ${formatMoney(p.amount)}.`"
                >
                    <div class="rowLeft">
                        <span
                            v-if="p.is_urgent"
                            class="warnIcon"
                            aria-hidden="true"
                            title="Urgente"
                        >
                            ⚠
                        </span>

                        <div class="rowText">
                            <div class="rowTitle">
                                {{ p.account_name }}
                            </div>

                            <div class="rowMeta">
                                <span class="metaItem">
                                    <span class="metaLabel">Venc.</span>
                                    <span class="metaValue">{{
                                        formatDate(p.due_date)
                                    }}</span>
                                </span>

                                <span class="metaItem">
                                    <span class="metaLabel">Quando.</span>
                                    <span class="metaValue">{{
                                        daysLabel(p.days_until_due)
                                    }}</span>
                                </span>
                            </div>
                        </div>
                    </div>

                    <div class="rowRight">
                        <div class="amount">{{ formatMoney(p.amount) }}</div>

                        <div
                            v-if="p.is_urgent"
                            class="urgentPill"
                            :aria-label="`Urgente: vence em ${daysLabel(p.days_until_due)}`"
                        >
                            Urgente
                        </div>
                    </div>
                </li>
            </ul>
        </div>
    </section>
</template>

<style scoped>
.panel {
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.05),
            rgb(255 255 255 / 0.02)
        ),
        hsl(var(--card));
    backdrop-filter: blur(16px);
    border: 1px solid rgb(255 255 255 / 0.08);
    border-radius: var(--radius-xl);
    box-shadow:
        0 20px 60px rgb(0 0 0 / 0.28),
        inset 0 1px 0 rgb(255 255 255 / 0.04);
    overflow: clip;
}

.panelHeader {
    padding: var(--space-5) var(--space-6);
    border-bottom: 1px solid rgb(255 255 255 / 0.06);
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: var(--space-3);
    align-items: center;
    background: linear-gradient(
        180deg,
        rgb(255 255 255 / 0.04),
        rgb(255 255 255 / 0.015)
    );
}

.panelTitle {
    margin: 0;
    font-size: 1.05rem;
    letter-spacing: -0.03em;
    line-height: 1.1;
    color: hsl(210 40% 98%);
    font-family:
        "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
}

.panelDescription {
    margin: 0.35rem 0 0;
    color: rgb(226 232 240 / 0.72);
    font-size: 0.94rem;
    line-height: 1.55;
}

.panelHeaderRight {
    color: hsl(38 92% 62%);
    font-weight: 900;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-size: 0.82rem;
}

.panelBody {
    padding: var(--space-6);
}

.empty {
    display: grid;
    gap: 0.35rem;
    padding: 1rem 0.25rem;
}

.emptyTitle {
    font-weight: 950;
    letter-spacing: -0.02em;
    color: hsl(var(--foreground));
}

.emptySub {
    color: hsl(var(--muted-foreground));
    font-weight: 750;
    line-height: 1.6;
}

.list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: var(--space-3);
}

.row {
    display: flex;
    justify-content: space-between;
    gap: var(--space-4);
    align-items: flex-start;
    border: 1px solid hsl(var(--border));
    border-radius: var(--radius-xl);
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.04),
            rgb(255 255 255 / 0.02)
        ),
        hsl(var(--card));
    padding: 0.95rem 1rem;
    transition:
        transform 160ms ease,
        border-color 160ms ease,
        background-color 160ms ease,
        box-shadow 160ms ease;
}

.row:hover {
    transform: translateY(-1px);
    border-color: rgb(245 158 11 / 0.24);
    box-shadow: var(--shadow-md);
}

.rowUrgent {
    border-color: hsl(var(--destructive) / 0.35);
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.04),
            rgb(255 255 255 / 0.02)
        ),
        hsl(var(--destructive) / 0.09);
}

.rowLeft {
    display: flex;
    gap: 0.85rem;
    align-items: flex-start;
    min-width: 0;
}

.warnIcon {
    flex: 0 0 auto;
    font-size: 1.2rem;
    filter: saturate(1.1);
    margin-top: 0.1rem;
}

.rowText {
    display: grid;
    gap: 0.25rem;
    min-width: 0;
}

.rowTitle {
    font-weight: 1000;
    letter-spacing: -0.02em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 320px;
    color: hsl(var(--foreground));
}

.rowMeta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    color: hsl(var(--muted-foreground));
    font-weight: 800;
    font-size: 0.9rem;
}

.metaItem {
    display: inline-flex;
    gap: 0.35rem;
    align-items: baseline;
}

.metaLabel {
    color: hsl(var(--muted-foreground) / 0.95);
    font-weight: 900;
}

.metaValue {
    color: hsl(var(--foreground));
    font-weight: 950;
}

.rowRight {
    display: grid;
    justify-items: end;
    gap: 0.6rem;
    flex: 0 0 auto;
}

.amount {
    font-weight: 1100;
    letter-spacing: -0.02em;
    font-size: 1.1rem;
    white-space: nowrap;
    color: hsl(var(--foreground));
}

.urgentPill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.4rem 0.65rem;
    border-radius: 999px;
    border: 1px solid hsl(var(--destructive) / 0.35);
    background: hsl(var(--destructive) / 0.12);
    color: hsl(var(--destructive));
    font-weight: 950;
    font-size: 0.9rem;
    white-space: nowrap;
}

@media (max-width: 767px) {
    .row {
        flex-direction: column;
        align-items: stretch;
    }

    .rowRight {
        justify-items: start;
    }

    .rowTitle {
        max-width: 100%;
    }
}

@media (prefers-reduced-motion: no-preference) {
    .panel,
    .row {
        animation: riseIn 420ms ease both;
    }
}

@keyframes riseIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}
</style>
