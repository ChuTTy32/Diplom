<template>
  <div class="dashboard">

    <!-- ─── HEADER ─────────────────────────────────────────────────── -->
    <header class="header">
      <div class="header-left">
        <span class="logo mono accent">RG</span>
        <div>
          <div class="title">RANSOMGUARD</div>
          <div class="subtitle mono dim">backup protection system v1.0</div>
        </div>
      </div>
      <div class="header-right">
        <div class="pulse-dot" :class="connected ? 'pulse-ok' : 'pulse-err'" />
        <span class="mono dim" style="font-size:11px">
          {{ connected ? 'CONNECTED' : 'OFFLINE' }}
        </span>
        <span class="clock mono">{{ clock }}</span>
      </div>
    </header>

    <!-- ─── STAT CARDS ─────────────────────────────────────────────── -->
    <section class="stats-grid">
      <StatCard
        label="total_alerts"
        :value="summary.total_alerts ?? '—'"
        :sub="summary.last_alert_time ? 'last: ' + fmtRelative(summary.last_alert_time) : 'no alerts'"
        :variant="(summary.total_alerts ?? 0) > 0 ? 'danger' : 'ok'"
      />
      <StatCard
        label="avg_entropy_1h"
        :value="summary.avg_entropy_1h != null ? summary.avg_entropy_1h.toFixed(4) : '—'"
        :sub="'threshold: ' + THRESHOLD"
        :variant="(summary.avg_entropy_1h ?? 0) >= THRESHOLD ? 'danger' : 'ok'"
      />
      <StatCard
        label="rpo_actual"
        :value="summary.rpo_minutes != null ? summary.rpo_minutes + ' min' : '—'"
        sub="recovery point objective"
        :variant="rpoVariant"
      />
      <StatCard
        label="rto_estimate"
        :value="summary.rto_minutes != null ? summary.rto_minutes + ' min' : '—'"
        sub="recovery time objective"
        variant="accent"
      />
      <StatCard
        label="last_backup"
        :value="summary.last_backup ? fmtRelative(summary.last_backup) : '—'"
        sub="borgbackup worm"
        :variant="lastBackupVariant"
      />
      <StatCard
        label="monitored_files"
        :value="entropyPoints.length"
        sub="unique events / 60min"
        variant=""
      />
    </section>

    <!-- ─── CHARTS ─────────────────────────────────────────────────── -->
    <section class="charts-grid">
      <EntropyChart :points="entropyPoints" :threshold="THRESHOLD" />
      <SystemChart  :points="systemPoints" />
    </section>

    <!-- ─── TABLES ─────────────────────────────────────────────────── -->
    <section class="tables-grid">
      <AlertTable  :alerts="alertRows" />
      <BackupTable :events="backupEvents" />
    </section>

    <!-- ─── FOOTER ─────────────────────────────────────────────────── -->
    <footer class="footer mono dim">
      НГАСУ (Сибстрин) · ВКР 09.03.02 · Защищённая система резервного копирования
      <span style="float:right">polling: 5s · {{ fmtTime(new Date().toISOString()) }}</span>
    </footer>

  </div>
</template>

<script setup lang="ts">
const THRESHOLD = 7.2

// ─── State ────────────────────────────────────────────────────────────
const connected    = ref(false)
const clock        = ref('')
const summary      = ref<any>({})
const entropyPoints = ref<any[]>([])
const systemPoints  = ref<any[]>([])
const alertRows     = ref<any[]>([])
const backupEvents  = ref<any[]>([])

// ─── API ──────────────────────────────────────────────────────────────
const { get } = useApi()

async function fetchAll() {
  try {
    const [sum, entropy, backup, system] = await Promise.all([
      get<any>('/metrics/summary'),
      get<any[]>('/metrics/entropy', { minutes: 60 }),
      get<any[]>('/metrics/backup',  { limit: 30 }),
      get<any[]>('/metrics/system',  { minutes: 30 }),
    ])
    summary.value      = sum
    entropyPoints.value = entropy
    alertRows.value    = entropy.filter((e: any) => e.alert).slice(0, 50)
    backupEvents.value = backup
    systemPoints.value = system
    connected.value    = true
  } catch {
    connected.value = false
  }
}

// ─── Helpers ──────────────────────────────────────────────────────────
function fmtTime(t: string) {
  return new Date(t).toLocaleTimeString()
}
function fmtRelative(t: string) {
  const diff = Math.floor((Date.now() - new Date(t).getTime()) / 1000)
  if (diff < 60) return diff + 's ago'
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago'
  return Math.floor(diff / 3600) + 'h ago'
}

const rpoVariant = computed(() => {
  const m = summary.value.rpo_minutes
  if (m == null) return ''
  if (m > 60) return 'danger'
  if (m > 15) return 'warn'
  return 'ok'
})

const lastBackupVariant = computed(() => {
  if (!summary.value.last_backup) return 'danger'
  const mins = (Date.now() - new Date(summary.value.last_backup).getTime()) / 60000
  if (mins > 30) return 'warn'
  return 'ok'
})


// ─── Lifecycle ────────────────────────────────────────────────────────
usePolling(fetchAll, 5000)

// Часы
onMounted(() => {
  const tick = () => {
    clock.value = new Date().toLocaleTimeString([], {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    })
  }
  tick()
  setInterval(tick, 1000)
})
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--bg);
}

/* ─── Header ─── */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 28px;
  border-bottom: 1px solid var(--border);
  background: var(--bg2);
  position: sticky; top: 0; z-index: 10;
}
.header-left { display: flex; align-items: center; gap: 14px; }
.logo {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.05em;
  background: linear-gradient(135deg, var(--accent), var(--ok));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.title {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: var(--text);
}
.subtitle { font-size: 10px; letter-spacing: 0.08em; margin-top: 1px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.clock { font-family: var(--font-mono); font-size: 13px; color: var(--text-mono); }

/* Pulse dot */
.pulse-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  position: relative;
}
.pulse-ok  { background: var(--ok); box-shadow: 0 0 0 0 rgba(0,230,118,0.4); animation: pulse-ok 2s infinite; }
.pulse-err { background: var(--danger); }
@keyframes pulse-ok {
  0%   { box-shadow: 0 0 0 0 rgba(0,230,118,0.4); }
  70%  { box-shadow: 0 0 0 6px rgba(0,230,118,0); }
  100% { box-shadow: 0 0 0 0 rgba(0,230,118,0); }
}

/* ─── Sections ─── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  border-bottom: 1px solid var(--border);
}
.stats-grid > * {
  border-right: 1px solid var(--border);
}
.stats-grid > *:last-child { border-right: none; }

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--border);
  border-bottom: 1px solid var(--border);
}
.charts-grid > * { background: var(--bg2); }

.tables-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--border);
  flex: 1;
}
.tables-grid > * { background: var(--bg2); }

/* ─── Footer ─── */
.footer {
  padding: 10px 28px;
  font-size: 10px;
  letter-spacing: 0.06em;
  border-top: 1px solid var(--border);
  background: var(--bg2);
}

/* ─── Responsive ─── */
@media (max-width: 1200px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 800px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .charts-grid, .tables-grid { grid-template-columns: 1fr; }
}
</style>
