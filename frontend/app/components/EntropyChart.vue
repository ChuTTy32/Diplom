<template>
  <div class="chart-wrap panel">
    <div class="panel-head">
      <span class="panel-title">
        Энтропия файлов <span class="dim" style="font-weight:400">(H, бит)</span>
        <span class="info-tip" tabindex="0">ⓘ
          <span class="tip-bubble">
            <b>Энтропия Шеннона</b> H&nbsp;=&nbsp;−Σ&nbsp;p·log₂(p) — мера
            случайности содержимого файла.<br><br>
            Обычные документы и код — <b>3–5 бит</b>, сжатые архивы — ~7,
            зашифрованные шифровальщиком данные — <b>почти 8 бит</b>
            (все байты равновероятны).<br><br>
            Превышение порога {{ threshold }} бит — признак шифрования:
            агент регистрирует алерт.
          </span>
        </span>
      </span>
      <span class="pill is-muted no-dot">порог {{ threshold }}</span>
    </div>
    <div class="chart-body">
      <div class="legend">
        <span class="lg"><i class="sw" style="background:#818cf8" />энтропия файла</span>
        <span class="lg"><i class="sw sw-dot" style="background:#fb7185" />алерт (H ≥ {{ threshold }})</span>
        <span class="lg"><i class="sw sw-dash" />порог {{ threshold }} бит</span>
      </div>
      <canvas ref="canvas" />
    </div>
  </div>
</template>
<script setup lang="ts">
import { Chart, LineController, LineElement, PointElement, LinearScale, Filler, Tooltip, CategoryScale } from 'chart.js'
Chart.register(LineController, LineElement, PointElement, LinearScale, Filler, Tooltip, CategoryScale)
const props = defineProps<{ points: Array<{ time: string; entropy: number; alert: boolean }>; threshold: number }>()
const canvas = ref<HTMLCanvasElement | null>(null)
let chart: Chart | null = null

const GRID = 'rgba(255,255,255,0.06)'
const TICK = '#6b7384'

function buildChart() {
  if (!canvas.value) return
  const ctx = canvas.value.getContext('2d')!
  const gradient = ctx.createLinearGradient(0, 0, 0, 220)
  gradient.addColorStop(0, 'rgba(129,140,248,0.22)')
  gradient.addColorStop(1, 'rgba(129,140,248,0)')
  chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'Entropy', data: [], borderColor: '#818cf8', borderWidth: 2, backgroundColor: gradient, fill: true, tension: 0.35, pointRadius: 0 },
        { label: 'Alerts', data: [], borderColor: 'transparent', backgroundColor: 'transparent', pointRadius: 5, pointHoverRadius: 6, pointBackgroundColor: '#fb7185', pointBorderColor: '#fff', pointBorderWidth: 1, showLine: false },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: '#20242e', borderColor: 'rgba(255,255,255,0.13)', borderWidth: 1, padding: 10, cornerRadius: 8, titleColor: '#aab1c0', bodyColor: '#e6e8ee', titleFont: { family: 'Inter', size: 11 }, bodyFont: { family: 'JetBrains Mono', size: 12 }, displayColors: false, callbacks: { title: (i) => new Date(i[0].label).toLocaleTimeString(), label: (i) => ` H = ${Number(i.raw).toFixed(4)}` } },
      },
      scales: {
        x: { type: 'category', ticks: { color: TICK, font: { family: 'Inter', size: 10 }, maxTicksLimit: 8, maxRotation: 0, callback: (_, i, ticks) => { const l = ticks[i]?.label; return l ? new Date(l).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '' } }, grid: { color: GRID }, border: { display: false } },
        y: { min: 0, max: 8.5, ticks: { color: TICK, font: { family: 'JetBrains Mono', size: 10 }, stepSize: 2 }, grid: { color: GRID }, border: { display: false } },
      },
    },
    plugins: [{ id: 'thr', afterDraw(c) { const { ctx, chartArea, scales } = c; const y = scales.y.getPixelForValue(props.threshold); ctx.save(); ctx.setLineDash([5,5]); ctx.strokeStyle = 'rgba(251,191,36,0.6)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(chartArea.left, y); ctx.lineTo(chartArea.right, y); ctx.stroke(); ctx.restore(); } }],
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
.chart-wrap { height: 300px; }
.chart-body { flex: 1; display: flex; flex-direction: column; padding: 16px 20px; min-height: 0; }
canvas { flex: 1; min-height: 0; }
</style>
