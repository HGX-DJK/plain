<template>
  <div class="page dashboard">
    <section class="hero">
      <div class="hero-bg"></div>
      <div class="hero-inner">
        <div class="hero-left">
          <span class="hero-eyebrow">空间数据总览</span>
          <h1>{{ greeting }}，{{ displayName }}</h1>
          <p>
            当前系统已沉淀 <b>{{ summary.feature_total }}</b> 条采集要素、<b>{{ summary.building_total }}</b> 栋建筑物、
            <b>{{ summary.unit_total }}</b> 家单位，其中 <b>{{ summary.building_unlinked }}</b> 栋建筑尚未关联单位。
          </p>
          <div class="hero-actions">
            <n-button type="primary" @click="go('/collect')">开始采集</n-button>
            <n-button class="ghost-btn" @click="go('/compare')">发起比对</n-button>
          </div>
        </div>

        <div class="hero-right">
          <div
            class="ring"
            :style="{
              background: `conic-gradient(#ffffff ${linkRate * 3.6}deg, rgba(255, 255, 255, 0.2) 0deg)`,
            }"
          >
            <div class="ring-inner">
              <strong>{{ linkRate }}%</strong>
              <span>建筑关联率</span>
            </div>
          </div>
          <div class="hero-kpis">
            <div class="kpi">
              <span>信息模块</span>
              <strong>{{ summary.module_total }}</strong>
            </div>
            <div class="kpi">
              <span>已关联建筑</span>
              <strong>{{ summary.building_linked }}</strong>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="stat-grid">
      <div v-for="s in stats" :key="s.key" class="stat-card">
        <div class="stat-icon" :style="{ color: s.color, background: s.bg }">
          <n-icon :size="20"><component :is="s.icon" /></n-icon>
        </div>
        <div class="stat-content">
          <span class="stat-label">{{ s.label }}</span>
          <strong class="stat-value">{{ s.value }}</strong>
        </div>
      </div>
    </section>

    <section class="panels">
      <div class="page-card panel">
        <header class="panel-head">
          <h3>按空间类型统计</h3>
          <span class="panel-extra">共 {{ summary.feature_total }} 条要素</span>
        </header>
        <n-empty v-if="!summary.features_by_geom?.length" description="暂无采集数据" size="small" />
        <div v-else class="geom-list">
          <div v-for="row in summary.features_by_geom" :key="row.geom_type" class="geom-row">
            <span class="geom-name">
              <i class="dot" :style="{ background: geomColor(row.geom_type) }"></i>
              {{ geomLabel(row.geom_type) }}
            </span>
            <div class="bar">
              <span
                :style="{
                  width: barWidth(row.count) + '%',
                  background: `linear-gradient(90deg, ${geomColor(row.geom_type)}, ${geomColor(row.geom_type)}bb)`,
                }"
              ></span>
            </div>
            <span class="geom-count">{{ row.count }}</span>
          </div>
        </div>
      </div>

      <div class="page-card panel">
        <header class="panel-head">
          <h3>最近比对任务</h3>
          <n-button text type="primary" size="small" @click="go('/compare')">查看全部</n-button>
        </header>
        <n-empty v-if="!summary.recent_tasks?.length" description="暂无比对任务" size="small" />
        <n-table v-else :bordered="false" size="small" :single-line="false" class="task-table">
          <thead>
            <tr>
              <th>任务名称</th>
              <th>状态</th>
              <th style="text-align: right">通过 / 总数</th>
              <th>创建时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in summary.recent_tasks" :key="t.id">
              <td class="task-name">{{ t.name }}</td>
              <td>
                <n-tag size="small" :type="statusType(t.status)" :bordered="false">
                  {{ statusLabel(t.status) }}
                </n-tag>
              </td>
              <td style="text-align: right">
                <span class="pass">{{ t.passed_count }}</span>
                <span class="slash">/</span>
                <span>{{ t.total_count }}</span>
              </td>
              <td class="time">{{ formatTime(t.created_at) }}</td>
            </tr>
          </tbody>
        </n-table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { Component } from 'vue'
import {
  AlertCircleOutline,
  BusinessOutline,
  CheckmarkCircleOutline,
  LayersOutline,
  MapOutline,
  PeopleOutline,
} from '@vicons/ionicons5'
import { dashboardApi, type DashboardSummary } from '@/api'
import { useUserStore } from '@/store/user'
import { toastError } from '@/utils/naive'

