<script setup lang="ts">
import { computed, ref } from "vue";
import Card from "./components/ui/Card.vue";
import Button from "./components/ui/Button.vue";
import Badge from "./components/ui/Badge.vue";
import DashboardSection from "./components/dashboard/DashboardSection.vue";
import IngestionSection from "./components/IngestionSection.vue";
import CategorizationSection from "./components/CategorizationSection.vue";
import TransactionsSection from "./components/TransactionsSection.vue";
import FixedExpensesSection from "./components/fixedExpenses/FixedExpensesSection.vue";
import ImportPage from "./pages/importPage.vue";

type TabKey =
    | "dashboard"
    | "ingestion"
    | "categorization"
    | "transactions"
    | "fixed-expenses"
    | "import";

type AppTab = {
    key: TabKey;
    kicker: string;
    label: string;
    description: string;
};

const tabs: AppTab[] = [
    {
        key: "dashboard",
        kicker: "SPEC5",
        label: "Dashboard",
        description:
            "Resumo mensal, cartões, time series, distribuição por categoria.",
    },
    {
        key: "ingestion",
        kicker: "SPEC1",
        label: "Ingestion",
        description:
            "Upload CSV/PDF, monitor batch status, inspect parse errors.",
    },
    {
        key: "categorization",
        kicker: "SPEC2",
        label: "Categorization",
        description: "Manage categories, keyword rules, auto-categorization.",
    },
    {
        key: "transactions",
        kicker: "LEDGER",
        label: "Transactions",
        description: "Review entries, edit categories, bulk apply changes.",
    },
    {
        key: "fixed-expenses",
        kicker: "SPEC4",
        label: "Fixed Expenses",
        description: "Recurring expenses, generation flow, periodic entries.",
    },
    {
        key: "import",
        kicker: "SPEC6",
        label: "Import",
        description: "Batch file import, deduplication, and import history.",
    },
];

const activeTab = ref<TabKey>("dashboard");

const activeTabMeta = computed(
    () => tabs.find((tab) => tab.key === activeTab.value) ?? tabs[0],
);

const activeTabIndex = computed(() => {
    const index = tabs.findIndex((tab) => tab.key === activeTab.value);
    return String(index >= 0 ? index + 1 : 1).padStart(2, "0");
});

const controlStats = [
    {
        value: "100%",
        label: "Normalization first",
    },
    {
        value: "24/7",
        label: "Batch-safe pipeline",
    },
    {
        value: "AUDIT",
        label: "Manual edits tracked",
    },
];
</script>

<template>
    <div class="appShell">
        <div class="appBackdrop" aria-hidden="true" />
        <div class="appGrid" aria-hidden="true" />
        <div class="appGlow appGlowLeft" aria-hidden="true" />
        <div class="appGlow appGlowRight" aria-hidden="true" />

        <Card as="header" className="heroShell">
            <div class="heroCopy">
                <p class="eyebrow">Financeiro · control room</p>
                <h1 class="heroTitle">Noir finance operations</h1>
                <p class="heroText">
                    Immutable transactions. Batch-oriented pipeline. Categories,
                    imports, recurring expenses, and manual overrides under one
                    disciplined shell.
                </p>

                <div class="heroPills">
                    <Badge variant="success">
                        <span class="statusDot" />
                        Backend live
                    </Badge>
                    <Badge variant="warning">Batch oriented</Badge>
                    <Badge variant="secondary">Normalization enforced</Badge>
                </div>
            </div>

            <div class="heroPanel">
                <div class="heroPanelHeader">
                    <span class="heroPanelLabel">Active sector</span>
                    <span class="heroPanelKicker">{{
                        activeTabMeta.kicker
                    }}</span>
                </div>

                <h2 class="heroPanelTitle">{{ activeTabMeta.label }}</h2>
                <p class="heroPanelDescription">
                    {{ activeTabMeta.description }}
                </p>

                <div class="heroStats">
                    <div
                        v-for="stat in controlStats"
                        :key="stat.label"
                        class="heroStat"
                    >
                        <strong>{{ stat.value }}</strong>
                        <span>{{ stat.label }}</span>
                    </div>
                </div>
            </div>
        </Card>

        <Card as="nav" className="railShell" aria-label="Primary sections">
            <Button
                v-for="(tab, index) in tabs"
                :key="tab.key"
                type="button"
                variant="ghost"
                size="sm"
                class="railButton"
                :class="{ railButtonActive: activeTab === tab.key }"
                :aria-current="activeTab === tab.key ? 'page' : undefined"
                @click="activeTab = tab.key"
            >
                <span class="railIndex">{{
                    String(index + 1).padStart(2, "0")
                }}</span>

                <span class="railText">
                    <span class="railLabelRow">
                        <span class="railLabel">{{ tab.label }}</span>
                        <span class="railKicker">{{ tab.kicker }}</span>
                    </span>
                    <span class="railDescription">{{ tab.description }}</span>
                </span>
            </Button>
        </Card>

        <main class="contentGrid">
            <Card as="section" className="contentShell">
                <div class="panelHeader panelHeaderNoir">
                    <div class="panelHeadingBlock">
                        <p class="panelEyebrow">{{ activeTabMeta.kicker }}</p>
                        <h2 class="panelTitle">{{ activeTabMeta.label }}</h2>
                        <p class="panelDescription">
                            {{ activeTabMeta.description }}
                        </p>
                    </div>

                    <div class="panelStatus">
                        <Badge variant="secondary"
                            >Sector {{ activeTabIndex }}</Badge
                        >
                        <Badge variant="success">Live sync</Badge>
                    </div>
                </div>

                <div class="panelBody panelBodyNoir">
                    <DashboardSection v-if="activeTab === 'dashboard'" />
                    <IngestionSection v-else-if="activeTab === 'ingestion'" />
                    <CategorizationSection
                        v-else-if="activeTab === 'categorization'"
                    />
                    <TransactionsSection
                        v-else-if="activeTab === 'transactions'"
                    />
                    <FixedExpensesSection
                        v-else-if="activeTab === 'fixed-expenses'"
                    />
                    <ImportPage v-else-if="activeTab === 'import'" />
                </div>
            </Card>
        </main>
    </div>
