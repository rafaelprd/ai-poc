<script setup lang="ts">
import { computed, ref } from 'vue'
import Card from './components/ui/Card.vue'
import Button from './components/ui/Button.vue'
import Badge from './components/ui/Badge.vue'
import IngestionSection from './components/IngestionSection.vue'
import CategorizationSection from './components/CategorizationSection.vue'
import TransactionsSection from './components/TransactionsSection.vue'

type TabKey = 'ingestion' | 'categorization' | 'transactions'

const tabs: Array<{
  key: TabKey
  label: string
  description: string
}> = [
  {
    key: 'ingestion',
    label: 'SPEC1 · Ingestion',
    description: 'Upload CSV/PDF, watch batch status, inspect parse errors.',
  },
  {
    key: 'categorization',
    label: 'SPEC2 · Categorization',
    description: 'Manage categories, rules, and auto-categorization.',
  },
  {
    key: 'transactions',
    label: 'Transactions',
    description: 'Review transactions, edit category, bulk apply changes.',
  },
]

const activeTab = ref<TabKey>('ingestion')

const activeTabMeta = computed(
  () => tabs.find((tab) => tab.key === activeTab.value) ?? tabs[0],
)
</script>

<template>
  <div class="appShell">
    <Card as="header" className="topBar">
      <div class="brandBlock">
        <p class="muted small" style="margin: 0">Financeiro</p>
        <h1 class="brandTitle">Ingestion and Categorization</h1>
        <p class="brandSubtitle">
          Batch pipeline, normalization, dedupe, rules, manual overrides.
        </p>
      </div>

      <Badge variant="success">
        <span class="statusDot" />
        Backend API connected
      </Badge>
    </Card>

    <Card as="nav" className="tabBar" aria-label="Primary sections">
      <Button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        size="sm"
        variant="ghost"
        class="tabButton"
        :class="{ tabButtonActive: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <span>{{ tab.label }}</span>
        <span class="muted small">{{ tab.description }}</span>
      </Button>
    </Card>

    <main class="contentGrid">
      <Card as="section">
        <div class="panelHeader">
          <div>
            <h2 class="panelTitle">{{ activeTabMeta.label }}</h2>
            <p class="panelDescription">{{ activeTabMeta.description }}</p>
          </div>
        </div>

        <div class="panelBody">
          <IngestionSection v-if="activeTab === 'ingestion'" />
          <CategorizationSection v-else-if="activeTab === 'categorization'" />
          <TransactionsSection v-else />
        </div>
      </Card>
    </main>
  </div>
</template>
