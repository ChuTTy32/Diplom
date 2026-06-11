#!/bin/bash
# =============================================================================
# ВНИМАНИЕ: этот скрипт перезаписывает frontend-исходники начальными версиями.
# Используйте ТОЛЬКО если нужно сбросить frontend к состоянию "с нуля".
# В нормальной работе НЕ ЗАПУСКАТЬ — frontend уже настроен и доработан.
# =============================================================================
echo "СТОП. Этот скрипт перезапишет исходники frontend."
echo "Запустите с флагом --force если уверены:"
echo "  bash setup_frontend.sh --force"
[ "${1:-}" != "--force" ] && exit 1

# Запускать из /home/chutts/Diplom/
set -e
cd /home/chutts/Diplom

echo "=== Создаём папки ==="
mkdir -p frontend/{assets/css,composables,pages,components}
mkdir -p backend/app/api

echo "=== frontend/app.vue ==="
cat > frontend/app.vue << 'EOF'
<template>
  <NuxtPage />
</template>
EOF

echo "=== frontend/nuxt.config.ts ==="
cat > frontend/nuxt.config.ts << 'EOF'
export default defineNuxtConfig({
  devtools: { enabled: false },
  ssr: false,
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000',
    },
  },
  app: {
    head: {
      title: 'RansomGuard — Backup Monitor',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;400;600;700&display=swap' },
      ],
    },
  },
  css: ['~/assets/css/main.css'],
})
EOF

echo "=== frontend/package.json ==="
cat > frontend/package.json << 'EOF'
{
  "name": "ransomware-backup-dashboard",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "nuxt build",
    "dev": "nuxt dev",
    "generate": "nuxt generate",
    "preview": "nuxt preview"
  },
  "dependencies": {
    "nuxt": "^3.12.0",
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "chart.js": "^4.4.3",
    "chartjs-adapter-date-fns": "^3.0.0",
    "date-fns": "^3.6.0"
  },
  "devDependencies": {
    "@nuxt/devtools": "latest",
    "typescript": "^5.4.0"
  }
}
EOF

echo "=== frontend/assets/css/main.css ==="
cat > frontend/assets/css/main.css << 'EOF'
:root {
  --bg:        #090b0f;
  --bg2:       #0e1118;
  --bg3:       #141820;
  --border:    #1e2530;
  --border2:   #2a3444;
  --text:      #c8d4e0;
  --text-dim:  #4a5a6a;
  --text-mono: #7ab3c8;
  --accent:    #00d4ff;
  --accent2:   #0099bb;
  --danger:    #ff3b5c;
  --danger2:   #c0002a;
  --warn:      #ffaa00;
  --ok:        #00e676;
  --ok2:       #00a152;
  --font-mono: 'Share Tech Mono', monospace;
  --font-body: 'Barlow', sans-serif;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.5;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--bg2); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }
.mono { font-family: var(--font-mono); }
.danger { color: var(--danger); }
.ok { color: var(--ok); }
.warn { color: var(--warn); }
.accent { color: var(--accent); }
.dim { color: var(--text-dim); }
EOF

echo "=== frontend/composables/useApi.ts ==="
cat > frontend/composables/useApi.ts << 'EOF'
export function useApi() {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  async function get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
    const url = new URL(base + path)
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)))
    }
    const res = await fetch(url.toString())
    if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
    return res.json()
  }

  return { get }
}

export function usePolling(fn: () => Promise<void>, intervalMs = 5000) {
  let timer: ReturnType<typeof setInterval> | null = null
  onMounted(async () => {
    await fn()
    timer = setInterval(fn, intervalMs)
  })
  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })
}
EOF

echo "=== frontend/components/StatCard.vue ==="
cat > frontend/components/StatCard.vue << 'EOF'
<template>
  <div class="stat-card" :class="variant">
    <div class="stat-label mono">{{ label }}</div>
    <div class="stat-value">{{ value }}</div>
    <div v-if="sub" class="stat-sub dim">{{ sub }}</div>
    <div class="stat-line" />
  </div>