</template>

<style scoped>
:global(body) {
    background:
        radial-gradient(
            circle at top,
            rgb(255 255 255 / 0.04),
            transparent 34%
        ),
        linear-gradient(180deg, #050607 0%, #090a0d 100%);
    color: hsl(210 40% 98%);
}

.appShell {
    position: relative;
    min-height: 100vh;
    overflow: clip;
    padding: clamp(1rem, 2vw, 1.5rem);
    max-width: 1600px;
    margin: 0 auto;
    color: hsl(210 40% 98%);
}

.appBackdrop {
    position: absolute;
    inset: 0;
    background:
        radial-gradient(
            circle at 15% 15%,
            rgb(245 158 11 / 0.14),
            transparent 20%
        ),
        radial-gradient(
            circle at 85% 12%,
            rgb(59 130 246 / 0.12),
            transparent 18%
        ),
        radial-gradient(
            circle at 50% 100%,
            rgb(255 255 255 / 0.06),
            transparent 32%
        );
    pointer-events: none;
}

.appGrid {
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: 0.28;
    background-image:
        linear-gradient(rgb(255 255 255 / 0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgb(255 255 255 / 0.05) 1px, transparent 1px);
    background-size: 92px 92px;
    mask-image: radial-gradient(circle at center, black 30%, transparent 100%);
}

.appGlow {
    position: absolute;
    width: 38rem;
    height: 38rem;
    border-radius: 999px;
    filter: blur(64px);
    opacity: 0.2;
    pointer-events: none;
}

.appGlowLeft {
    left: -10rem;
    top: 8rem;
    background: radial-gradient(
        circle,
        rgb(245 158 11 / 0.55),
        transparent 60%
    );
}

.appGlowRight {
    right: -12rem;
    top: 22rem;
    background: radial-gradient(circle, rgb(59 130 246 / 0.5), transparent 60%);
}

.heroShell,
.railShell,
.contentShell {
    position: relative;
    z-index: 1;
}

.heroShell {
    display: grid;
    grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.95fr);
    gap: 1.25rem;
    align-items: stretch;
    padding: 1.25rem;
    margin-bottom: 1rem;
    border: 1px solid rgb(255 255 255 / 0.08);
    background:
        linear-gradient(180deg, rgb(15 17 22 / 0.9), rgb(8 9 12 / 0.88)),
        radial-gradient(
            circle at top right,
            rgb(245 158 11 / 0.08),
            transparent 35%
        );
    backdrop-filter: blur(18px);
    box-shadow:
        0 24px 80px rgb(0 0 0 / 0.45),
        inset 0 1px 0 rgb(255 255 255 / 0.05);
    overflow: hidden;
}

.heroShell::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(
        135deg,
        transparent 0%,
        rgb(255 255 255 / 0.04) 50%,
        transparent 100%
    );
    opacity: 0.7;
    pointer-events: none;
}

