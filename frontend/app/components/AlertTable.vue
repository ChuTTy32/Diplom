<template>
  <div class="table-wrap panel">
    <div class="panel-head">
      <span class="panel-title">Журнал алертов</span>
      <span class="pill" :class="alerts.length ? 'is-danger' : 'is-ok'">
        {{ alerts.length ? alerts.length + ' активных' : 'чисто' }}
      </span>
    </div>
    <div class="table-scroll">
      <table class="tbl">
        <thead><tr><th>Время</th><th>Файл</th><th>Энтропия</th><th>Размер</th><th>Хост</th></tr></thead>
        <tbody>
          <tr v-for="row in alerts" :key="row.time+row.file_path" :class="{ 'row-alert': row.alert }">
            <td class="mono time-cell">{{ fmtTime(row.time) }}</td>
            <td class="path-cell" :title="row.file_path">{{ shortPath(row.file_path) }}</td>
            <td class="mono" :class="eClass(row.entropy)">{{ row.entropy.toFixed(4) }}</td>
            <td class="mono dim">{{ fmtSize(row.file_size) }}</td>
            <td class="mono dim">{{ row.host }}</td>
          </tr>
          <tr v-if="!alerts.length"><td colspan="5" class="no-data">алертов нет</td></tr>
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
.table-wrap { max-height: 340px; }
.table-scroll { overflow-y: auto; flex: 1; }
.row-alert { background: var(--danger-bg); }
.row-alert:hover { background: rgba(251,113,133,0.18); }
.time-cell { color: var(--text-2); }
.path-cell { max-width: 240px; overflow: hidden; text-overflow: ellipsis; color: var(--text); }
</style>
