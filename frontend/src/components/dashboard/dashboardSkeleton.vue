<template>
  <div class="dashboardSkeleton" role="status" aria-live="polite" aria-label="Carregando dashboard">
    <!-- Top controls -->
    <div class="topRow">
      <div class="skeleton chip" aria-hidden="true" />
    </div>

    <!-- Metrics row -->
    <div class="metricsRow">
      <div class="metricCard skeletonCard" aria-hidden="true">
        <div class="skeleton bar w-55" />
        <div class="skeleton bar w-75" />
        <div class="skeleton bar w-35" />
      </div>
      <div class="metricCard skeletonCard" aria-hidden="true">
        <div class="skeleton bar w-55" />
        <div class="skeleton bar w-75" />
        <div class="skeleton bar w-35" />
      </div>
      <div class="metricCard skeletonCard" aria-hidden="true">
        <div class="skeleton bar w-55" />
        <div class="skeleton bar w-75" />
        <div class="skeleton bar w-35" />
      </div>
    </div>

    <!-- Two-column content -->
    <div class="twoCol">
      <!-- Pie + table -->
      <div class="colPanel">
        <div class="panelHeaderStub">
          <div class="skeleton bar w-45" />
          <div class="skeleton bar w-20" />
        </div>

        <div class="panelBodyStub">
          <div class="skeleton donut" aria-hidden="true" />
          <div class="skeleton bar w-80 mt-3" />
          <div class="skeleton bar w-60" />
          <div class="skeleton list">
            <div class="skeleton bar w-90" v-for="i in 4" :key="i" />
          </div>
        </div>
      </div>

      <div class="colPanel">
        <div class="panelHeaderStub">
          <div class="skeleton bar w-55" />
          <div class="skeleton bar w-25" />
        </div>

        <div class="panelBodyStub">
          <div class="tableHead">
            <div class="skeleton bar w-35" />
            <div class="skeleton bar w-20" />
            <div class="skeleton bar w-20" />
            <div class="skeleton bar w-15" />
          </div>

          <div class="tableRows">
            <div class="tableRow" v-for="row in 7" :key="row" aria-hidden="true">
              <div class="cellDot">
                <div class="skeleton dot" />
              </div>
              <div class="skeleton bar w-70" />
              <div class="skeleton bar w-45" />
              <div class="skeleton bar w-25" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Time series -->
    <div class="fullCol">
      <div class="colPanel">
        <div class="panelHeaderStub">
          <div class="skeleton bar w-40" />
          <div class="skeleton pill" />
        </div>

        <div class="panelBodyStub">
          <div class="skeleton chartArea" aria-hidden="true" />
          <div class="skeleton bar w-30 mt-3" />
        </div>
      </div>
    </div>

    <!-- Bottom row -->
    <div class="bottomRow twoColBottom">
      <div class="colPanel">
        <div class="panelHeaderStub">
          <div class="skeleton bar w-45" />
          <div class="skeleton bar w-20" />
        </div>

        <div class="panelBodyStub cardsGrid">
          <div class="skeleton cardStub" v-for="i in 3" :key="i" aria-hidden="true">
            <div class="skeleton bar w-70" />
            <div class="skeleton bar w-45 mt-2" />
            <div class="skeleton bar w-55 mt-2" />
            <div class="skeleton pill sm mt-3" />
          </div>
        </div>
      </div>

      <div class="colPanel">
        <div class="panelHeaderStub">
          <div class="skeleton bar w-55" />
          <div class="skeleton bar w-25" />
        </div>

        <div class="panelBodyStub">
          <div class="skeleton list spaced" aria-hidden="true">
            <div class="skeleton rowLine" v-for="i in 5" :key="i">
              <div class="skeleton dot" />
              <div class="skeleton bar w-70" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboardSkeleton {
  display: grid;
  gap: 1.25rem;
}

.topRow {
  display: flex;
  justify-content: flex-start;
  align-items: center;
}

