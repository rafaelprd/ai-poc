<script setup lang="ts">
import { computed } from 'vue'
import type { CardInvoice, CardInvoiceStatus } from '../../lib/api'

const props = defineProps<{
  cards: CardInvoice[]
  ariaLabel?: string
}>()

const cards = computed(() => Array.isArray(props.cards) ? props.cards : [])

const brl = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function formatMoney(v: number) {
  if (!Number.isFinite(v)) return '—'
  return brl.format(v)
}

function pad2(n: number) {
  return String(n).padStart(2, '0')
}

function formatDate(iso: string) {
  if (!iso || typeof iso !== 'string') return '—'
  // Expect YYYY-MM-DD
  const [y, m, d] = iso.split('-').map((x) => Number(x))
  if (!y || !m || !d) return iso
  return `${pad2(d)}/${pad2(m)}/${y}`
}

function statusLabel(status: CardInvoiceStatus) {
  switch (status) {
    case 'open':
      return 'Em aberto'
    case 'closed':
      return 'Faturado'
    case 'paid':
      return 'Pago'
    case 'overdue':
      return 'Atrasado'
    default:
      return status
  }
}

function daysLabel(status: CardInvoiceStatus, daysUntilDue: number) {
  const n = Number(daysUntilDue)
  if (!Number.isFinite(n)) return '—'

  if (status === 'paid') return '—'
  if (status === 'overdue') return `Vencido há ${Math.abs(n)} dia${Math.abs(n) === 1 ? '' : 's'}`
  if (status === 'closed') return `Vence em ${n} dia${n === 1 ? '' : 's'}`
  if (status === 'open') return `Vence em ${n} dia${n === 1 ? '' : 's'}`
  return `Em ${n} dia${n === 1 ? '' : 's'}`
}

function statusTone(status: CardInvoiceStatus) {
  switch (status) {
    case 'open':
      return {
        bg: 'hsl(var(--info) / 0.14)',
        fg: 'hsl(var(--info))',
        bd: 'hsl(var(--info) / 0.28)',
      }
    case 'closed':
      return {
        bg: 'hsl(var(--warning) / 0.14)',
        fg: 'hsl(var(--warning))',
        bd: 'hsl(var(--warning) / 0.28)',
      }
    case 'paid':
      return {
        bg: 'hsl(var(--success) / 0.14)',
        fg: 'hsl(var(--success))',
        bd: 'hsl(var(--success) / 0.28)',
      }
    case 'overdue':
      return {
        bg: 'hsl(var(--destructive) / 0.14)',
        fg: 'hsl(var(--destructive))',
        bd: 'hsl(var(--destructive) / 0.28)',
      }
    default:
      return {
        bg: 'hsl(var(--muted-foreground) / 0.12)',
        fg: 'hsl(var(--muted-foreground))',
        bd: 'hsl(var(--muted-foreground) / 0.22)',
      }
  }
}

const panelAria = computed(() => props.ariaLabel ?? 'Painel de faturas de cartões')
</script>

