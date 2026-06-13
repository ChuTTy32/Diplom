<template>
  <div class="stat-card" :class="variant">
    <div class="stat-top">
      <span class="stat-label">
        {{ label }}
        <span v-if="tip" class="info-tip" tabindex="0">ⓘ
          <!-- tip — наш статический текст из index.vue, не пользовательский ввод -->
          <span class="tip-bubble" v-html="tip" />
        </span>
      </span>
      <span class="stat-dot" />
    </div>
    <div class="stat-value mono">{{ value }}</div>
    <div v-if="sub" class="stat-sub">{{ sub }}</div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ label: string; value: string | number; sub?: string; variant?: string; tip?: string }>()
</script>
<style scoped>
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 18px 20px;
  transition: transform 0.18s ease, border-color 0.18s ease;
}
.stat-card:hover { transform: translateY(-2px); border-color: var(--border-2); }

.stat-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 14px; }
.stat-label { font-size: 11px; font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-dim); }
.stat-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--border-2); flex-shrink: 0; margin-top: 3px; }

.stat-value { font-size: 30px; font-weight: 600; line-height: 1; color: var(--text); letter-spacing: -0.02em; }
.stat-sub { font-size: 12px; color: var(--text-dim); margin-top: 8px; }

/* Состояния — цвет значения и точки */
.danger .stat-value { color: var(--danger); } .danger .stat-dot { background: var(--danger); box-shadow: 0 0 0 4px var(--danger-bg); }
.ok     .stat-value { color: var(--ok); }     .ok     .stat-dot { background: var(--ok);     box-shadow: 0 0 0 4px var(--ok-bg); }
.warn   .stat-value { color: var(--warn); }   .warn   .stat-dot { background: var(--warn);   box-shadow: 0 0 0 4px var(--warn-bg); }
.accent .stat-value { color: var(--accent); } .accent .stat-dot { background: var(--accent); box-shadow: 0 0 0 4px var(--accent-bg); }
</style>
