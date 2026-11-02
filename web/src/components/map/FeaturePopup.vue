<template>
  <div
    class="feature-popup"
    :class="`is-${placement}`"
    :style="anchorStyle"
    role="dialog"
    aria-label="要素属性信息"
    @click.stop
    @dblclick.stop
    @mousedown.stop
    @wheel.stop
  >
    <span class="popup-caret" aria-hidden="true" />

    <header class="popup-head">
      <span class="popup-mark" aria-hidden="true" />
      <div class="popup-heading">
        <p class="popup-title" :title="title">{{ title }}</p>
        <p v-if="subtitle" class="popup-sub" :title="subtitle">{{ subtitle }}</p>
      </div>
      <button class="popup-close" type="button" aria-label="关闭" @click="emit('close')">
        <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">
          <path
            d="M6 6l12 12M18 6L6 18"
            fill="none"
            stroke="currentColor"
            stroke-width="2.4"
            stroke-linecap="round"
          />
        </svg>
      </button>
    </header>

    <div v-if="badges && badges.length" class="popup-badges">
      <span v-for="badge in badges" :key="badge" class="popup-badge">{{ badge }}</span>
    </div>

    <div v-if="rows.length" class="popup-body">
      <dl class="popup-rows">
        <div v-for="row in rows" :key="row.label" class="popup-row">
          <dt>{{ row.label }}</dt>
          <dd>{{ row.value }}</dd>
        </div>
      </dl>
    </div>

    <footer v-if="hint" class="popup-foot">{{ hint }}</footer>
  </div>
</template>

<script setup lang="ts">
/** 地图要素属性弹窗：纯展示，定位与数据由 MapView 负责。 */
import { computed } from 'vue'
import { withAlpha, type PopupData } from './featurePopup'

const props = defineProps<PopupData>()
const emit = defineEmits<{ close: [] }>()

const anchorStyle = computed<Record<string, string>>(() => {
  const accent = props.accent || '#2d6cdf'
  return {
    left: `${props.x}px`,
    top: `${props.y}px`,
    '--accent': accent,
    '--accent-soft': withAlpha(accent, 0.1),
    '--accent-line': withAlpha(accent, 0.24),
  }
})
</script>

<style scoped>
.feature-popup {
  position: absolute;
  z-index: 12;
  width: 292px;
  max-width: calc(100% - 24px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid var(--line-strong, #dfe5ef);
  border-radius: 14px;
  box-shadow:
    0 20px 44px -20px rgba(15, 23, 42, 0.45),
    0 2px 8px rgba(15, 23, 42, 0.06);
  font-size: 13px;
  color: var(--ink-700, #334155);
  line-height: 1.5;
  pointer-events: auto;
}
.feature-popup.is-top {
  transform: translate(-50%, calc(-100% - 14px));
  transform-origin: bottom center;
}
.feature-popup.is-bottom {
  transform: translate(-50%, 14px);
  transform-origin: top center;
}

.popup-caret {
  position: absolute;
  left: 50%;
  width: 11px;
  height: 11px;
  background: #fff;
  border: 1px solid var(--line-strong, #dfe5ef);
  transform: translateX(-50%) rotate(45deg);
}
.is-top .popup-caret {
  bottom: -7px;
  border-top: 0;
  border-left: 0;
}
.is-bottom .popup-caret {
  top: -7px;
  background: var(--accent-soft);
  border-bottom: 0;
  border-right: 0;
}

/* ---------- 头部 ---------- */
.popup-head {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 11px 12px 10px;
  border-bottom: 1px solid var(--line, #e9edf5);
  border-radius: 13px 13px 0 0;
  background: linear-gradient(180deg, var(--accent-soft), #fff 78%);
}
.popup-mark {
  flex: none;
  width: 9px;
  height: 9px;
  margin-top: 5px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.popup-heading {
  flex: 1;
  min-width: 0;
}
.popup-title {
  margin: 0;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink-900, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.popup-sub {
  margin: 2px 0 0;
  font-size: 11.5px;
  color: var(--ink-500, #64748b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.popup-close {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin: -2px -3px 0 0;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--ink-400, #94a3b8);
  cursor: pointer;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}
.popup-close:hover {
  background: rgba(15, 23, 42, 0.06);
  color: var(--ink-700, #334155);
}
.popup-close:focus-visible {
  outline: 2px solid var(--accent-line);
  outline-offset: 1px;
}

/* ---------- 标签 ---------- */
.popup-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 9px 12px 0;
}
.popup-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.2px;
  white-space: nowrap;
}

/* ---------- 属性列表 ---------- */
.popup-body {
  max-height: min(46vh, 268px);
  overflow: auto;
  overscroll-behavior: contain;
}
.popup-rows {
  margin: 0;
  padding: 8px 12px 10px;
}
.popup-row {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 5px 6px;
  border-radius: 7px;
}
.popup-row:nth-child(odd) {
  background: #f8fafc;
}
.popup-row dt {
  color: var(--ink-500, #64748b);
  font-size: 12px;
  line-height: 1.6;
}
.popup-row dd {
  margin: 0;
  color: var(--ink-800, #1e293b);
  font-size: 12.5px;
  line-height: 1.6;
  overflow-wrap: anywhere;
  word-break: break-word;
}

/* ---------- 底部 ---------- */
.popup-foot {
  padding: 6px 12px 7px;
  border-top: 1px solid var(--line, #e9edf5);
  border-radius: 0 0 13px 13px;
  background: #fbfcfe;
  color: var(--ink-400, #94a3b8);
  font-size: 11px;
  letter-spacing: 0.1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
