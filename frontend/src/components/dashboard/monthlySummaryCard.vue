<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
    totalExpenses: number;
    totalIncome: number;
    net: number;
}>();

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

const netVariant = computed(() => (props.net >= 0 ? "positive" : "negative"));
const netLabel = computed(() =>
    props.net >= 0 ? "Saldo Líquido" : "Saldo Líquido (negativo)",
);
</script>

<template>
    <section class="monthlySummary" aria-label="Resumo mensal">
        <div class="metric metricExpenses" aria-label="Total de despesas">
            <div class="metricAccent" aria-hidden="true" />
            <div class="metricLabel">Despesas</div>
            <div class="metricValue dangerText">
                {{ formatMoney(totalExpenses) }}
            </div>
            <p class="metricHint">Fluxo saindo da mesa.</p>
        </div>

        <div class="metric metricIncome" aria-label="Total de receitas">
            <div class="metricAccent" aria-hidden="true" />
            <div class="metricLabel">Receitas</div>
            <div class="metricValue successText">
                {{ formatMoney(totalIncome) }}
            </div>
            <p class="metricHint">Fluxo entrando no livro.</p>
        </div>

        <div class="metric metricNet" aria-label="Saldo líquido">
            <div class="metricAccent" aria-hidden="true" />
            <div class="metricLabel">{{ netLabel }}</div>
            <div
                class="metricValue"
                :class="
                    netVariant === 'positive' ? 'positiveText' : 'negativeText'
                "
            >
                {{ formatMoney(net) }}
            </div>
            <p class="metricHint">
                {{
                    netVariant === "positive"
                        ? "Terreno acima do zero."
                        : "Saldo abaixo do zero."
                }}
            </p>
        </div>
    </section>
</template>

<style scoped>
.monthlySummary {
    display: grid;
    gap: 1rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    align-items: stretch;
}

.metric {
    position: relative;
    padding: 1.05rem 1.05rem 1rem;
    border-radius: var(--radius-xl);
    border: 1px solid rgb(255 255 255 / 0.08);
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.06),
            rgb(255 255 255 / 0.02)
        ),
        hsl(var(--card));
    box-shadow:
        0 18px 48px rgb(0 0 0 / 0.22),
        inset 0 1px 0 rgb(255 255 255 / 0.04);
    overflow: hidden;
    min-width: 0;
}

.metric::before {
    content: "";
    position: absolute;
    inset: 0;
    background:
        radial-gradient(
            circle at top right,
            rgb(245 158 11 / 0.08),
            transparent 38%
        ),
        radial-gradient(
            circle at bottom left,
            rgb(59 130 246 / 0.06),
            transparent 32%
        );
    pointer-events: none;
}

.metricAccent {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    height: 4px;
    background: linear-gradient(90deg, hsl(var(--primary)), hsl(221 83% 60%));
}

.metricExpenses .metricAccent {
    background: linear-gradient(
        90deg,
        hsl(var(--destructive)),
        hsl(38 92% 62%)
    );
}

.metricIncome .metricAccent {
    background: linear-gradient(90deg, hsl(var(--success)), hsl(199 92% 58%));
}

.metricNet .metricAccent {
    background: linear-gradient(90deg, hsl(38 92% 62%), hsl(221 83% 60%));
}

.metricLabel {
    position: relative;
    z-index: 1;
    color: hsl(var(--muted-foreground));
    font-size: 0.84rem;
    margin-bottom: 0.4rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.metricValue {
    position: relative;
    z-index: 1;
    font-size: 1.55rem;
    font-weight: 900;
    letter-spacing: -0.05em;
    line-height: 1.1;
}

.metricHint {
    position: relative;
    z-index: 1;
    margin: 0.45rem 0 0;
    color: hsl(var(--muted-foreground));
    font-size: 0.88rem;
    line-height: 1.45;
}

.dangerText {
    color: hsl(var(--destructive));
}

.successText {
    color: hsl(var(--success));
}

.positiveText {
    color: hsl(var(--success));
}

.negativeText {
    color: hsl(var(--destructive));
}

@media (max-width: 1023px) {
    .monthlySummary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 767px) {
    .monthlySummary {
        grid-template-columns: 1fr;
    }
}

@media (prefers-reduced-motion: no-preference) {
    .metric {
        animation: fadeRise 420ms ease both;
    }

    .metric:nth-child(2) {
        animation-delay: 70ms;
    }

    .metric:nth-child(3) {
        animation-delay: 140ms;
    }
}

@keyframes fadeRise {
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