const router = useRouter()
const store = useUserStore()

const summary = ref<DashboardSummary>({
  module_total: 0,
  feature_total: 0,
  building_total: 0,
  unit_total: 0,
  building_linked: 0,
  building_unlinked: 0,
  recent_tasks: [],
  features_by_geom: [],
})

const displayName = computed(() => store.info?.real_name || store.info?.username || '管理员')

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const linkRate = computed(() => {
  const total = summary.value.building_total
  if (!total) return 0
  return Math.round((summary.value.building_linked / total) * 100)
})

interface StatCard {
  key: string
  label: string
  value: number
  icon: Component
  color: string
  bg: string
}

const stats = computed<StatCard[]>(() => [
  {
    key: 'module',
    label: '信息模块',
    value: summary.value.module_total,
    icon: LayersOutline,
    color: '#2f6bff',
    bg: 'rgba(47, 107, 255, 0.1)',
  },
  {
    key: 'feature',
    label: '采集要素',
    value: summary.value.feature_total,
    icon: MapOutline,
    color: '#0ea5b7',
    bg: 'rgba(14, 165, 183, 0.1)',
  },
  {
    key: 'building',
    label: '建筑物',
    value: summary.value.building_total,
    icon: BusinessOutline,
    color: '#7c5cff',
    bg: 'rgba(124, 92, 255, 0.1)',
  },
  {
    key: 'unit',
    label: '单位',
    value: summary.value.unit_total,
    icon: PeopleOutline,
    color: '#f0a020',
    bg: 'rgba(240, 160, 32, 0.12)',
  },
  {
    key: 'linked',
    label: '已关联建筑',
    value: summary.value.building_linked,
    icon: CheckmarkCircleOutline,
    color: '#18a058',
    bg: 'rgba(24, 160, 88, 0.1)',
  },
  {
    key: 'unlinked',
    label: '未关联建筑',
    value: summary.value.building_unlinked,
    icon: AlertCircleOutline,
    color: '#e5484d',
    bg: 'rgba(229, 72, 77, 0.1)',
  },
])

const GEOM_LABELS: Record<string, string> = { point: '点要素', line: '线要素', polygon: '面要素' }
const GEOM_COLORS: Record<string, string> = {
  point: '#2f6bff',
  line: '#18a058',
  polygon: '#f0a020',
}

function geomLabel(g: string) {
  return GEOM_LABELS[g] ?? '未分类'
}
function geomColor(g: string) {
  return GEOM_COLORS[g] ?? '#94a3b8'
}
function barWidth(count: number) {
  const max = Math.max(...summary.value.features_by_geom.map((r) => r.count), 1)
  return Math.max(4, Math.round((count / max) * 100))
}

const STATUS_LABELS: Record<string, string> = {
  done: '已完成',
  running: '进行中',
  pending: '待执行',
  failed: '失败',
}
function statusLabel(s: string) {
  return STATUS_LABELS[s] ?? s
}
function statusType(s: string): 'success' | 'error' | 'warning' | 'info' | 'default' {
  if (s === 'done') return 'success'
  if (s === 'failed') return 'error'
  if (s === 'running') return 'info'
  return 'default'
}
function formatTime(t?: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 16)
}

function go(path: string) {
  router.push(path)
}

onMounted(async () => {
  try {
    summary.value = await dashboardApi.summary()
  } catch (e) {
    toastError((e as Error).message || '加载汇总数据失败')
  }
})
</script>

<style scoped lang="scss">
/* ---------------- Hero ---------------- */
.hero {
  position: relative;
  flex: none;
  border-radius: 20px;
  overflow: hidden;
  color: #fff;
  background:
    radial-gradient(90% 130% at 100% 0%, rgba(92, 148, 255, 0.85) 0%, rgba(92, 148, 255, 0) 55%),
    linear-gradient(120deg, #172a52 0%, #1b3a7a 45%, #2f6bff 100%);
  box-shadow: 0 26px 50px -34px rgba(31, 85, 220, 0.95);
}

.hero-bg {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 46px 46px;
  mask-image: radial-gradient(70% 120% at 90% 10%, #000 0%, transparent 75%);
  pointer-events: none;
}

.hero-inner {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  padding: 30px 34px;
}

.hero-eyebrow {
  display: inline-block;
  font-size: 11.5px;
  letter-spacing: 2px;
  color: rgba(255, 255, 255, 0.55);
  margin-bottom: 10px;
}

.hero-left h1 {
  margin: 0 0 10px;
  font-size: 26px;
  font-weight: 600;
  letter-spacing: 0.6px;
}

.hero-left p {
  margin: 0 0 20px;
  max-width: 620px;
  font-size: 13.5px;
  line-height: 1.85;
  color: rgba(255, 255, 255, 0.72);
}
.hero-left p b {
  color: #fff;
  font-weight: 600;
  padding: 0 2px;
}

.hero-actions {
  display: flex;
  gap: 10px;
}
.hero-actions :deep(.n-button--primary-type) {
  background: #fff;
  color: #1f55dc;
  border-color: #fff;
}
.hero-actions :deep(.n-button--primary-type:hover) {
  background: #eef4ff;
  color: #1f55dc;
}

.ghost-btn {
  color: #fff;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.4);
}
.ghost-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.24);
  border-color: rgba(255, 255, 255, 0.65);
}