</template>
<script setup lang="ts">
defineProps<{ label: string; value: string | number; sub?: string; variant?: string }>()
</script>
<style scoped>
.stat-card { background: var(--bg2); border: 1px solid var(--border); padding: 20px 24px; position: relative; overflow: hidden; transition: border-color 0.2s; }
.stat-card:hover { border-color: var(--border2); }
.stat-label { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px; }
.stat-value { font-family: var(--font-mono); font-size: 28px; line-height: 1; margin-bottom: 6px; color: var(--text); }
.stat-sub { font-size: 11px; margin-top: 4px; }
.stat-line { position: absolute; bottom: 0; left: 0; right: 0; height: 2px; background: var(--border2); }
.danger .stat-value { color: var(--danger); } .danger .stat-line { background: var(--danger2); }
.ok .stat-value { color: var(--ok); }         .ok .stat-line { background: var(--ok2); }
.warn .stat-value { color: var(--warn); }      .warn .stat-line { background: #b87a00; }
.accent .stat-value { color: var(--accent); }  .accent .stat-line { background: var(--accent2); }
</style>
EOF

echo "=== frontend/components/EntropyChart.vue ==="
cat > frontend/components/EntropyChart.vue << 'EOF'
<template>
  <div class="chart-wrap">
    <div class="chart-header">
      <span class="mono">ENTROPY_STREAM</span>
      <span class="mono dim" style="font-size:10px">threshold={{ threshold }}</span>
    </div>
    <canvas ref="canvas" />
  </div>
</template>
<script setup lang="ts">
import { Chart, LineController, LineElement, PointElement, LinearScale, Filler, Tooltip, CategoryScale } from 'chart.js'
Chart.register(LineController, LineElement, PointElement, LinearScale, Filler, Tooltip, CategoryScale)
const props = defineProps<{ points: Array<{ time: string; entropy: number; alert: boolean }>; threshold: number }>()
const canvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null
function buildChart() {
  if (!canvas.value) return
  const ctx = canvas.value.getContext('2d')!
  const gradient = ctx.createLinearGradient(0, 0, 0, 200)
  gradient.addColorStop(0, 'rgba(0,212,255,0.15)')
  gradient.addColorStop(1, 'rgba(0,212,255,0)')
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'Entropy', data: [], borderColor: '#00d4ff', borderWidth: 1.5, backgroundColor: gradient, fill: true, tension: 0.3, pointRadius: 0 },
        { label: 'Alerts', data: [], borderColor: 'transparent', backgroundColor: 'transparent', pointRadius: 5, pointBackgroundColor: '#ff3b5c', showLine: false },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 200 },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: '#0e1118', borderColor: '#1e2530', borderWidth: 1, titleColor: '#7ab3c8', bodyColor: '#c8d4e0', titleFont: { family: 'Share Tech Mono' }, bodyFont: { family: 'Share Tech Mono' }, callbacks: { title: (i) => new Date(i[0].label).toLocaleTimeString(), label: (i) => ` H = ${Number(i.raw).toFixed(4)}` } },
      },
      scales: {
        x: { type: 'category', ticks: { color: '#4a5a6a', font: { family: 'Share Tech Mono', size: 10 }, maxTicksLimit: 8, maxRotation: 0, callback: (_, i, ticks) => { const l = ticks[i]?.label; return l ? new Date(l).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '' } }, grid: { color: '#1e2530' }, border: { color: '#1e2530' } },
        y: { min: 0, max: 8.5, ticks: { color: '#4a5a6a', font: { family: 'Share Tech Mono', size: 10 }, stepSize: 1 }, grid: { color: '#1e2530' }, border: { color: '#1e2530' } },
      },
    },
    plugins: [{ id: 'thr', afterDraw(c) { const { ctx, chartArea, scales } = c; const y = scales.y.getPixelForValue(props.threshold); ctx.save(); ctx.setLineDash([4,4]); ctx.strokeStyle = 'rgba(255,170,0,0.5)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(chartArea.left, y); ctx.lineTo(chartArea.right, y); ctx.stroke(); ctx.restore(); } }],
  })
}
function updateChart() {
  if (!chart) return
  const sorted = [...props.points].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()).slice(-80)
  chart.data.labels = sorted.map(p => p.time)
  chart.data.datasets[0].data = sorted.map(p => p.entropy)
  chart.data.datasets[1].data = sorted.map(p => p.alert ? p.entropy : null)
  chart.update('none')
}
onMounted(() => buildChart())
onUnmounted(() => chart?.destroy())
watch(() => props.points, updateChart, { deep: true })
</script>
<style scoped>
.chart-wrap { background: var(--bg2); border: 1px solid var(--border); padding: 16px 20px 12px; height: 220px; display: flex; flex-direction: column; }
.chart-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; font-size: 11px; letter-spacing: 0.1em; color: var(--text-dim); text-transform: uppercase; }
canvas { flex: 1; min-height: 0; }
</style>
EOF

