<template>
  <div class="page">
    <div class="page-card">
      <div class="toolbar">
        <n-input
          v-model:value="keyword"
          placeholder="搜索任务名称"
          clearable
          style="width: 220px"
          @keyup.enter="reload"
        />
        <n-select
          v-model:value="filterSource"
          :options="SOURCE_OPTIONS"
          clearable
          placeholder="数据来源"
          style="width: 140px"
          @update:value="reload"
        />
        <n-button @click="reload">查询</n-button>
        <div class="spacer" />
        <n-button v-if="can('compare:run')" type="primary" @click="openCreate">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          发起比对任务
        </n-button>
      </div>

      <n-data-table
        flex-height
        style="flex: 1; min-height: 0"
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="pagination"
        remote
        :row-key="(r: CompareTask) => r.id"
      />
    </div>

    <!-- 发起比对 -->
    <n-modal
      v-model:show="showCreate"
      preset="card"
      title="发起经纬度比对"
      style="width: 620px; max-width: 94vw"
      :mask-closable="false"
    >
      <n-alert type="info" :show-icon="false" size="small" style="margin-bottom: 14px">
        比对将把「申报坐标」与「采集几何中心（实测坐标）」逐条计算球面距离，超过阈值判为超差。
      </n-alert>
      <n-form ref="createFormRef" :model="createForm" :rules="createRules" label-placement="left" label-width="92">
        <n-form-item label="任务名称" path="name">
          <n-input v-model:value="createForm.name" placeholder="如 2026 年 10 月建筑比对" />
        </n-form-item>
        <n-form-item label="数据来源" path="source_type">
          <n-radio-group v-model:value="createForm.source_type">
            <n-radio-button v-for="s in SOURCE_OPTIONS" :key="s.value" :value="s.value">
              {{ s.label }}
            </n-radio-button>
          </n-radio-group>
        </n-form-item>
        <n-form-item v-if="createForm.source_type === 'feature'" label="信息模块">
          <n-select
            v-model:value="createForm.module_id"
            :options="moduleOptions"
            clearable
            placeholder="不选则比对全部模块"
          />
        </n-form-item>
        <n-form-item label="超差阈值" path="threshold_m">
          <n-input-number v-model:value="createForm.threshold_m" :min="0.1" :precision="2" style="width: 180px">
            <template #suffix>米</template>
          </n-input-number>
        </n-form-item>
        <n-form-item label="说明">
          <n-input
            v-model:value="createForm.description"
            type="textarea"
            :rows="2"
            placeholder="任务说明（可选）"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="form-footer">
          <n-button @click="showCreate = false">取消</n-button>
          <n-button type="primary" :loading="running" @click="runTask">开始比对</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 比对结果 -->
    <n-modal
      v-model:show="showDetail"
      preset="card"
      :title="detailTask ? `比对结果 - ${detailTask.name}` : '比对结果'"
      style="width: 1240px; max-width: 96vw"
      :mask-closable="false"
    >
      <div class="detail-head">
        <div class="detail-meta">
          <n-tag size="small" type="info">
            {{ detailTask?.source_type === 'building' ? '建筑物' : '采集要素' }}
          </n-tag>
          <span v-if="detailTask?.module_name">模块：{{ detailTask.module_name }}</span>
          <span>阈值：{{ detailTask?.threshold_m }} 米</span>
          <span>创建：{{ formatTime(detailTask?.created_at) }}</span>
          <span v-if="detailTask?.description">说明：{{ detailTask.description }}</span>
        </div>
        <div class="detail-stat">
          <n-tag :bordered="false">共 {{ detailTask?.total_count ?? 0 }} 条</n-tag>
          <n-tag type="success" :bordered="false">通过 {{ detailTask?.passed_count ?? 0 }}</n-tag>
          <n-tag type="error" :bordered="false">超差 {{ detailTask?.failed_count ?? 0 }}</n-tag>
          <n-tag type="warning" :bordered="false">
            异常 {{ (detailTask?.total_count ?? 0) - (detailTask?.passed_count ?? 0) - (detailTask?.failed_count ?? 0) }}
          </n-tag>
        </div>
      </div>

      <div class="detail-toolbar">
        <n-select
          v-model:value="issueFilter"
          :options="ISSUE_OPTIONS"
          clearable
          size="small"
          placeholder="全部结论"
          style="width: 170px"
        />
        <n-input v-model:value="itemKeyword" size="small" placeholder="搜索编号 / 名称" clearable style="width: 200px" />
        <span class="spacer" />
        <n-button v-if="can('compare:export')" size="small" @click="exportCsv()">
          <template #icon><n-icon><DownloadOutline /></n-icon></template>
          导出 CSV
        </n-button>
      </div>

      <div class="detail-body">
        <div class="detail-table">
          <n-data-table
            :columns="itemColumns"
            :data="filteredItems"
            :loading="detailLoading"
            size="small"
            :row-key="(r: CompareItem) => r.id"
            :row-props="itemRowProps"
            :max-height="420"
          />
        </div>
        <div class="detail-map">
          <MapView
            ref="detailMapRef"
            :center="mapCenter"
            :zoom="mapZoom"
            :max-zoom="mapMaxZoom"
          />
          <div class="map-legend">
            <span class="legend-item"><i class="dot" style="background: #18a058" />合格</span>
            <span class="legend-item"><i class="dot" style="background: #d03050" />超差</span>
            <span class="legend-item"><i class="dot" style="background: #999" />数据异常</span>
            <span class="legend-item">小点=申报 大点=实测</span>
          </div>
        </div>
      </div>
    </n-modal>

    <!-- 备注 -->
    <n-modal v-model:show="showRemark" preset="dialog" title="填写核查备注" positive-text="保存" negative-text="取消" @positive-click="saveRemark">
      <div class="remark-target">{{ remarkItem?.code || remarkItem?.name }}</div>
      <n-input v-model:value="remarkText" type="textarea" :rows="3" placeholder="核查情况说明" />
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onMounted, reactive, ref } from 'vue'
import { NButton, NIcon, NTag, type DataTableColumns, type FormInst, type FormRules } from 'naive-ui'
import {
  AddOutline,
  CreateOutline,
  DownloadOutline,
  EyeOutline,
  RefreshOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import {
  compareApi,
  moduleApi,
  type CompareItem,
  type CompareTask,
  type ModuleBrief,
} from '@/api'
import MapView from '@/components/map/MapView.vue'
import { useUserStore } from '@/store/user'
import { dialogConfirm, toastError, toastSuccess } from '@/utils/naive'
import { formatDateTime } from '@/utils/time'

const store = useUserStore()
const can = (code: string) => store.hasPerm(code)

const SOURCE_OPTIONS = [
  { label: '采集要素', value: 'feature' },
  { label: '建筑物', value: 'building' },
]
const ISSUE_OPTIONS = [
  { label: '合格', value: 'ok' },
  { label: '超差', value: 'over_threshold' },
  { label: '缺申报坐标', value: 'missing_declared' },
  { label: '缺实测坐标', value: 'missing_measured' },
  { label: '坐标非法', value: 'invalid_coord' },
]
const STATUS_LABELS: Record<string, string> = {
  done: '已完成',
  running: '进行中',
  pending: '待执行',
  failed: '失败',
}
const SOURCE_LABELS: Record<string, string> = { feature: '采集要素', building: '建筑物' }

const mapCenter = computed<[number, number]>(() => store.bootstrap?.center ?? [116.397428, 39.90923])
const mapZoom = computed(() => store.bootstrap?.zoom ?? 15)
const mapMaxZoom = computed(() => store.bootstrap?.max_zoom ?? 18)
const defaultThreshold = computed(() => store.bootstrap?.default_threshold_m ?? 10)

// ---------------- 任务列表 ----------------
const keyword = ref('')
const filterSource = ref<string | null>(null)
const rows = ref<CompareTask[]>([])
const loading = ref(false)
const pagination = reactive({
  page: 1,
  pageSize: 10,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
  onChange: (p: number) => {
    pagination.page = p
    load()
  },
  onUpdatePageSize: (s: number) => {
    pagination.pageSize = s
    pagination.page = 1
    load()
  },
})

async function load() {
  loading.value = true
  try {
    const res = await compareApi.tasks({
      keyword: keyword.value || undefined,
      source_type: filterSource.value || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    rows.value = res.items
    pagination.itemCount = res.total
  } catch (e) {
    toastError((e as Error).message || '加载比对任务失败')
  } finally {
    loading.value = false
  }
}
function reload() {
  pagination.page = 1
  load()
}

function formatTime(t?: string | null) {
  return formatDateTime(t)
}

const columns = computed<DataTableColumns<CompareTask>>(() => [
  { title: '任务名称', key: 'name', minWidth: 180, ellipsis: { tooltip: true } },
  {
    title: '数据来源',
    key: 'source_type',
    width: 100,
    render: (r) => SOURCE_LABELS[r.source_type] ?? r.source_type,
  },
  {
    title: '信息模块',
    key: 'module_name',
    width: 130,
    ellipsis: { tooltip: true },
    render: (r) => (r.source_type === 'building' ? '全部建筑物' : r.module_name || '全部模块'),
  },
  { title: '阈值(米)', key: 'threshold_m', width: 90 },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (r) =>
      h(
        NTag,
        { size: 'small', type: r.status === 'done' ? 'success' : r.status === 'failed' ? 'error' : 'info' },
        { default: () => STATUS_LABELS[r.status] ?? r.status },
      ),
  },
  {
    title: '通过 / 超差 / 总数',
    key: 'counts',
    width: 150,
    render: (r) =>
      h('span', null, [
        h('span', { style: 'color:#18a058' }, String(r.passed_count)),
        ' / ',
        h('span', { style: 'color:#d03050' }, String(r.failed_count)),
        ' / ',
        String(r.total_count),
      ]),
  },
  { title: '创建时间', key: 'created_at', width: 160, render: (r) => formatTime(r.created_at) },
  {
    title: '操作',
    key: 'actions',
    width: 210,
    render: (r) =>
      h('div', { style: 'display:flex;gap:2px' }, [
        h(
          NButton,
          { size: 'tiny', quaternary: true, type: 'primary', title: '查看结果', onClick: () => openDetail(r) },
          { icon: () => h(NIcon, null, { default: () => h(EyeOutline) }), default: () => '查看' },
        ),
        can('compare:run')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'info', title: '重新比对', onClick: () => rerun(r) },
              { icon: () => h(NIcon, null, { default: () => h(RefreshOutline) }) },
            )
          : null,
        can('compare:export')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, title: '导出 CSV', onClick: () => exportCsv(r) },
              { icon: () => h(NIcon, null, { default: () => h(DownloadOutline) }) },
            )
          : null,
        can('compare:delete')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'error', title: '删除任务', onClick: () => remove(r) },
              { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }) },
            )
          : null,
      ]),
  },
])