.hero-right {
  display: flex;
  align-items: center;
  gap: 26px;
  flex: none;
}

.ring {
  width: 122px;
  height: 122px;
  border-radius: 50%;
  padding: 9px;
  display: grid;
  place-items: center;
  box-shadow: 0 12px 26px -18px rgba(0, 0, 0, 0.75);
}

.ring-inner {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 30%, #24478c 0%, #1a3466 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
}
.ring-inner strong {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.ring-inner span {
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.6);
}

.hero-kpis {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.kpi {
  min-width: 122px;
  padding: 10px 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(6px);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.kpi span {
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.62);
}
.kpi strong {
  font-size: 20px;
  font-weight: 600;
}

/* ---------------- 统计卡 ---------------- */
.stat-grid {
  flex: none;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 16px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid var(--line);
  box-shadow: var(--shadow-card);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 32px -22px rgba(15, 23, 42, 0.5);
}

.stat-icon {
  width: 42px;
  height: 42px;
  flex: none;
  border-radius: 12px;
  display: grid;
  place-items: center;
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.stat-label {
  font-size: 12px;
  color: var(--ink-500);
  white-space: nowrap;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink-900);
  line-height: 1.2;
}

.stat-card::after {
  content: '';
  position: absolute;
  right: -20px;
  bottom: -28px;
  width: 62px;
  height: 62px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.04;
}

/* ---------------- 下方面板 ---------------- */
.panels {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  gap: 16px;
  flex: 1;
  min-height: 280px;
}

.panel {
  padding: 18px 20px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.panel-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink-900);
  position: relative;
  padding-left: 10px;
}
.panel-head h3::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 14px;
  border-radius: 3px;
  background: linear-gradient(180deg, var(--brand-500), var(--brand-700));
}
.panel-extra {
  font-size: 12px;
  color: var(--ink-400);
}

.geom-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 4px;
}

.geom-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.geom-name {
  width: 78px;
  flex: none;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: var(--ink-600);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.bar {
  flex: 1;
  height: 10px;
  border-radius: 6px;
  background: #f0f3f9;
  overflow: hidden;
}
.bar span {
  display: block;
  height: 100%;
  border-radius: 6px;
  transition: width 0.5s ease;
}

.geom-count {
  width: 56px;
  flex: none;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-800);
}

.task-table {
  table-layout: fixed;
}
.task-table :deep(th) {
  font-size: 12px;
  color: var(--ink-500);
  font-weight: 500;
  background: transparent;
}
.task-table :deep(td) {
  font-size: 13px;
}
.task-table :deep(th:nth-child(1)),
.task-table :deep(td:nth-child(1)) {
  width: 42%;
}
.task-table :deep(th:nth-child(2)),
.task-table :deep(td:nth-child(2)) {
  width: 17%;
}
.task-table :deep(th:nth-child(3)),
.task-table :deep(td:nth-child(3)) {
  width: 21%;
}
.task-table :deep(th:nth-child(4)),
.task-table :deep(td:nth-child(4)) {
  width: 20%;
}
.task-name {
  color: var(--ink-800);
  font-weight: 500;
}
.pass {
  color: #18a058;
  font-weight: 600;
}
.slash {
  color: var(--ink-300);
  margin: 0 3px;
}
.time {
  color: var(--ink-400);
  font-size: 12px;
  white-space: nowrap;
}

@media (max-width: 1400px) {
  .stat-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .panels {
    grid-template-columns: minmax(0, 1fr);
  }
  .hero-right {
    display: none;
  }
}

@media (max-width: 760px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