echo "=== frontend/components/SystemChart.vue ==="
cat > frontend/components/SystemChart.vue << 'EOF'
<template>
  <div class="chart-wrap">
    <div class="chart-header mono">SYSTEM_METRICS</div>
    <canvas ref="canvas" />
  </div>
</template>
<script setup lang="ts">
import { Chart, LineController, LineElement, PointElement, LinearScale, Filler, Tooltip, CategoryScale } from 'chart.js'
Chart.register(LineController, LineElement, PointElement, LinearScale, Filler, Tooltip, CategoryScale)
const props = defineProps<{ points: Array<{ time: string; cpu_pct: number; mem_pct: number; disk_pct: number }> }>()
const canvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null
function buildChart() {
  if (!canvas.value) return
  chart = new Chart(canvas.value.getContext('2d')!, {
    type: 'line',
    data: { labels: [], datasets: [
      { label: 'CPU',  data: [], borderColor: '#00d4ff', borderWidth: 1.5, fill: false, tension: 0.3, pointRadius: 0 },
      { label: 'RAM',  data: [], borderColor: '#ffaa00', borderWidth: 1.5, fill: false, tension: 0.3, pointRadius: 0 },
      { label: 'Disk', data: [], borderColor: '#00e676', borderWidth: 1.5, fill: false, tension: 0.3, pointRadius: 0 },
    ]},
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 200 },
      plugins: { legend: { display: true, labels: { color: '#4a5a6a', font: { family: 'Share Tech Mono', size: 10 }, boxWidth: 12, padding: 16 } }, tooltip: { backgroundColor: '#0e1118', borderColor: '#1e2530', borderWidth: 1, titleColor: '#7ab3c8', bodyColor: '#c8d4e0', titleFont: { family: 'Share Tech Mono' }, bodyFont: { family: 'Share Tech Mono' }, callbacks: { title: (i) => new Date(i[0].label).toLocaleTimeString(), label: (i) => ` ${i.dataset.label}: ${Number(i.raw).toFixed(1)}%` } } },
      scales: {
        x: { type: 'category', ticks: { color: '#4a5a6a', font: { family: 'Share Tech Mono', size: 10 }, maxTicksLimit: 6, maxRotation: 0, callback: (_, i, ticks) => { const l = ticks[i]?.label; return l ? new Date(l).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '' } }, grid: { color: '#1e2530' }, border: { color: '#1e2530' } },
        y: { min: 0, max: 100, ticks: { color: '#4a5a6a', font: { family: 'Share Tech Mono', size: 10 }, callback: (v) => `${v}%` }, grid: { color: '#1e2530' }, border: { color: '#1e2530' } },
      },
    },
  })
}
function updateChart() {
  if (!chart) return
  const sorted = [...props.points].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()).slice(-60)
  chart.data.labels = sorted.map(p => p.time)
  chart.data.datasets[0].data = sorted.map(p => p.cpu_pct)
  chart.data.datasets[1].data = sorted.map(p => p.mem_pct)
  chart.data.datasets[2].data = sorted.map(p => p.disk_pct)
  chart.update('none')
}
onMounted(() => buildChart())
onUnmounted(() => chart?.destroy())
watch(() => props.points, updateChart, { deep: true })
</script>
<style scoped>
.chart-wrap { background: var(--bg2); border: 1px solid var(--border); padding: 16px 20px 12px; height: 220px; display: flex; flex-direction: column; }
.chart-header { font-size: 11px; letter-spacing: 0.1em; color: var(--text-dim); text-transform: uppercase; margin-bottom: 8px; }
canvas { flex: 1; min-height: 0; }
</style>
EOF

