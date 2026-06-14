<template>
  <div class="dashboard">

    <!-- ─── HEADER ─────────────────────────────────────────────────── -->
    <header class="header">
      <div class="header-left">
        <span class="logo-mark">RG</span>
        <div>
          <div class="title">RansomGuard</div>
          <div class="subtitle">Система превентивной защиты резервных копий</div>
        </div>
      </div>
      <div class="header-right">
        <span class="pill" :class="connected ? 'is-ok' : 'is-danger'">
          {{ connected ? 'Подключено' : 'Нет связи' }}
        </span>
        <span class="clock mono">{{ clock }}</span>
      </div>
    </header>

    <!-- ─── STAT CARDS ─────────────────────────────────────────────── -->
    <section class="stats-grid">
      <StatCard
        label="Алерты (24ч)"
        :value="summary.total_alerts ?? '—'"
        :sub="summary.last_alert_time ? 'последний: ' + fmtRelative(summary.last_alert_time) : 'алертов нет'"
        :variant="(summary.total_alerts ?? 0) > 0 ? 'danger' : 'ok'"
        tip="Сколько раз за последние 24 часа энтропия изменённого файла
             превысила порог 7.2 бит — каждое такое событие является
             признаком возможного шифрования."
      />
      <StatCard
        label="Энтропия (ср. за 1ч)"
        :value="summary.avg_entropy_1h != null ? summary.avg_entropy_1h.toFixed(4) : '—'"
        :sub="'порог: ' + THRESHOLD + ' бит'"
        :variant="(summary.avg_entropy_1h ?? 0) >= THRESHOLD ? 'danger' : 'ok'"
        tip="Средняя энтропия Шеннона всех изменённых файлов за час.
             Обычные документы — 3–5 бит, зашифрованные — около 8.
             Рост среднего к порогу — массовое шифрование."
      />
      <StatCard
        label="RPO (факт)"
        :value="summary.rpo_minutes != null ? summary.rpo_minutes + ' мин' : '—'"
        sub="точка восстановления"
        :variant="rpoVariant"
        tip="<b>Recovery Point Objective</b> — максимальный объём данных,
             который будет потерян при атаке: время, прошедшее между двумя
             последними резервными копиями. Чем меньше — тем лучше."
      />
      <StatCard
        label="RTO (оценка)"
        :value="summary.rto_minutes != null ? summary.rto_minutes + ' мин' : '—'"
        sub="время восстановления"
        variant="accent"
        tip="<b>Recovery Time Objective</b> — расчётное время полного
             восстановления данных из архива: размер архива ÷ скорость
             чтения диска + накладные расходы BorgBackup."
      />
      <StatCard
        label="Последний бэкап"
        :value="summary.last_backup ? fmtRelative(summary.last_backup) : '—'"
        sub="BorgBackup WORM"
        :variant="lastBackupVariant"
        tip="Время последнего успешного архива. <b>WORM</b> (write once,
             read many) — режим дозаписи: архивы невозможно изменить или
             удалить даже при полной компрометации системы."
      />
      <StatCard
        label="События файлов"
        :value="entropyPoints.length"
        sub="уникальных за 60 мин"
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
      <AlertTable    :alerts="alertRows" />
      <BackupTable   :events="backupEvents" />
      <IncidentTable :incidents="incidentRows" />
    </section>

    <!-- ─── FOOTER ─────────────────────────────────────────────────── -->
    <footer class="footer">
      <span>НГАСУ (Сибстрин) · ВКР 09.03.02 · Защищённая система резервного копирования</span>
      <span class="dim">обновление каждые 5 с</span>
    </footer>

  </div>
</template>

<script setup lang="ts">
const THRESHOLD = 7.2

// ─── State ────────────────────────────────────────────────────────────
const connected     = ref(false)
const clock         = ref('')
const summary       = ref<any>({})
const entropyPoints = ref<any[]>([])
const systemPoints  = ref<any[]>([])
const alertRows     = ref<any[]>([])
const backupEvents  = ref<any[]>([])
const incidentRows  = ref<any[]>([])

// ─── API ──────────────────────────────────────────────────────────────
const { get } = useApi()

async function fetchAll() {
  try {
    const [sum, entropy, backup, system, incidents] = await Promise.all([
      get<any>('/metrics/summary'),
      get<any[]>('/metrics/entropy',  { minutes: 60 }),
      get<any[]>('/metrics/backup',   { limit: 30 }),
      get<any[]>('/metrics/system',   { minutes: 30 }),
      get<any[]>('/incidents/list',   { limit: 30 }),
    ])
    summary.value       = sum
    entropyPoints.value = entropy
    alertRows.value     = entropy.filter((e: any) => e.alert).slice(0, 50)
    backupEvents.value  = backup
    systemPoints.value  = system
    incidentRows.value  = incidents
    connected.value     = true
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
  // Метка времени в будущем (рассинхрон часов / битая запись) — не печатаем
  // «-20024 с назад», показываем нейтральное «только что».
  if (diff < 0) return 'только что'
  if (diff < 60) return diff + ' с назад'
  if (diff < 3600) return Math.floor(diff / 60) + ' мин назад'
  return Math.floor(diff / 3600) + ' ч назад'
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
let clockTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  const tick = () => {
    clock.value = new Date().toLocaleTimeString([], {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    })
  }
  tick()
  clockTimer = setInterval(tick, 1000)
})
onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px clamp(16px, 4vw, 40px) 28px;
}

/* ─── Header ─── */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.header-left { display: flex; align-items: center; gap: 14px; }
.logo-mark {
  width: 42px; height: 42px;
  display: grid; place-items: center;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--accent), #4f46e5);
  color: #fff; font-weight: 800; font-size: 16px; letter-spacing: 0.02em;
  box-shadow: 0 6px 18px -6px rgba(99,102,241,0.7);
}
.title { font-size: 18px; font-weight: 700; letter-spacing: -0.01em; color: var(--text); }
.subtitle { font-size: 12.5px; color: var(--text-dim); margin-top: 1px; }
.header-right { display: flex; align-items: center; gap: 14px; }
.clock { font-size: 13px; color: var(--text-2); }

/* ─── Sections (карточки с воздухом) ─── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 14px;
}
.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
.tables-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
/* IncidentTable — третий элемент, во всю ширину снизу */
.tables-grid > *:nth-child(3) { grid-column: 1 / -1; }

/* ─── Footer ─── */
.footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 4px 6px;
  font-size: 12px;
  color: var(--text-2);
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