<template>
  <section class="panel" :aria-label="panelAria">
    <header class="panelHeader">
      <div>
        <h2 class="panelTitle">Cartões</h2>
        <p class="panelDescription">Totais e vencimentos por cartão</p>
      </div>

      <div v-if="cards.length" class="panelHeaderRight" aria-hidden="true">
        {{ cards.length }} cartão{{ cards.length === 1 ? '' : 's' }}
      </div>
      <div v-else class="panelHeaderRight" aria-hidden="true">
        Nenhum cartão ativo
      </div>
    </header>

    <div class="panelBody">
      <div v-if="!cards.length" class="empty">
        <div class="emptyTitle">Nenhuma fatura para exibir</div>
        <div class="emptySub">Cadastre contas do tipo cartão de crédito para ver o status.</div>
      </div>

      <div v-else class="cardsGrid">
        <article
          v-for="card in cards"
          :key="String(card.account_id)"
          class="cardItem"
          :aria-label="`Cartão ${card.account_name}`"
        >
          <div class="cardTop">
            <div class="cardNameBlock">
              <div class="cardName">{{ card.account_name }}</div>
              <div class="cardMeta">
                <span class="muted">Transações:</span> <strong>{{ card.transaction_count ?? 0 }}</strong>
              </div>
            </div>

            <div class="statusWrap">
              <span
                class="statusBadge"
                :style="{
                  backgroundColor: statusTone(card.status).bg,
                  color: statusTone(card.status).fg,
                  borderColor: statusTone(card.status).bd,
                }"
                :aria-label="`Status: ${statusLabel(card.status)}`"
              >
                {{ statusLabel(card.status) }}
              </span>
            </div>
          </div>

          <div class="cardAmounts">
            <div class="amountLabel">Fatura atual</div>
            <div class="amountValue">{{ formatMoney(card.current_invoice_total) }}</div>
          </div>

          <div class="datesGrid" role="group" aria-label="Datas da fatura">
            <div class="dateLine">
              <div class="dateLabel">Fechamento</div>
              <div class="dateValue">{{ formatDate(card.closing_date) }}</div>
            </div>
            <div class="dateLine">
              <div class="dateLabel">Vencimento</div>
              <div class="dateValue">{{ formatDate(card.due_date) }}</div>
            </div>
            <div class="dateLine span2">
              <div class="dateLabel">Resumo</div>
              <div class="dateValue">
                {{ daysLabel(card.status, card.days_until_due) }}
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel {
  background: rgb(255 255 255 / 0.9);
  backdrop-filter: blur(12px);
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  overflow: clip;
}

.panelHeader {
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid hsl(var(--border));
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: center;
  background: linear-gradient(
    180deg,
    rgb(255 255 255 / 0.96),
    rgb(248 250 252 / 0.92)
  );
}

.panelTitle {
  margin: 0;
  font-size: 1.05rem;
  letter-spacing: -0.02em;
}

.panelDescription {
  margin: 0.35rem 0 0;
  color: hsl(var(--muted-foreground));
  font-size: 0.94rem;
  line-height: 1.5;
}

.panelHeaderRight {
  color: hsl(var(--muted-foreground));
  font-weight: 850;
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
}

.emptySub {
  color: hsl(var(--muted-foreground));
  font-weight: 750;
  line-height: 1.6;
}

.cardsGrid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}

.cardItem {
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius-xl);
  background: rgb(255 255 255 / 0.85);
  padding: var(--space-5);
  box-shadow: var(--shadow-sm);
  min-width: 0;
}

.cardTop {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: flex-start;
}

.cardNameBlock {
  display: grid;
  gap: 0.25rem;
}

.cardName {
  font-weight: 950;
  letter-spacing: -0.02em;
  font-size: 1.02rem;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  max-width: 100%;
}

.cardMeta {
  color: hsl(var(--muted-foreground));
  font-weight: 800;
  font-size: 0.92rem;
}

.statusWrap {
  flex: 0 0 auto;
}

.statusBadge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.45rem 0.7rem;
  border-radius: 999px;
  border: 1px solid transparent;
  font-weight: 950;
  letter-spacing: -0.01em;
  white-space: nowrap;
}

.cardAmounts {
  margin-top: var(--space-4);
  padding: var(--space-3);
  border-radius: var(--radius-xl);
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.65);
}

.amountLabel {
  color: hsl(var(--muted-foreground));
  font-weight: 850;
  font-size: 0.9rem;
}

.amountValue {
  margin-top: 0.35rem;
  font-size: 1.35rem;
  font-weight: 1000;
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.datesGrid {
  margin-top: var(--space-4);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.dateLine {
  border-radius: var(--radius-xl);
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.7);
  padding: 0.75rem 0.85rem;
  min-width: 0;
}

.dateLine.span2 {
  grid-column: span 2;
}

.dateLabel {
  color: hsl(var(--muted-foreground));
  font-weight: 850;
  font-size: 0.88rem;
}

.dateValue {
  margin-top: 0.3rem;
  font-weight: 950;
  letter-spacing: -0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (min-width: 1100px) {
  .cardsGrid {
    grid-template-columns: 1fr;
  }
}
</style>