.heroCopy {
    position: relative;
    display: grid;
    align-content: center;
    gap: 0.9rem;
    padding: 0.5rem 0.25rem;
    min-width: 0;
}

.eyebrow {
    margin: 0;
    color: hsl(38 92% 62%);
    letter-spacing: 0.26em;
    text-transform: uppercase;
    font-size: 0.75rem;
    font-weight: 800;
}

.heroTitle {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(2rem, 4vw, 4.5rem);
    line-height: 0.94;
    letter-spacing: -0.06em;
    max-width: 10ch;
    text-wrap: balance;
}

.heroText {
    margin: 0;
    max-width: 62ch;
    color: rgb(226 232 240 / 0.82);
    font-size: 0.98rem;
    line-height: 1.7;
}

.heroPills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    align-items: center;
}

.heroPanel {
    position: relative;
    display: grid;
    align-content: space-between;
    gap: 1rem;
    min-width: 0;
    padding: 1.1rem 1.1rem 1rem;
    border-radius: calc(var(--radius-xl) + 0.35rem);
    border: 1px solid rgb(255 255 255 / 0.08);
    background:
        linear-gradient(
            180deg,
            rgb(255 255 255 / 0.05),
            rgb(255 255 255 / 0.02)
        ),
        radial-gradient(
            circle at top left,
            rgb(245 158 11 / 0.12),
            transparent 40%
        );
    box-shadow:
        inset 0 1px 0 rgb(255 255 255 / 0.05),
        0 18px 40px rgb(0 0 0 / 0.26);
    overflow: hidden;
}

.heroPanel::after {
    content: "";
    position: absolute;
    inset: auto -20% -35% auto;
    width: 16rem;
    height: 16rem;
    border-radius: 999px;
    background: radial-gradient(
        circle,
        rgb(245 158 11 / 0.18),
        transparent 65%
    );
    pointer-events: none;
}

.heroPanelHeader {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
}

.heroPanelLabel {
    color: rgb(226 232 240 / 0.6);
    font-size: 0.8rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.heroPanelKicker {
    padding: 0.35rem 0.55rem;
    border-radius: 999px;
    background: rgb(245 158 11 / 0.13);
    color: hsl(38 92% 62%);
    border: 1px solid rgb(245 158 11 / 0.22);
    font-size: 0.78rem;
    font-weight: 900;
    letter-spacing: 0.12em;
}

.heroPanelTitle {
    margin: 0;
    font-size: 1.65rem;
    letter-spacing: -0.04em;
    line-height: 1.05;
    font-family: var(--font-display);
}

.heroPanelDescription {
    margin: 0;
    color: rgb(226 232 240 / 0.74);
    line-height: 1.65;
}

.heroStats {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
    margin-top: 0.25rem;
}

.heroStat {
    display: grid;
    gap: 0.3rem;
    min-width: 0;
    padding: 0.75rem 0.8rem;
    border-radius: 1rem;
    border: 1px solid rgb(255 255 255 / 0.08);
    background: rgb(255 255 255 / 0.04);
}

.heroStat strong {
    font-size: 1rem;
    letter-spacing: 0.1em;
    color: hsl(38 92% 62%);
}

.heroStat span {
    font-size: 0.82rem;
    color: rgb(226 232 240 / 0.7);
    line-height: 1.45;
}

.railShell {
    display: grid;
    gap: 0.65rem;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    padding: 0.65rem;
    margin-bottom: 1rem;
    border: 1px solid rgb(255 255 255 / 0.08);
    background: rgb(10 11 14 / 0.76);
    backdrop-filter: blur(18px);
    box-shadow: 0 14px 42px rgb(0 0 0 / 0.28);
}

.railButton {
    position: relative;
    min-width: 0;
    height: auto;
    padding: 0.95rem 0.9rem;
    border-radius: 1.05rem;
    border: 1px solid transparent;
    background: transparent;
    color: rgb(226 232 240 / 0.72);
    display: flex;
    gap: 0.85rem;
    align-items: flex-start;
    text-align: left;
    transition:
        transform 160ms ease,
        background-color 160ms ease,
        border-color 160ms ease,
        box-shadow 160ms ease,
        color 160ms ease;
}

.railButton::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(180deg, rgb(255 255 255 / 0.04), transparent);
    opacity: 0;
    transition: opacity 160ms ease;
    pointer-events: none;
}