// ---------------- 发起比对 ----------------
const showCreate = ref(false)
const running = ref(false)
const createFormRef = ref<FormInst | null>(null)
const moduleOptions = ref<{ label: string; value: number }[]>([])
const createForm = reactive({
  name: '',
  source_type: 'feature',
  module_id: null as number | null,
  threshold_m: 10,
  description: '',
})
const createRules: FormRules = {
  name: { required: true, message: '请输入任务名称', trigger: ['blur', 'input'] },
  threshold_m: { required: true, type: 'number', message: '请输入超差阈值', trigger: ['blur', 'change'] },
}

async function loadModules() {
  try {
    const list: ModuleBrief[] = await moduleApi.brief()
    moduleOptions.value = list.map((m) => ({ label: `${m.name}（${m.code}）`, value: m.id }))
  } catch {
    moduleOptions.value = []
  }
}

function todayName() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} 经纬度比对`
}

function openCreate() {
  Object.assign(createForm, {
    name: todayName(),
    source_type: 'feature',
    module_id: null,
    threshold_m: defaultThreshold.value,
    description: '',
  })
  showCreate.value = true
}

async function runTask() {
  try {
    await createFormRef.value?.validate()
  } catch {
    return
  }
  running.value = true
  try {
    const res = await compareApi.run({
      name: createForm.name.trim(),
      source_type: createForm.source_type,
      module_id: createForm.source_type === 'feature' ? createForm.module_id : null,
      threshold_m: createForm.threshold_m,
      description: createForm.description || null,
      source_ids: [],
    })
    showCreate.value = false
    toastSuccess(
      `比对完成：共 ${res.total_count} 条，通过 ${res.passed_count}，超差 ${res.failed_count}`,
    )
    reload()
    openDetail(res as CompareTask)
  } catch (e) {
    toastError((e as Error).message || '比对任务执行失败')
  } finally {
    running.value = false
  }
}

async function rerun(task: CompareTask) {
  try {
    await compareApi.rerun(task.id)
    toastSuccess('已重新执行比对')
    reload()
  } catch (e) {
    toastError((e as Error).message || '重新比对失败')
  }
}

function remove(task: CompareTask) {
  dialogConfirm(`确认删除比对任务「${task.name}」及其全部明细？`, async () => {
    try {
      await compareApi.remove(task.id)
      toastSuccess('已删除')
      reload()
    } catch (e) {
      toastError((e as Error).message || '删除失败')
    }
  })
}

async function exportCsv(task?: CompareTask) {
  const target = task ?? detailTask.value
  if (!target) return
  try {
    const blob = await compareApi.exportBlob(target.id)
    // 接口异常时后端返回的是 JSON，避免把错误信息当成 CSV 下载
    if (blob.type && blob.type.includes('json')) {
      const text = await blob.text()
      let message = '导出失败'
      try {
        message = (JSON.parse(text) as { message?: string }).message || message
      } catch {
        /* 忽略解析失败 */
      }
      toastError(message)
      return
    }
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `比对结果_${target.name}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1500)
  } catch (e) {
    toastError((e as Error).message || '导出失败')
  }
}

