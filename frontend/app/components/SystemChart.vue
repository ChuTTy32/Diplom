<template>
  <div class="chart-wrap panel">
    <div class="panel-head">
      <span class="panel-title">
        Системные метрики
        <span class="info-tip" tabindex="0">ⓘ
          <span class="tip-bubble">
            Нагрузка на хост в процентах, агент снимает показания каждые 5&nbsp;секунд.<br><br>
            Массовое шифрование — это интенсивная криптография и запись на диск,
            поэтому <b>резкий всплеск CPU</b> одновременно с ростом энтропии файлов —
            характерная сигнатура работы шифровальщика.
          </span>
        </span>
      </span>
    </div>
    <div class="chart-body">
      <div class="legend">
        <span class="lg"><i class="sw" style="background:#818cf8" />CPU — процессор</span>
        <span class="lg"><i class="sw" style="background:#fbbf24" />ОЗУ — память</span>
        <span class="lg"><i class="sw" style="background:#34d399" />Диск — раздел с данными</span>
      </div>
      <canvas ref="canvas" />
    </div>
  </div>
</template>
<script setup lang="ts">
import { Chart, LineController, LineElement, PointElement, LinearScale, Filler, Tooltip, CategoryScale } from 'chart.js'
Chart.register(LineController, LineElement, PointElement, LinearScale, Filler, Tooltip, CategoryScale)
const props = defineProps<{ points: Array<{ time: string; cpu_pct: number; mem_pct: number; disk_pct: number }> }>()
const canvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

const GRID = 'rgba(255,255,255,0.06)'
const TICK = '#6b7384'

function buildChart() {
  if (!canvas.value) return
  chart = new Chart(canvas.value.getContext('2d')!, {
    type: 'line',
    data: { labels: [], datasets: [
      { label: 'CPU',  data: [], borderColor: '#818cf8', borderWidth: 2, fill: false, tension: 0.35, pointRadius: 0 },
      { label: 'ОЗУ',  data: [], borderColor: '#fbbf24', borderWidth: 2, fill: false, tension: 0.35, pointRadius: 0 },
      { label: 'Диск', data: [], borderColor: '#34d399', borderWidth: 2, fill: false, tension: 0.35, pointRadius: 0 },
    ]},
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#20242e', borderColor: 'rgba(255,255,255,0.13)', borderWidth: 1, padding: 10, cornerRadius: 8, titleColor: '#aab1c0', bodyColor: '#e6e8ee', titleFont: { family: 'Inter', size: 11 }, bodyFont: { family: 'JetBrains Mono', size: 12 }, callbacks: { title: (i) => new Date(i[0].label).toLocaleTimeString(), label: (i) => ` ${i.dataset.label}: ${Number(i.raw).toFixed(1)}%` } } },
      scales: {
        x: { type: 'category', ticks: { color: TICK, font: { family: 'Inter', size: 10 }, maxTicksLimit: 6, maxRotation: 0, callback: (_, i, ticks) => { const l = ticks[i]?.label; return l ? new Date(l).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '' } }, grid: { color: GRID }, border: { display: false } },
        y: { min: 0, max: 100, ticks: { color: TICK, font: { family: 'JetBrains Mono', size: 10 }, callback: (v) => `${v}%` }, grid: { color: GRID }, border: { display: false } },
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
.chart-wrap { height: 300px; }
.chart-body { flex: 1; display: flex; flex-direction: column; padding: 16px 20px; min-height: 0; }
canvas { flex: 1; min-height: 0; }
</style>
