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

    <h2 class="title">Nenhuma movimentação encontrada para este período.</h2>
    <p class="subtitle">
      Importe seus dados para começar a ver resumos, gráficos e status de cartões.
    </p>

    <div class="actions">
      <a class="primaryLink" href="/#/ingestion" aria-label="Ir para página de importação">
        Ir para importação
      </a>
      <a class="secondaryLink" href="/#/transactions" aria-label="Ir para página de transações">
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
  display: grid;
  gap: 1rem;
  place-items: center;
  text-align: center;
  padding: 2.5rem 1.25rem;
  border-radius: var(--radius-xl);
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.8);
  box-shadow: var(--shadow-sm);
}

.illustration {
  position: relative;
  width: min(420px, 100%);
  height: 220px;
}

.bubble {
  position: absolute;
  border-radius: 999px;
  background: hsl(var(--accent) / 0.18);
  border: 1px solid hsl(var(--border));
  filter: saturate(1.1);
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
  background: hsl(var(--info) / 0.14);
}
.b3 {
  width: 90px;
  height: 90px;
  left: 40%;
  bottom: 10%;
  background: hsl(var(--success) / 0.14);
}

.card {
  position: absolute;
  left: 50%;
  top: 55%;
  transform: translate(-50%, -50%);
  width: min(320px, 85%);
  padding: 1.1rem 1.1rem;
  border-radius: var(--radius-xl);
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.85);
  box-shadow: var(--shadow-sm);
}

.line {
  height: 12px;
  border-radius: 999px;
  background: hsl(var(--muted-foreground) / 0.18);
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
  background: linear-gradient(90deg, transparent, rgb(255 255 255 / 0.7), transparent);
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
  border: 1px solid hsl(var(--border));
  background: radial-gradient(circle at 35% 30%, rgb(59 130 246 / 0.18), transparent 45%);
}

@keyframes shimmer {
  0% {
    transform: translateX(0);
    opacity: 0.85;
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
}

.subtitle {
  margin: 0;
  color: hsl(var(--muted-foreground));
  max-width: 44ch;
  line-height: 1.6;
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
  border: 1px solid hsl(var(--border));
  transition:
    transform 160ms ease,
    background-color 160ms ease,
    border-color 160ms ease;
  font-weight: 650;
}

.primaryLink {
  background: hsl(var(--primary) / 0.12);
  color: hsl(var(--primary));
  border-color: hsl(var(--primary) / 0.22);
}

.primaryLink:hover {
  transform: translateY(-1px);
  background: hsl(var(--primary) / 0.18);
  border-color: hsl(var(--primary) / 0.35);
}

.secondaryLink {
  background: rgb(255 255 255 / 0.6);
  color: hsl(var(--foreground));
}

.secondaryLink:hover {
  transform: translateY(-1px);
  background: hsl(var(--accent) / 0.12);
  border-color: hsl(var(--accent) / 0.25);
}
</style>
