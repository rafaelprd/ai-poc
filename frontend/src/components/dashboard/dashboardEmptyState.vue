<template>
    <div class="emptyState" role="status" aria-live="polite">
        <div class="illustration" aria-hidden="true">
            <div class="bubble b1" />
            <div class="bubble b2" />
            <div class="bubble b3" />
            <div class="card">
                <div class="line l1" />
                <div class="line l2" />
                <div class="line l3" />
                <div class="line l4" />
            </div>
            <div class="wheel" />
        </div>

        <h2 class="title">
            Nenhuma movimentação encontrada para este período.
        </h2>
        <p class="subtitle">
            Importe seus dados para começar a ver resumos, gráficos e status de
            cartões.
        </p>

        <div class="actions">
            <a
                class="primaryLink"
                href="/#/ingestion"
                aria-label="Ir para página de importação"
            >
                Ir para importação
            </a>
            <a
                class="secondaryLink"
                href="/#/transactions"
                aria-label="Ir para página de transações"
            >
                Ver transações
            </a>
        </div>
    </div>
</template>

<script setup lang="ts">
/**
 * Empty state shown when selected period has zero transactions (SPEC5).
 * Routing is app-shell hash-based; links remain simple and non-blocking.
 */
</script>

<style scoped>
.emptyState {
    position: relative;
    display: grid;
    gap: 1rem;
    place-items: center;
    text-align: center;
    padding: 2.75rem 1.25rem;
    border-radius: var(--radius-xl);
    border: 1px solid rgb(255 255 255 / 0.08);
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.04),
            rgb(255 255 255 / 0.02)
        ),
        radial-gradient(circle at top, rgb(245 158 11 / 0.08), transparent 34%),
        hsl(var(--card));
    box-shadow:
        0 24px 70px rgb(0 0 0 / 0.28),
        inset 0 1px 0 rgb(255 255 255 / 0.04);
    overflow: hidden;
}

.emptyState::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(
        135deg,
        transparent 0%,
        rgb(255 255 255 / 0.05) 50%,
        transparent 100%
    );
    opacity: 0.7;
    pointer-events: none;
}

.illustration {
    position: relative;
    width: min(420px, 100%);
    height: 220px;
}

.bubble {
    position: absolute;
    border-radius: 999px;
    background:
        radial-gradient(
            circle at 35% 30%,
            rgb(255 255 255 / 0.14),
            transparent 50%
        ),
        hsl(var(--accent) / 0.2);
    border: 1px solid rgb(255 255 255 / 0.08);
    filter: saturate(1.05);
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.06);
}

.b1 {
    width: 110px;
    height: 110px;
    left: 10%;
    top: 15%;
}
.b2 {
    width: 70px;
    height: 70px;
    right: 10%;
    top: 10%;
    background:
        radial-gradient(
            circle at 35% 30%,
            rgb(255 255 255 / 0.12),
            transparent 50%
        ),
        hsl(var(--info) / 0.16);
}
.b3 {
    width: 90px;
    height: 90px;
    left: 40%;
    bottom: 10%;
    background:
        radial-gradient(
            circle at 35% 30%,
            rgb(255 255 255 / 0.12),
            transparent 50%
        ),
        hsl(var(--success) / 0.16);
}

.card {
    position: absolute;
    left: 50%;
    top: 55%;
    transform: translate(-50%, -50%);
    width: min(320px, 85%);
    padding: 1.1rem 1.1rem;
    border-radius: var(--radius-xl);
    border: 1px solid rgb(255 255 255 / 0.08);
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.06),
            rgb(255 255 255 / 0.03)
        ),
        hsl(var(--card));
    box-shadow:
        0 18px 42px rgb(0 0 0 / 0.22),
        inset 0 1px 0 rgb(255 255 255 / 0.04);
}

.line {
    height: 12px;
    border-radius: 999px;
    background: hsl(var(--muted-foreground) / 0.16);
    margin: 0.55rem 0;
    position: relative;
    overflow: hidden;
}

.line::after {
    content: "";
    position: absolute;
    top: 0;
    left: -40%;
    height: 100%;
    width: 40%;
    background: linear-gradient(
        90deg,
        transparent,
        rgb(255 255 255 / 0.55),
        transparent
    );
    animation: shimmer 1.2s ease-in-out infinite;
}

.l1 {
    width: 62%;
}
.l2 {
    width: 78%;
}
.l3 {
    width: 55%;
}
.l4 {
    width: 70%;
}

.wheel {
    position: absolute;
    left: 50%;
    top: 100%;
    transform: translate(-50%, -50%);
    width: 72px;
    height: 72px;
    border-radius: 999px;
    border: 1px solid rgb(255 255 255 / 0.08);
    background:
        radial-gradient(
            circle at 35% 30%,
            rgb(245 158 11 / 0.22),
            transparent 45%
        ),
        hsl(var(--card));
    box-shadow: inset 0 1px 0 rgb(255 255 255 / 0.04);
}

@keyframes shimmer {
    0% {
        transform: translateX(0);
        opacity: 0.75;
    }
    100% {
        transform: translateX(250%);
        opacity: 1;
    }
}

.title {
    margin: 0;
    font-size: 1.15rem;
    letter-spacing: -0.02em;
    color: hsl(var(--foreground));
}

.subtitle {
    margin: 0;
    color: hsl(var(--muted-foreground));
    max-width: 44ch;
    line-height: 1.65;
}

.actions {
    display: flex;
    gap: 0.85rem;
    flex-wrap: wrap;
    justify-content: center;
}

.primaryLink,
.secondaryLink {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.75rem 1.05rem;
    border-radius: 999px;
    border: 1px solid rgb(255 255 255 / 0.08);
    transition:
        transform 160ms ease,
        background-color 160ms ease,
        border-color 160ms ease,
        box-shadow 160ms ease;
    font-weight: 700;
}

.primaryLink {
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.08),
            rgb(255 255 255 / 0.03)
        ),
        hsl(var(--primary));
    color: hsl(var(--primary-foreground));
    border-color: hsl(var(--primary) / 0.22);
    box-shadow: 0 16px 32px hsl(var(--primary) / 0.18);
}

.primaryLink:hover {
    transform: translateY(-1px);
    border-color: hsl(var(--primary) / 0.35);
    box-shadow: 0 20px 36px hsl(var(--primary) / 0.22);
}

.secondaryLink {
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.05),
            rgb(255 255 255 / 0.02)
        ),
        hsl(var(--card));
    color: hsl(var(--foreground));
}

.secondaryLink:hover {
    transform: translateY(-1px);
    background: hsl(var(--accent) / 0.18);
    border-color: hsl(var(--accent) / 0.3);
}

@media (prefers-reduced-motion: no-preference) {
    .emptyState {
        animation: riseIn 420ms ease both;
    }

    .bubble,
    .wheel {
        animation: floaty 10s ease-in-out infinite;
    }

    .b2 {
        animation-delay: 300ms;
    }

    .b3 {
        animation-delay: 600ms;
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

@keyframes floaty {
    0%,
    100% {
        transform: translate3d(0, 0, 0);
    }
    50% {
        transform: translate3d(0, -10px, 0);
    }
}
</style>