// ---------------- 比对结果 ----------------
const showDetail = ref(false)
const detailLoading = ref(false)
const detailTask = ref<CompareTask | null>(null)
const detailItems = ref<CompareItem[]>([])
const issueFilter = ref<string | null>(null)
const itemKeyword = ref('')
const selectedItemId = ref<number | null>(null)
const detailMapRef = ref<InstanceType<typeof MapView> | null>(null)

const filteredItems = computed(() => {
  const kw = itemKeyword.value.trim().toLowerCase()
  return detailItems.value.filter((i) => {
    if (issueFilter.value && i.issue !== issueFilter.value) return false
    if (!kw) return true
    return (i.code || '').toLowerCase().includes(kw) || (i.name || '').toLowerCase().includes(kw)
  })
})

async function openDetail(task: CompareTask) {
  showDetail.value = true
  detailTask.value = task
  detailItems.value = []
  issueFilter.value = null
  itemKeyword.value = ''
  selectedItemId.value = null
  await nextTick()
  await loadDetail(task.id)
  await loadDetailMap(task.id)
}

async function loadDetail(taskId: number) {
  detailLoading.value = true
  try {
    const data = await compareApi.taskDetail(taskId)
    detailTask.value = data
    detailItems.value = data.items ?? []
  } catch (e) {
    toastError((e as Error).message || '加载比对明细失败')
  } finally {
    detailLoading.value = false
  }
}

