<template>
  <div class="chart-wrap">
    <div class="chart-header">
      <span class="mono">ЭНТРОПИЯ ФАЙЛОВ (H, бит)</span>
      <span class="mono dim" style="font-size:10px">порог = {{ threshold }}</span>
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
        tooltip: { backgroundColor: '#0e1118', borderColor: '#1e2530', borderWidth: 1, titleColor: '#7ab3c8', bodyColor: '#c8d4e0', titleFont: { family: 'JetBrains Mono' }, bodyFont: { family: 'JetBrains Mono' }, callbacks: { title: (i) => new Date(i[0].label).toLocaleTimeString(), label: (i) => ` H = ${Number(i.raw).toFixed(4)}` } },
      },
      scales: {
        x: { type: 'category', ticks: { color: '#4a5a6a', font: { family: 'JetBrains Mono', size: 10 }, maxTicksLimit: 8, maxRotation: 0, callback: (_, i, ticks) => { const l = ticks[i]?.label; return l ? new Date(l).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '' } }, grid: { color: '#1e2530' }, border: { color: '#1e2530' } },
        y: { min: 0, max: 8.5, ticks: { color: '#4a5a6a', font: { family: 'JetBrains Mono', size: 10 }, stepSize: 1 }, grid: { color: '#1e2530' }, border: { color: '#1e2530' } },
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
