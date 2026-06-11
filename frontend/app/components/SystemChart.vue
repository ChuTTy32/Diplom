<template>
  <div class="chart-wrap">
    <div class="chart-header mono">СИСТЕМНЫЕ МЕТРИКИ</div>
    <div class="chart-note dim">
      Нагрузка на хост в процентах: CPU — процессор, ОЗУ — оперативная память,
      Диск — заполнение раздела с защищаемыми данными. Всплеск CPU во время
      атаки — работа шифровальщика и реакция системы.
    </div>
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
      { label: 'ОЗУ',  data: [], borderColor: '#ffaa00', borderWidth: 1.5, fill: false, tension: 0.3, pointRadius: 0 },
      { label: 'Диск', data: [], borderColor: '#00e676', borderWidth: 1.5, fill: false, tension: 0.3, pointRadius: 0 },
    ]},
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 200 },
      plugins: { legend: { display: true, labels: { color: '#4a5a6a', font: { family: 'JetBrains Mono', size: 10 }, boxWidth: 12, padding: 16 } }, tooltip: { backgroundColor: '#0e1118', borderColor: '#1e2530', borderWidth: 1, titleColor: '#7ab3c8', bodyColor: '#c8d4e0', titleFont: { family: 'JetBrains Mono' }, bodyFont: { family: 'JetBrains Mono' }, callbacks: { title: (i) => new Date(i[0].label).toLocaleTimeString(), label: (i) => ` ${i.dataset.label}: ${Number(i.raw).toFixed(1)}%` } } },
      scales: {
        x: { type: 'category', ticks: { color: '#4a5a6a', font: { family: 'JetBrains Mono', size: 10 }, maxTicksLimit: 6, maxRotation: 0, callback: (_, i, ticks) => { const l = ticks[i]?.label; return l ? new Date(l).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '' } }, grid: { color: '#1e2530' }, border: { color: '#1e2530' } },
        y: { min: 0, max: 100, ticks: { color: '#4a5a6a', font: { family: 'JetBrains Mono', size: 10 }, callback: (v) => `${v}%` }, grid: { color: '#1e2530' }, border: { color: '#1e2530' } },
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
.chart-wrap { background: var(--bg2); border: 1px solid var(--border); padding: 16px 20px 12px; height: 250px; display: flex; flex-direction: column; }
.chart-header { font-size: 11px; letter-spacing: 0.1em; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px; }
.chart-note { font-size: 10.5px; line-height: 1.45; margin-bottom: 8px; max-width: 720px; }
canvas { flex: 1; min-height: 0; }
</style>