.metricsRow {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.twoCol {
  display: grid;
  gap: 1.25rem;
  grid-template-columns: 1fr 1fr;
  align-items: start;
}

.fullCol {
  display: grid;
}

.twoColBottom {
  grid-template-columns: 1fr 1fr;
}

.colPanel {
  background: rgb(255 255 255 / 0.9);
  border: 1px solid hsl(var(--border));
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  overflow: clip;
}

.panelHeaderStub {
  padding: var(--space-5) var(--space-6);
  border-bottom: 1px solid hsl(var(--border));
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: center;
  background: linear-gradient(
    180deg,
    rgb(255 255 255 / 0.96),
    rgb(248 250 252 / 0.92)
  );
}

.panelBodyStub {
  padding: var(--space-6);
}

.tableHead {
  display: grid;
  grid-template-columns: 36px 1.3fr 0.7fr 0.6fr;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.tableRows {
  display: grid;
  gap: 0.65rem;
}

.tableRow {
  display: grid;
  grid-template-columns: 36px 1.3fr 0.7fr 0.6fr;
  gap: 0.75rem;
  align-items: center;
}

.cellDot {
  display: flex;
  align-items: center;
  justify-content: center;
}

.cardsGrid {
  display: grid;
  gap: 1rem;
  grid-template-columns: 1fr;
}

@media (min-width: 1100px) {
  .cardsGrid {
    grid-template-columns: 1fr;
  }
}

.skeleton {
  background: hsl(var(--muted-foreground) / 0.18);
  border-radius: 0.5rem;
  position: relative;
  overflow: hidden;
}

.skeleton::after {
  content: "";
  position: absolute;
  top: 0;
  left: -30%;
  height: 100%;
  width: 30%;
  background: linear-gradient(
    90deg,
    transparent,
    rgb(255 255 255 / 0.6),
    transparent
  );
  animation: shimmer 1.2s ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    transform: translateX(0);
    opacity: 0.8;
  }
  100% {
    transform: translateX(500%);
    opacity: 1;
  }
}

.skeletonCard {
  padding: var(--space-6);
  border-radius: var(--radius-xl);
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.7);
  box-shadow: var(--shadow-sm);
}

.bar {
  height: 0.85rem;
  margin-bottom: 0.55rem;
}

.w-20 {
  width: 20%;
}
.w-25 {
  width: 25%;
}
.w-30 {
  width: 30%;
}
.w-35 {
  width: 35%;
}
.w-40 {
  width: 40%;
}
.w-45 {
  width: 45%;
}
.w-55 {
  width: 55%;
}
.w-60 {
  width: 60%;
}
.w-70 {
  width: 70%;
}
.w-75 {
  width: 75%;
}
.w-80 {
  width: 80%;
}
.w-90 {
  width: 90%;
}

.mt-2 {
  margin-top: 0.5rem;
}
.mt-3 {
  margin-top: 0.75rem;
}

.chip {
  width: min(520px, 100%);
  height: 2.6rem;
  border-radius: 999px;
}

.pill {
  width: 10.5rem;
  height: 2.1rem;
  border-radius: 999px;
}

.pill.sm {
  width: 7rem;
  height: 1.9rem;
  border-radius: 999px;
}

.donut {
  width: min(320px, 100%);
  height: 220px;
  border-radius: 999px;
  margin: 0 auto 0.75rem;
}

.list {
  display: grid;
  gap: 0.6rem;
  margin-top: 0.9rem;
}

.spaced {
  gap: 0.75rem;
}

.rowLine {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.2rem 0;
  border-radius: 0.75rem;
}

.dot {
  width: 0.85rem;
  height: 0.85rem;
  border-radius: 999px;
  flex: 0 0 auto;
}

.chartArea {
  height: 260px;
  border-radius: var(--radius-xl);
  background:
    radial-gradient(circle at 30% 40%, rgb(255 255 255 / 0.25), transparent 38%),
    linear-gradient(90deg, rgb(255 255 255 / 0.08), rgb(255 255 255 / 0.03));
}
.cardStub {
  padding: var(--space-5) var(--space-6);
  border-radius: var(--radius-xl);
  border: 1px solid hsl(var(--border));
  background: rgb(255 255 255 / 0.65);
}

@media (max-width: 1023px) {
  .metricsRow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .twoCol {
    grid-template-columns: 1fr;
  }
  .twoColBottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .metricsRow {
    grid-template-columns: 1fr;
  }
  .cardsGrid {
    grid-template-columns: 1fr;
  }
}
</style>
