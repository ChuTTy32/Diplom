<template>
  <div class="table-wrap">
    <div class="table-header mono">СОБЫТИЯ БЭКАПОВ</div>
    <div class="table-scroll">
      <table>
        <thead><tr><th class="mono">ВРЕМЯ</th><th class="mono">СТАТУС</th><th class="mono">АРХИВ</th><th class="mono">ДЛИТ.</th><th class="mono">RPO</th><th class="mono">RTO</th></tr></thead>
        <tbody>
          <tr v-for="row in events" :key="row.time">
            <td class="mono time-cell">{{ fmtTime(row.time) }}</td>
            <td><span class="status-badge mono" :class="row.event_type">{{ statusLabel(row.event_type) }}</span></td>
            <td class="mono dim archive-cell" :title="row.archive_name">{{ shortArchive(row.archive_name) }}</td>
            <td class="mono">{{ row.duration_sec != null ? row.duration_sec+' с' : '—' }}</td>
            <td class="mono" :class="rpoClass(row.rpo_minutes)">{{ row.rpo_minutes != null ? row.rpo_minutes+' мин' : '—' }}</td>
            <td class="mono dim">{{ row.rto_minutes != null ? row.rto_minutes+' мин' : '—' }}</td>
          </tr>
          <tr v-if="!events.length"><td colspan="6" class="no-data mono dim">— событий нет —</td></tr>
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
// event_type из БД остаётся англ. (CSS-классы), на экране — русский
const statusLabel = (t: string) => ({ success: 'УСПЕХ', fail: 'ОШИБКА', start: 'СТАРТ' }[t] ?? t.toUpperCase())
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
