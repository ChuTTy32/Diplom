<template>
  <div class="table-wrap">
    <div class="table-header">
      <span class="mono">ЖУРНАЛ ИНЦИДЕНТОВ</span>
      <span class="badge mono" :class="hasCritical ? 'critical' : hasWarning ? 'warning' : 'ok'">
        {{ hasCritical ? 'КРИТИЧНО' : hasWarning ? 'ВНИМАНИЕ' : 'ЧИСТО' }}
      </span>
    </div>
    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th class="mono">ВРЕМЯ</th>
            <th class="mono">УРОВЕНЬ</th>
            <th class="mono">ДЕЙСТВИЕ</th>
            <th class="mono">ТРИГГЕР</th>
            <th class="mono">ЭНТРОПИЯ</th>
            <th class="mono">ХОСТ</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in incidents"
            :key="row.id"
            :class="row.severity === 'critical' ? 'row-critical' : 'row-warning'"
          >
            <td class="mono time-cell">{{ fmtTime(row.time) }}</td>
            <td>
              <span class="sev-badge mono" :class="row.severity">
                {{ sevLabel(row.severity) }}
              </span>
            </td>
            <td class="mono action-cell" :class="actionClass(row.action_taken)">
              {{ actionLabel(row.action_taken) }}
            </td>
            <td class="trigger-cell" :title="row.trigger_file">
              {{ shortTrigger(row.trigger_file) }}
            </td>
            <td class="mono" :class="eClass(row.entropy)">
              {{ row.entropy != null ? row.entropy.toFixed(4) : '—' }}
            </td>
            <td class="mono dim">{{ row.host }}</td>
          </tr>
          <tr v-if="!incidents.length">
            <td colspan="6" class="no-data mono dim">— инцидентов нет —</td>
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
  // eBPF-события: "[eBPF] proc=... pid=... file=..."
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
  ({ critical: 'КРИТИЧНО', warning: 'ПРЕДУПР.' }[s] ?? s.toUpperCase())

const actionLabel = (a: string) =>
  ({ lockdown: 'БЛОКИРОВКА', emergency_backup: 'ЭКСТР. БЭКАП', logged: 'ЗАПИСАНО' }[a] ?? a)

const eClass = (e: number | null) => {
  if (e == null) return 'dim'
  if (e >= 7.9)  return 'danger'
  if (e >= 7.2)  return 'warn'
  return 'ok'
}
</script>

<style scoped>
.table-wrap {
  background: var(--bg2);
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  max-height: 300px;
}
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border);
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--text-dim);
  text-transform: uppercase;
  flex-shrink: 0;
}
.badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 2px;
  letter-spacing: 0.08em;
}
.badge.critical { background: rgba(255,59,92,0.15);  color: var(--danger); border: 1px solid var(--danger2); }
.badge.warning  { background: rgba(255,170,0,0.12);  color: var(--warn);   border: 1px solid #7a5000; }
.badge.ok       { background: rgba(0,230,118,0.1);   color: var(--ok);     border: 1px solid var(--ok2); }

.table-scroll { overflow-y: auto; flex: 1; }
table { width: 100%; border-collapse: collapse; }
thead th {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: var(--text-dim);
  padding: 8px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--bg2);
}
tbody td {
  padding: 7px 14px;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
.row-critical { background: rgba(255,59,92,0.04); }
.row-critical:hover { background: rgba(255,59,92,0.08); }
.row-warning  { background: rgba(255,170,0,0.03); }
.row-warning:hover  { background: rgba(255,170,0,0.07); }

.time-cell    { color: var(--text-mono); }
.trigger-cell { max-width: 220px; overflow: hidden; text-overflow: ellipsis; color: var(--text); }
.action-cell  { text-transform: uppercase; font-size: 11px; letter-spacing: 0.06em; }
.no-data      { text-align: center; padding: 24px; font-size: 12px; }

.sev-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 2px;
  letter-spacing: 0.06em;
}
.sev-badge.critical { background: rgba(255,59,92,0.15); color: var(--danger); }
.sev-badge.warning  { background: rgba(255,170,0,0.12); color: var(--warn); }
</style>
