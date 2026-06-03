<template>
  <div class="stat-card" :class="variant">
    <div class="stat-label mono">{{ label }}</div>
    <div class="stat-value">{{ value }}</div>
    <div v-if="sub" class="stat-sub dim">{{ sub }}</div>
    <div class="stat-line" />
  </div>
</template>
<script setup lang="ts">
defineProps<{ label: string; value: string | number; sub?: string; variant?: string }>()
</script>
<style scoped>
.stat-card { background: var(--bg2); border: 1px solid var(--border); padding: 20px 24px; position: relative; overflow: hidden; transition: border-color 0.2s; }
.stat-card:hover { border-color: var(--border2); }
.stat-label { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px; }
.stat-value { font-family: var(--font-mono); font-size: 28px; line-height: 1; margin-bottom: 6px; color: var(--text); }
.stat-sub { font-size: 11px; margin-top: 4px; }
.stat-line { position: absolute; bottom: 0; left: 0; right: 0; height: 2px; background: var(--border2); }
.danger .stat-value { color: var(--danger); } .danger .stat-line { background: var(--danger2); }
.ok .stat-value { color: var(--ok); }         .ok .stat-line { background: var(--ok2); }
.warn .stat-value { color: var(--warn); }      .warn .stat-line { background: #b87a00; }
.accent .stat-value { color: var(--accent); }  .accent .stat-line { background: var(--accent2); }
</style>