async function loadDetailMap(taskId: number) {
  try {
    const data = await compareApi.map(taskId)
    await nextTick()
    const items = [
      ...data.points.map((s) => ({ ...s, kind: s.kind ?? 'point' })),
      ...data.lines.map((s) => ({ ...s, kind: 'measure' })),
    ].map((s) => ({
      id: s.id,
      geometry: s.geometry,
      color: s.color,
      label: s.label,
      kind: s.kind,
      onClick: () => {
        selectedItemId.value = s.pair_id
      },
    }))
    if (!items.length) {
      detailMapRef.value?.clearLayer('compare-layer')
      return
    }
    detailMapRef.value?.renderPlain(items, 'compare-layer')
    const coords = data.points
      .map((p) => {
        const c = (p.geometry as { coordinates?: number[] }).coordinates
        return c && c.length >= 2 ? ([c[0], c[1]] as [number, number]) : null
      })
      .filter((c): c is [number, number] => !!c)
    if (coords.length) detailMapRef.value?.fitPoints(coords, 60)
  } catch (e) {
    toastError((e as Error).message || '加载比对地图失败')
  }
}

function itemRowProps(row: CompareItem) {
  return {
    style: row.id === selectedItemId.value ? 'background:#e8f1ff' : '',
    onClick: () => {
      selectedItemId.value = row.id
      if (row.measured_lng != null && row.measured_lat != null) {
        detailMapRef.value?.panTo(row.measured_lng, row.measured_lat, 18)
      } else if (row.declared_lng != null && row.declared_lat != null) {
        detailMapRef.value?.panTo(row.declared_lng, row.declared_lat, 18)
      }
    },
  }
}

