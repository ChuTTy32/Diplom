<template>
  <div class="table-wrap panel">
    <div class="panel-head">
      <span class="panel-title">Журнал инцидентов</span>
      <span class="pill" :class="hasCritical ? 'is-danger' : hasWarning ? 'is-warn' : 'is-ok'">
        {{ hasCritical ? 'критично' : hasWarning ? 'внимание' : 'чисто' }}
      </span>
    </div>
    <div class="table-scroll">
      <table class="tbl">
        <thead>
          <tr>
            <th>Время</th><th>Уровень</th><th>Действие</th><th>Триггер</th><th>Энтропия</th><th>Хост</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in incidents"
            :key="row.id"
            :class="row.severity === 'critical' ? 'row-critical' : 'row-warning'"
          >
            <td class="mono time-cell">{{ fmtTime(row.time) }}</td>
            <td><span class="pill" :class="row.severity === 'critical' ? 'is-danger' : 'is-warn'">{{ sevLabel(row.severity) }}</span></td>
            <td class="mono action-cell" :class="actionClass(row.action_taken)">{{ actionLabel(row.action_taken) }}</td>
            <td class="trigger-cell" :title="row.trigger_file">{{ shortTrigger(row.trigger_file) }}</td>
            <td class="mono" :class="eClass(row.entropy)">
              <!-- 0.0 = eBPF (поведенческая детекция, контент не измерялся) -->
              {{ row.entropy ? row.entropy.toFixed(4) : '—' }}
            </td>
            <td class="mono dim">{{ row.host }}</td>
          </tr>
          <tr v-if="!incidents.length">
            <td colspan="6" class="no-data">инцидентов нет</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Incident {
  id: number
  time: string
  severity: string
  trigger_file: string
  entropy: number | null
  alert_count: number
  action_taken: string
  host: string
}

const props = defineProps<{ incidents: Incident[] }>()

const hasCritical = computed(() => props.incidents.some(i => i.severity === 'critical'))
const hasWarning  = computed(() => props.incidents.some(i => i.severity === 'warning'))

const fmtTime = (t: string) =>
  new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

const shortTrigger = (t: string) => {
  if (!t) return '—'
  if (t.startsWith('[eBPF]')) return t.replace('[eBPF] ', '')
  const parts = t.split('/')
  return parts.length > 3 ? '…/' + parts.slice(-2).join('/') : t
}

const actionClass = (a: string) => {
  if (a === 'lockdown')         return 'danger'
  if (a === 'emergency_backup') return 'warn'
  return 'dim'
}

// Значения в БД остаются англ. (API-контракт), на экране — русский
const sevLabel = (s: string) =>
  ({ critical: 'критично', warning: 'предупр.' }[s] ?? s)

const actionLabel = (a: string) =>
  ({ lockdown: 'блокировка', emergency_backup: 'экстр. бэкап', logged: 'записано' }[a] ?? a)

const eClass = (e: number | null) => {
  if (!e)        return 'dim'
  if (e >= 7.9)  return 'danger'
  if (e >= 7.2)  return 'warn'
  return 'ok'
}
</script>

<style scoped>
.table-wrap { max-height: 320px; }
.table-scroll { overflow-y: auto; flex: 1; }
.row-critical { background: var(--danger-bg); }
.row-critical:hover { background: rgba(251,113,133,0.18); }
.row-warning  { background: var(--warn-bg); }
.row-warning:hover  { background: rgba(251,191,36,0.2); }
.time-cell    { color: var(--text-2); }
.trigger-cell { max-width: 260px; overflow: hidden; text-overflow: ellipsis; color: var(--text); }
.action-cell  { font-size: 12px; }
</style>