echo "=== frontend/components/AlertTable.vue ==="
cat > frontend/components/AlertTable.vue << 'EOF'
<template>
  <div class="table-wrap">
    <div class="table-header">
      <span class="mono">ALERT_LOG</span>
      <span class="badge danger mono" v-if="alerts.length">{{ alerts.length }} ACTIVE</span>
      <span class="badge ok mono" v-else>CLEAR</span>
    </div>
    <div class="table-scroll">
      <table>
        <thead><tr><th class="mono">TIME</th><th class="mono">FILE</th><th class="mono">ENTROPY</th><th class="mono">SIZE</th><th class="mono">HOST</th></tr></thead>
        <tbody>
          <tr v-for="row in alerts" :key="row.time+row.file_path" :class="{ 'row-alert': row.alert }">
            <td class="mono time-cell">{{ fmtTime(row.time) }}</td>
            <td class="path-cell" :title="row.file_path">{{ shortPath(row.file_path) }}</td>
            <td class="mono" :class="eClass(row.entropy)">{{ row.entropy.toFixed(4) }}</td>
            <td class="mono dim">{{ fmtSize(row.file_size) }}</td>
            <td class="mono dim">{{ row.host }}</td>
          </tr>
          <tr v-if="!alerts.length"><td colspan="5" class="no-data mono dim">— no alerts —</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ alerts: Array<{ time: string; file_path: string; entropy: number; file_size: number|null; alert: boolean; host: string }> }>()
const fmtTime = (t: string) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const shortPath = (p: string) => { const parts = p.split('/'); return parts.length > 3 ? '…/' + parts.slice(-2).join('/') : p }
const fmtSize = (b: number|null) => { if (!b) return '—'; if (b > 1048576) return (b/1048576).toFixed(1)+' MB'; if (b > 1024) return (b/1024).toFixed(1)+' KB'; return b+' B' }
const eClass = (e: number) => e >= 7.5 ? 'danger' : e >= 7.0 ? 'warn' : 'ok'
</script>
<style scoped>
.table-wrap { background: var(--bg2); border: 1px solid var(--border); display: flex; flex-direction: column; max-height: 320px; }
.table-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; border-bottom: 1px solid var(--border); font-size: 11px; letter-spacing: 0.1em; color: var(--text-dim); text-transform: uppercase; flex-shrink: 0; }
.badge { font-size: 10px; padding: 2px 8px; border-radius: 2px; letter-spacing: 0.08em; }
.badge.danger { background: rgba(255,59,92,0.15); color: var(--danger); border: 1px solid var(--danger2); }
.badge.ok { background: rgba(0,230,118,0.1); color: var(--ok); border: 1px solid var(--ok2); }
.table-scroll { overflow-y: auto; flex: 1; }
table { width: 100%; border-collapse: collapse; }
thead th { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--text-dim); padding: 8px 16px; text-align: left; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--bg2); }
tbody td { padding: 7px 16px; font-size: 12px; border-bottom: 1px solid var(--border); white-space: nowrap; }
.row-alert { background: rgba(255,59,92,0.04); }
.row-alert:hover { background: rgba(255,59,92,0.08); }
tbody tr:not(.row-alert):hover { background: var(--bg3); }
.time-cell { color: var(--text-mono); }
.path-cell { max-width: 240px; overflow: hidden; text-overflow: ellipsis; color: var(--text); }
.no-data { text-align: center; padding: 24px; font-size: 12px; }
</style>
EOF