const itemColumns = computed<DataTableColumns<CompareItem>>(() => [
  { title: '编号', key: 'code', width: 110, ellipsis: { tooltip: true } },
  { title: '名称', key: 'name', minWidth: 120, ellipsis: { tooltip: true } },
  {
    title: '申报坐标',
    key: 'declared',
    width: 150,
    render: (r) =>
      r.declared_lng != null && r.declared_lat != null
        ? `${r.declared_lng.toFixed(6)}, ${r.declared_lat.toFixed(6)}`
        : '-',
  },
  {
    title: '实测坐标',
    key: 'measured',
    width: 150,
    render: (r) =>
      r.measured_lng != null && r.measured_lat != null
        ? `${r.measured_lng.toFixed(6)}, ${r.measured_lat.toFixed(6)}`
        : '-',
  },
  {
    title: '偏差(米)',
    key: 'deviation_m',
    width: 90,
    render: (r) => (r.deviation_m != null ? r.deviation_m : '-'),
  },
  {
    title: '方位',
    key: 'bearing',
    width: 90,
    render: (r) =>
      r.bearing_text ? `${r.bearing_text}${r.bearing_deg != null ? ` ${r.bearing_deg}°` : ''}` : '-',
  },
  {
    title: '结论',
    key: 'issue',
    width: 110,
    render: (r) =>
      h(
        NTag,
        {
          size: 'small',
          type: r.issue === 'ok' ? 'success' : r.issue === 'over_threshold' ? 'error' : 'warning',
        },
        { default: () => r.issue_label || r.issue || '-' },
      ),
  },
  {
    title: '备注',
    key: 'remark',
    width: 150,
    ellipsis: { tooltip: true },
    render: (r) =>
      h(
        NButton,
        { size: 'tiny', quaternary: true, type: 'primary', onClick: () => openRemark(r) },
        {
          icon: () => h(NIcon, null, { default: () => h(CreateOutline) }),
          default: () => r.remark || '填写',
        },
      ),
  },
])

const showRemark = ref(false)
const remarkItem = ref<CompareItem | null>(null)
const remarkText = ref('')

function openRemark(item: CompareItem) {
  remarkItem.value = item
  remarkText.value = item.remark || ''
  showRemark.value = true
}

async function saveRemark() {
  const item = remarkItem.value
  if (!item) return
  try {
    await compareApi.updateItem(item.id, remarkText.value || null)
    item.remark = remarkText.value || null
    toastSuccess('备注已保存')
  } catch (e) {
    toastError((e as Error).message || '保存备注失败')
  }
}

onMounted(async () => {
  await Promise.all([loadModules(), load()])
})
</script>

<style scoped>
.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.detail-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  color: #666;
  font-size: 13px;
}
.detail-stat {
  display: flex;
  gap: 8px;
}
.detail-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.detail-toolbar .spacer {
  flex: 1;
}
.detail-body {
  display: flex;
  gap: 12px;
  min-height: 440px;
}
.detail-table {
  flex: 1;
  min-width: 0;
}
.detail-map {
  width: 420px;
  height: 440px;
  flex: none;
  position: relative;
  border-radius: 6px;
  overflow: hidden;
}
.map-legend {
  position: absolute;
  left: 12px;
  top: 12px;
  z-index: 10;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  max-width: calc(100% - 24px);
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--ink-600);
  box-shadow: 0 8px 20px -14px rgba(15, 23, 42, 0.5);
  pointer-events: none;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
}
.remark-target {
  color: #666;
  font-size: 13px;
  margin-bottom: 8px;
}
</style>
