<template>
  <div class="table-wrap panel">
    <div class="panel-head">
      <span class="panel-title">События резервного копирования</span>
    </div>
    <div class="table-scroll">
      <table class="tbl">
        <thead><tr><th>Время</th><th>Статус</th><th>Архив</th><th>Длит.</th><th>RPO</th><th>RTO</th></tr></thead>
        <tbody>
          <tr v-for="row in events" :key="row.time">
            <td class="mono time-cell">{{ fmtTime(row.time) }}</td>
            <td><span class="pill" :class="statusPill(row.event_type)">{{ statusLabel(row.event_type) }}</span></td>
            <td class="mono dim archive-cell" :title="row.archive_name">{{ shortArchive(row.archive_name) }}</td>
            <td class="mono">{{ row.duration_sec != null ? row.duration_sec+' с' : '—' }}</td>
            <td class="mono" :class="rpoClass(row.rpo_minutes)">{{ row.rpo_minutes != null ? row.rpo_minutes+' мин' : '—' }}</td>
            <td class="mono dim">{{ row.rto_minutes != null ? row.rto_minutes+' мин' : '—' }}</td>
          </tr>
          <tr v-if="!events.length"><td colspan="6" class="no-data">событий нет</td></tr>
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
const statusPill = (t: string) => ({ success: 'is-ok', fail: 'is-danger', start: 'is-accent' }[t] ?? 'is-muted')
// event_type из БД остаётся англ. (API-контракт), на экране — русский
const statusLabel = (t: string) => ({ success: 'успех', fail: 'ошибка', start: 'старт' }[t] ?? t)
</script>
<style scoped>
.table-wrap { max-height: 300px; }
.table-scroll { overflow-y: auto; flex: 1; }
.time-cell { color: var(--text-2); }
.archive-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