echo "=== frontend/components/BackupTable.vue ==="
cat > frontend/components/BackupTable.vue << 'EOF'
<template>
  <div class="table-wrap">
    <div class="table-header mono">BACKUP_EVENTS</div>
    <div class="table-scroll">
      <table>
        <thead><tr><th class="mono">TIME</th><th class="mono">STATUS</th><th class="mono">ARCHIVE</th><th class="mono">DURATION</th><th class="mono">RPO</th><th class="mono">RTO</th></tr></thead>
        <tbody>
          <tr v-for="row in events" :key="row.time">
            <td class="mono time-cell">{{ fmtTime(row.time) }}</td>
            <td><span class="status-badge mono" :class="row.event_type">{{ row.event_type.toUpperCase() }}</span></td>
            <td class="mono dim archive-cell" :title="row.archive_name">{{ shortArchive(row.archive_name) }}</td>
            <td class="mono">{{ row.duration_sec != null ? row.duration_sec+'s' : '—' }}</td>
            <td class="mono" :class="rpoClass(row.rpo_minutes)">{{ row.rpo_minutes != null ? row.rpo_minutes+'m' : '—' }}</td>
            <td class="mono dim">{{ row.rto_minutes != null ? row.rto_minutes+'m' : '—' }}</td>
          </tr>
          <tr v-if="!events.length"><td colspan="6" class="no-data mono dim">— no backup events —</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ events: Array<{ time: string; event_type: string; archive_name: string|null; duration_sec: number|null; rpo_minutes: number|null; rto_minutes: number|null; error_msg: string|null }> }>()
const fmtTime = (t: string) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const shortArchive = (n: string|null) => { if (!n) return '—'; const p = n.split('::'); return p[1] || n }
const rpoClass = (m: number|null) => m == null ? 'dim' : m > 60 ? 'danger' : m > 15 ? 'warn' : 'ok'
</script>
<style scoped>
.table-wrap { background: var(--bg2); border: 1px solid var(--border); display: flex; flex-direction: column; max-height: 260px; }
.table-header { padding: 12px 20px; border-bottom: 1px solid var(--border); font-size: 11px; letter-spacing: 0.1em; color: var(--text-dim); text-transform: uppercase; flex-shrink: 0; }
.table-scroll { overflow-y: auto; flex: 1; }
table { width: 100%; border-collapse: collapse; }
thead th { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--text-dim); padding: 8px 16px; text-align: left; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--bg2); }
tbody td { padding: 7px 16px; font-size: 12px; border-bottom: 1px solid var(--border); }
tbody tr:hover { background: var(--bg3); }
.time-cell { color: var(--text-mono); }
.archive-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.no-data { text-align: center; padding: 24px; font-size: 12px; }
.status-badge { font-size: 10px; padding: 2px 7px; border-radius: 2px; letter-spacing: 0.06em; }
.status-badge.success { background: rgba(0,230,118,0.1); color: var(--ok); border: 1px solid var(--ok2); }
.status-badge.fail { background: rgba(255,59,92,0.15); color: var(--danger); border: 1px solid var(--danger2); }
.status-badge.start { background: rgba(0,212,255,0.1); color: var(--accent); border: 1px solid var(--accent2); }
</style>
EOF

echo "=== frontend/pages/index.vue ==="
cat > frontend/pages/index.vue << 'EOF'
<template>
  <div class="dashboard">
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
        <span class="mono dim" style="font-size:11px">{{ connected ? 'CONNECTED' : 'OFFLINE' }}</span>
        <span class="clock mono">{{ clock }}</span>
      </div>
    </header>
    <section class="stats-grid">
      <StatCard label="total_alerts" :value="summary.total_alerts ?? '—'" :sub="summary.last_alert_time ? 'last: ' + fmtRelative(summary.last_alert_time) : 'no alerts'" :variant="(summary.total_alerts ?? 0) > 0 ? 'danger' : 'ok'" />
      <StatCard label="avg_entropy_1h" :value="summary.avg_entropy_1h != null ? summary.avg_entropy_1h.toFixed(4) : '—'" :sub="'threshold: ' + THRESHOLD" :variant="(summary.avg_entropy_1h ?? 0) >= THRESHOLD ? 'danger' : 'ok'" />
      <StatCard label="rpo_actual" :value="summary.rpo_minutes != null ? summary.rpo_minutes + ' min' : '—'" sub="recovery point objective" :variant="rpoVariant" />
      <StatCard label="rto_estimate" :value="summary.rto_minutes != null ? summary.rto_minutes + ' min' : '—'" sub="recovery time objective" variant="accent" />
      <StatCard label="last_backup" :value="summary.last_backup ? fmtRelative(summary.last_backup) : '—'" sub="borgbackup worm" :variant="lastBackupVariant" />
      <StatCard label="monitored_files" :value="entropyPoints.length" sub="unique events / 60min" variant="" />
    </section>
    <section class="charts-grid">
      <EntropyChart :points="entropyPoints" :threshold="THRESHOLD" />
      <SystemChart  :points="systemPoints" />
    </section>
    <section class="tables-grid">
      <AlertTable  :alerts="alertRows" />
      <BackupTable :events="backupEvents" />
    </section>
    <footer class="footer mono dim">
      НГАСУ (Сибстрин) · ВКР 09.03.02 · Защищённая система резервного копирования
      <span style="float:right">polling: 5s</span>
    </footer>
  </div>
