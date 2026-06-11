<template>
  <div class="table-wrap">
    <div class="table-header">
      <span class="mono">ЖУРНАЛ АЛЕРТОВ</span>
      <span class="badge danger mono" v-if="alerts.length">{{ alerts.length }} АКТИВНЫХ</span>
      <span class="badge ok mono" v-else>ЧИСТО</span>
    </div>
    <div class="table-scroll">
      <table>
        <thead><tr><th class="mono">ВРЕМЯ</th><th class="mono">ФАЙЛ</th><th class="mono">ЭНТРОПИЯ</th><th class="mono">РАЗМЕР</th><th class="mono">ХОСТ</th></tr></thead>
        <tbody>
          <tr v-for="row in alerts" :key="row.time+row.file_path" :class="{ 'row-alert': row.alert }">
            <td class="mono time-cell">{{ fmtTime(row.time) }}</td>
            <td class="path-cell" :title="row.file_path">{{ shortPath(row.file_path) }}</td>
            <td class="mono" :class="eClass(row.entropy)">{{ row.entropy.toFixed(4) }}</td>
            <td class="mono dim">{{ fmtSize(row.file_size) }}</td>
            <td class="mono dim">{{ row.host }}</td>
          </tr>
          <tr v-if="!alerts.length"><td colspan="5" class="no-data mono dim">— алертов нет —</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ alerts: Array<{ time: string; file_path: string; entropy: number; file_size: number|null; alert: boolean; host: string }> }>()
const fmtTime = (t: string) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const shortPath = (p: string) => { const parts = p.split('/'); return parts.length > 3 ? '…/' + parts.slice(-2).join('/') : p }
const fmtSize = (b: number|null) => { if (!b) return '—'; if (b > 1048576) return (b/1048576).toFixed(1)+' МБ'; if (b > 1024) return (b/1024).toFixed(1)+' КБ'; return b+' Б' }
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