.railButton:hover {
    transform: translateY(-1px);
    color: hsl(210 40% 98%);
    background: rgb(255 255 255 / 0.05);
    border-color: rgb(255 255 255 / 0.06);
    box-shadow: 0 12px 30px rgb(0 0 0 / 0.18);
}

.railButton:hover::before {
    opacity: 1;
}

.railButtonActive {
    color: hsl(210 40% 98%);
    background:
        linear-gradient(
            180deg,
            rgb(245 158 11 / 0.16),
            rgb(255 255 255 / 0.05)
        ),
        rgb(255 255 255 / 0.04);
    border-color: rgb(245 158 11 / 0.22);
    box-shadow:
        0 18px 36px rgb(0 0 0 / 0.2),
        inset 0 1px 0 rgb(255 255 255 / 0.06);
}

.railIndex {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    background: rgb(255 255 255 / 0.06);
    color: hsl(38 92% 62%);
    font-size: 0.76rem;
    font-weight: 900;
    letter-spacing: 0.08em;
}

.railText {
    min-width: 0;
    display: grid;
    gap: 0.2rem;
}

.railLabelRow {
    display: flex;
    justify-content: space-between;
    gap: 0.65rem;
    align-items: baseline;
}

.railLabel {
    font-size: 0.95rem;
    font-weight: 850;
    letter-spacing: -0.02em;
}

.railKicker {
    color: rgb(245 158 11 / 0.9);
    font-size: 0.75rem;
    font-weight: 900;
    letter-spacing: 0.14em;
}

.railDescription {
    color: rgb(226 232 240 / 0.64);
    font-size: 0.82rem;
    line-height: 1.45;
}

.contentGrid {
    display: grid;
    gap: 1rem;
}

.contentShell {
    padding: 0;
    border: 1px solid rgb(255 255 255 / 0.08);
    background: linear-gradient(
        180deg,
        rgb(12 13 17 / 0.96),
        rgb(8 9 12 / 0.94)
    );
    backdrop-filter: blur(18px);
    box-shadow:
        0 24px 72px rgb(0 0 0 / 0.32),
        inset 0 1px 0 rgb(255 255 255 / 0.04);
    overflow: hidden;
}

.panelHeaderNoir {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
    padding: 1.2rem 1.25rem;
    border-bottom: 1px solid rgb(255 255 255 / 0.06);
    background: linear-gradient(
        180deg,
        rgb(255 255 255 / 0.035),
        rgb(255 255 255 / 0.015)
    );
}

.panelHeadingBlock {
    min-width: 0;
}

.panelEyebrow {
    margin: 0 0 0.35rem;
    color: hsl(38 92% 62%);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 0.74rem;
    font-weight: 800;
}

.panelTitle {
    margin: 0;
    font-family:
        "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
    font-size: clamp(1.4rem, 2vw, 2rem);
    line-height: 1.05;
    letter-spacing: -0.05em;
}

.panelDescription {
    margin: 0.45rem 0 0;
    color: rgb(226 232 240 / 0.74);
    line-height: 1.6;
    max-width: 72ch;
}

.panelStatus {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: flex-end;
}

.panelBodyNoir {
    padding: 1.25rem;
}

.statusDot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: currentColor;
    box-shadow: 0 0 0 4px rgb(34 197 94 / 0.08);
}

@media (max-width: 1240px) {
    .railShell {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .heroShell {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 820px) {
    .heroStats {
        grid-template-columns: 1fr;
    }

    .railShell {
        grid-template-columns: 1fr;
    }

    .panelHeaderNoir {
        flex-direction: column;
    }

    .panelStatus {
        justify-content: flex-start;
    }
}

@media (prefers-reduced-motion: no-preference) {
    .heroShell {
        animation: riseIn 520ms ease both;
    }

    .railShell {
        animation: riseIn 620ms ease both;
        animation-delay: 70ms;
    }

    .contentShell {
        animation: riseIn 700ms ease both;
        animation-delay: 120ms;
    }

    .heroPanel::after,
    .appGlow {
        animation: floatGlow 12s ease-in-out infinite;
    }
}

@keyframes riseIn {
    from {
        opacity: 0;
        transform: translateY(12px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes floatGlow {
    0%,
    100% {
        transform: translate3d(0, 0, 0) scale(1);
    }
    50% {
        transform: translate3d(0, -14px, 0) scale(1.03);
    }
}
</style>