</template>
<script setup lang="ts">
const THRESHOLD = 7.2
const connected     = ref(false)
const clock         = ref('')
const summary       = ref<any>({})
const entropyPoints = ref<any[]>([])
const systemPoints  = ref<any[]>([])
const alertRows     = ref<any[]>([])
const backupEvents  = ref<any[]>([])
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
  } catch { connected.value = false }
}
const fmtRelative = (t: string) => { const d = Math.floor((Date.now() - new Date(t).getTime()) / 1000); if (d < 60) return d+'s ago'; if (d < 3600) return Math.floor(d/60)+'m ago'; return Math.floor(d/3600)+'h ago' }
const rpoVariant = computed(() => { const m = summary.value.rpo_minutes; if (m == null) return ''; if (m > 60) return 'danger'; if (m > 15) return 'warn'; return 'ok' })
const lastBackupVariant = computed(() => { if (!summary.value.last_backup) return 'danger'; return (Date.now() - new Date(summary.value.last_backup).getTime()) / 60000 > 30 ? 'warn' : 'ok' })
usePolling(fetchAll, 5000)
onMounted(() => { const tick = () => { clock.value = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) }; tick(); setInterval(tick, 1000) })
</script>
<style scoped>
.dashboard { min-height: 100vh; display: flex; flex-direction: column; background: var(--bg); }
.header { display: flex; justify-content: space-between; align-items: center; padding: 14px 28px; border-bottom: 1px solid var(--border); background: var(--bg2); position: sticky; top: 0; z-index: 10; }
.header-left { display: flex; align-items: center; gap: 14px; }
.logo { font-size: 22px; font-weight: 700; letter-spacing: 0.05em; background: linear-gradient(135deg, var(--accent), var(--ok)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.title { font-size: 15px; font-weight: 700; letter-spacing: 0.15em; color: var(--text); }
.subtitle { font-size: 10px; letter-spacing: 0.08em; margin-top: 1px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.clock { font-family: var(--font-mono); font-size: 13px; color: var(--text-mono); }
.pulse-dot { width: 7px; height: 7px; border-radius: 50%; }
.pulse-ok { background: var(--ok); animation: pulse-ok 2s infinite; }
.pulse-err { background: var(--danger); }
@keyframes pulse-ok { 0% { box-shadow: 0 0 0 0 rgba(0,230,118,0.4); } 70% { box-shadow: 0 0 0 6px rgba(0,230,118,0); } 100% { box-shadow: 0 0 0 0 rgba(0,230,118,0); } }
.stats-grid { display: grid; grid-template-columns: repeat(6,1fr); border-bottom: 1px solid var(--border); }
.stats-grid > * { border-right: 1px solid var(--border); }
.stats-grid > *:last-child { border-right: none; }
.charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--border); border-bottom: 1px solid var(--border); }
.charts-grid > * { background: var(--bg2); }
.tables-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--border); flex: 1; }
.tables-grid > * { background: var(--bg2); }
.footer { padding: 10px 28px; font-size: 10px; letter-spacing: 0.06em; border-top: 1px solid var(--border); background: var(--bg2); }
@media (max-width: 1200px) { .stats-grid { grid-template-columns: repeat(3,1fr); } }
@media (max-width: 800px) { .stats-grid { grid-template-columns: repeat(2,1fr); } .charts-grid, .tables-grid { grid-template-columns: 1fr; } }
</style>
EOF

echo "=== backend/app/api/metrics.py ==="
cat > backend/app/api/metrics.py << 'EOF'
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import List

from app.core.database import get_db
from app.schemas.metrics import (
    EntropyMetricIn, EntropyMetricOut,
    BackupEventIn, BackupEventOut,
    SystemMetricIn, AlertSummary,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.post("/entropy", status_code=201)
async def ingest_entropy(payload: EntropyMetricIn, db: AsyncSession = Depends(get_db)):
    await db.execute(text("INSERT INTO entropy_metrics (file_path, entropy, file_size, alert, host) VALUES (:file_path, :entropy, :file_size, :alert, :host)"), payload.model_dump())
    await db.commit()
    return {"status": "ok"}

@router.get("/entropy", response_model=List[EntropyMetricOut])
async def get_entropy(minutes: int = Query(60, ge=1, le=1440), alert_only: bool = False, db: AsyncSession = Depends(get_db)):
    since = datetime.utcnow() - timedelta(minutes=minutes)
    where = "WHERE time >= :since" + (" AND alert = TRUE" if alert_only else "")
    result = await db.execute(text(f"SELECT * FROM entropy_metrics {where} ORDER BY time DESC LIMIT 1000"), {"since": since})
    return result.mappings().all()

@router.post("/backup", status_code=201)
async def ingest_backup_event(payload: BackupEventIn, db: AsyncSession = Depends(get_db)):
    await db.execute(text("INSERT INTO backup_events (event_type, archive_name, duration_sec, size_bytes, rpo_minutes, rto_minutes, error_msg) VALUES (:event_type, :archive_name, :duration_sec, :size_bytes, :rpo_minutes, :rto_minutes, :error_msg)"), payload.model_dump())
    await db.commit()
    return {"status": "ok"}

@router.get("/backup", response_model=List[BackupEventOut])
async def get_backup_events(limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT * FROM backup_events ORDER BY time DESC LIMIT :limit"), {"limit": limit})
    return result.mappings().all()

@router.post("/system", status_code=201)
async def ingest_system(payload: SystemMetricIn, db: AsyncSession = Depends(get_db)):
    await db.execute(text("INSERT INTO system_metrics (cpu_pct, mem_pct, disk_pct, net_in_kb, net_out_kb) VALUES (:cpu_pct, :mem_pct, :disk_pct, :net_in_kb, :net_out_kb)"), payload.model_dump())
    await db.commit()
    return {"status": "ok"}

@router.get("/system")
async def get_system(minutes: int = Query(30, ge=1, le=1440), db: AsyncSession = Depends(get_db)):
    since = datetime.utcnow() - timedelta(minutes=minutes)
    result = await db.execute(text("SELECT * FROM system_metrics WHERE time >= :since ORDER BY time DESC LIMIT 500"), {"since": since})
    return result.mappings().all()

@router.get("/summary", response_model=AlertSummary)
async def get_summary(db: AsyncSession = Depends(get_db)):
    since_1h = datetime.utcnow() - timedelta(hours=1)
    alerts = await db.execute(text("SELECT COUNT(*) as cnt, MAX(time) as last_time FROM entropy_metrics WHERE alert = TRUE"))
    alert_row = alerts.mappings().one()
    avg_e = await db.execute(text("SELECT AVG(entropy) as avg_e FROM entropy_metrics WHERE time >= :since"), {"since": since_1h})
    avg_entropy = avg_e.scalar()
    last_bk = await db.execute(text("SELECT time, rpo_minutes, rto_minutes FROM backup_events WHERE event_type = 'success' ORDER BY time DESC LIMIT 1"))
    bk_row = last_bk.mappings().one_or_none()
    return AlertSummary(total_alerts=alert_row["cnt"] or 0, last_alert_time=alert_row["last_time"], avg_entropy_1h=round(avg_entropy, 4) if avg_entropy else None, last_backup=bk_row["time"] if bk_row else None, rpo_minutes=bk_row["rpo_minutes"] if bk_row else None, rto_minutes=bk_row["rto_minutes"] if bk_row else None)
EOF

echo ""
echo "=== ВСЁ ГОТОВО. Структура: ==="
find frontend backend/app/api -type f | sort
