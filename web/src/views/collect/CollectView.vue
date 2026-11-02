<template>
  <div class="page">
    <div class="map-page">
      <div class="side-panel">
      <div class="panel-section target-section">
        <div class="target-row">
          <div class="section-title target-title">采集目标</div>
          <n-select
            v-model:value="selectedModuleId"
            :options="moduleOptions"
            :title="selectedModule ? `${selectedModule.name}（${selectedModule.code}）` : ''"
            placeholder="选择信息模块"
            size="small"
            @update:value="onModuleChange"
          />
          <template v-if="selectedModule">
            <span class="color-dot" :style="{ background: selectedModule.color }" />
            <n-tag size="small" type="info" :bordered="false" :title="`几何类型：${GEOM_LABELS[selectedModule.geom_type]}`">
              {{ GEOM_LABELS[selectedModule.geom_type] }}
            </n-tag>
          </template>
        </div>
        <div class="draw-btns">
          <n-button
            v-if="!drawing && !shapingNew && can('feature:create')"
            type="primary"
            block
            :disabled="!selectedModule"
            @click="beginDraw"
          >
            <template #icon><n-icon><PencilOutline /></n-icon></template>
            绘制{{ selectedModule ? GEOM_LABELS[selectedModule.geom_type] : '' }}要素
          </n-button>
          <n-button v-if="drawing || shapingBusy" type="warning" block @click="cancelDraw">
            取消绘制（Esc）
          </n-button>
          <n-alert v-if="drawing || shapingBusy" type="info" :show-icon="false" size="small">
            在地图上单击/拖动绘制，双击或再次单击结束
          </n-alert>
          <n-alert v-if="shapingNew" type="success" :show-icon="false" size="small">
            面状要素可「挖洞」或「添加飞地」，完成后再填写属性
          </n-alert>
        </div>
      </div>

      <div class="panel-section layer-section">
        <div class="section-title">
          图层
          <span v-if="layerTotalCount" class="list-count">显示 {{ layerCheckedCount }}/{{ layerTotalCount }}</span>
        </div>
        <div v-if="modules.length" class="layer-toolbar">
          <n-input
            v-model:value="layerKeyword"
            size="small"
            placeholder="搜索图层名称/编码"
            clearable
          />
          <n-checkbox
            :checked="allLayersChecked"
            :indeterminate="someLayersChecked"
            @update:checked="toggleAllVisible"
          >
            全选
          </n-checkbox>
        </div>
        <div v-if="!modules.length" class="empty-hint">暂无模块，请先在「信息模块管理」中创建</div>
        <div v-else class="layer-list">
          <div v-for="m in filteredModules" :key="m.id" class="layer-row" @click="selectedModuleId = m.id; onModuleChange()">
            <n-checkbox
              :checked="visibleIds.includes(m.id)"
              @update:checked="toggleVisible(m.id, $event)"
              @click.stop
            />
            <span class="color-dot" :style="{ background: m.color }" />
            <span class="layer-name">{{ m.name }}</span>
            <n-tag size="tiny" :bordered="false">{{ GEOM_LABELS[m.geom_type] }}</n-tag>
          </div>
          <div v-if="!filteredModules.length" class="empty-hint">没有匹配的图层</div>
        </div>
      </div>

      <div class="panel-section list-section">
        <div class="section-title">
          要素列表
          <span v-if="selectedModule" class="list-count">共 {{ listTotal }} 条</span>
        </div>
        <div class="list-toolbar">
          <n-input v-model:value="listKeyword" size="small" placeholder="搜索名称/编号" clearable @keyup.enter="reloadList" />
          <n-button size="small" @click="reloadList">查询</n-button>
        </div>
        <div class="list-body">
          <n-data-table
            v-if="selectedModule"
            :columns="listColumns"
            :data="listRows"
            :loading="listLoading"
            size="small"
            :pagination="listPagination"
            remote
            :row-key="(r: FeatureItem) => r.id"
            :row-props="rowProps"
          />
          <n-empty v-else description="请先选择信息模块" size="small" style="margin-top: 40px" />
        </div>
      </div>
    </div>

    <div class="map-panel">
      <MapView
        ref="mapRef"
        :center="mapCenter"
        :zoom="mapZoom"
        :max-zoom="mapMaxZoom"
        :field-labels="fieldLabels"
        :on-feature-click="onMapFeatureClick"
        :on-view-change="onViewChange"
      />
      <div class="map-status" :class="{ 'is-loading': mapLoading }">
        <span class="status-dot" />
        <span class="status-text">{{ mapStatus }}</span>
        <n-button text size="tiny" :disabled="mapLoading" @click="loadGroups()">重新取数</n-button>
      </div>
      <div v-if="shapingNew" class="shape-bar">
        <div class="shape-info">
          <span class="shape-badge">面要素</span>
          <span class="shape-text">可继续挖洞或添加飞地</span>
          <span class="shape-count">面片 {{ shapeInfo.parts }} · 洞 {{ shapeInfo.holes }}</span>
        </div>
        <div class="shape-actions">
          <n-button size="small" :loading="shapingBusy" @click="pendingAddHole">挖洞</n-button>
          <n-button size="small" :loading="shapingBusy" @click="pendingAddPart">添加飞地</n-button>
          <n-button size="small" :disabled="shapingBusy" @click="pendingUndoRing">撤销上一环</n-button>
          <n-button size="small" @click="pendingCancel">取消</n-button>
          <n-button size="small" type="primary" @click="pendingFinish">填写属性</n-button>
        </div>
      </div>
      <div v-else-if="editingShapeId" class="shape-bar">
        <div class="shape-info">
          <span class="shape-badge is-warning">形状编辑</span>
          <span class="shape-text">拖动顶点改形状，单击边线插点</span>
          <span v-if="selectedModule?.geom_type === 'polygon'" class="shape-count">
            面片 {{ shapeInfo.parts }} · 洞 {{ shapeInfo.holes }}
          </span>
        </div>
        <div class="shape-actions">
          <template v-if="selectedModule?.geom_type === 'polygon'">
            <n-button size="small" :loading="shapingBusy" @click="editAddHole">挖洞</n-button>
            <n-button size="small" :loading="shapingBusy" @click="editAddPart">添加飞地</n-button>
            <n-button size="small" :disabled="shapingBusy" @click="editUndoRing">撤销上一环</n-button>
          </template>
          <n-button size="small" @click="cancelShape">取消</n-button>
          <n-button size="small" type="primary" :loading="savingShape" @click="saveShape">保存形状</n-button>
        </div>
      </div>
    </div>
    </div>

    <n-modal v-model:show="showForm" preset="card" :title="editingFeature ? '编辑采集数据' : '保存采集数据'" style="width: 620px; max-width: 94vw" :mask-closable="false">
      <n-form ref="formRef" :model="form" :rules="formRules" label-placement="left" label-width="92">
        <n-grid :cols="2" :x-gap="16">
          <n-form-item-gi label="要素名称" path="name">
            <n-input v-model:value="form.name" placeholder="要素名称" />
          </n-form-item-gi>
          <n-form-item-gi label="数据编号" path="code">
            <n-input v-model:value="form.code" placeholder="留空自动生成" :disabled="!!editingFeature" />
          </n-form-item-gi>
          <n-form-item-gi label="状态">
            <n-select v-model:value="form.status" :options="STATUS_OPTIONS" />
          </n-form-item-gi>
          <n-form-item-gi label="申报经度">
            <n-input-number v-model:value="form.declared_lng" :precision="8" placeholder="自动取形心" style="width: 100%" />
          </n-form-item-gi>
          <n-form-item-gi label="申报纬度">
            <n-input-number v-model:value="form.declared_lat" :precision="8" placeholder="自动取形心" style="width: 100%" />
          </n-form-item-gi>
        </n-grid>

        <template v-if="selectedModuleFull?.fields?.length">
          <n-divider title-placement="left">属性信息</n-divider>
          <n-grid :cols="2" :x-gap="16">
            <n-form-item-gi
              v-for="f in selectedModuleFull.fields"
              :key="f.key"
              :label="f.label"
              :path="`props.${f.key}`"
              :rule="fieldRule(f)"
            >
              <n-input
                v-if="f.data_type === 'string'"
                v-model:value="form.props[f.key]"
                :placeholder="f.placeholder || `请输入${f.label}`"
              />
              <n-input-number
                v-else-if="f.data_type === 'integer' || f.data_type === 'number'"
                v-model:value="form.props[f.key]"
                :precision="f.data_type === 'integer' ? 0 : undefined"
                :placeholder="f.placeholder || `请输入${f.label}`"
                style="width: 100%"
              />
              <n-switch v-else-if="f.data_type === 'boolean'" v-model:value="form.props[f.key]" />
              <n-date-picker
                v-else-if="f.data_type === 'date'"
                v-model:value="form.props[f.key]"
                type="date"
                value-format="yyyy-MM-dd"
                style="width: 100%"
              />
              <n-select
                v-else-if="f.data_type === 'select'"
                v-model:value="form.props[f.key]"
                :options="f.options ?? []"
                clearable
              />
              <n-input v-else v-model:value="form.props[f.key]" />
            </n-form-item-gi>
          </n-grid>
        </template>

        <n-form-item label="备注">
          <n-input v-model:value="form.remark" type="textarea" :rows="2" placeholder="备注信息（可选）" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="form-footer">
          <n-button @click="closeForm">取消</n-button>
          <n-button type="primary" :loading="saving" @click="saveFeature">保存</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { NButton, NIcon, type DataTableColumns, type FormInst, type FormRules } from 'naive-ui'
import { CreateOutline, LocateOutline, PencilOutline, ShapesOutline, TrashOutline } from '@vicons/ionicons5'
import {
  featureApi,
  moduleApi,
  type FeatureItem,
  type FeatureMapGroup,
  type FieldDef,
  type InfoModule,
  type ModuleBrief,
} from '@/api'
import MapView from '@/components/map/MapView.vue'
import type { MapViewport } from '@/components/map/viewport'
import { useUserStore } from '@/store/user'
import { dialogConfirm, toastError, toastSuccess } from '@/utils/naive'

const store = useUserStore()
const can = (code: string) => store.hasPerm(code)

const GEOM_LABELS: Record<string, string> = { point: '点', line: '线', polygon: '面' }
const STATUS_OPTIONS = [
  { label: '草稿', value: 'draft' },
  { label: '已核实', value: 'verified' },
]

// ---------------- 底图配置（瓦片地址见 public/js/config.js） ----------------
const mapCenter = computed<[number, number]>(() => store.bootstrap?.center ?? [116.397428, 39.90923])
const mapZoom = computed(() => store.bootstrap?.zoom ?? 15)
const mapMaxZoom = computed(() => store.bootstrap?.max_zoom ?? 18)

// ---------------- 模块与图层 ----------------
const mapRef = ref<InstanceType<typeof MapView> | null>(null)
const modules = ref<ModuleBrief[]>([])
const selectedModuleId = ref<number | null>(null)
const selectedModuleFull = ref<InfoModule | null>(null)
const visibleIds = ref<number[]>([])
const groups = ref<FeatureMapGroup[]>([])
/** 各模块字段定义：地图属性卡里把属性 key 显示成中文字段名 */
const fieldLabels = ref<Record<number, Record<string, string>>>({})

const moduleOptions = computed(() =>
  modules.value.map((m) => ({ label: `${m.name}（${m.code}）`, value: m.id })),
)
const selectedModule = computed(() => modules.value.find((m) => m.id === selectedModuleId.value) ?? null)

// ---------------- 图层搜索与全选 ----------------
const layerKeyword = ref('')
const filteredModules = computed(() => {
  const kw = layerKeyword.value.trim().toLowerCase()
  if (!kw) return modules.value
  return modules.value.filter(
    (m) => m.name.toLowerCase().includes(kw) || m.code.toLowerCase().includes(kw),
  )
})
/** 图层标题上的计数：已勾选显示 / 全部采集图层 */
const layerCheckedCount = computed(() => visibleIds.value.length)
const layerTotalCount = computed(() => modules.value.length)
const allLayersChecked = computed(() => {
  if (!filteredModules.value.length) return false
  return filteredModules.value.every((m) => visibleIds.value.includes(m.id))
})
/** 当前筛选结果中部分勾选时，全选框显示为半选态 */
const someLayersChecked = computed(() => {
  const total = filteredModules.value.length
  const checked = filteredModules.value.filter((m) => visibleIds.value.includes(m.id)).length
  return checked > 0 && checked < total
})

/** 全选/取消全选：只作用于当前搜索过滤后的采集图层，新出现的图层按需补取 */
function toggleAllVisible(checked: boolean) {
  const ids = filteredModules.value.map((m) => m.id)
  if (checked) {
    const before = visibleIds.value
    visibleIds.value = Array.from(new Set([...before, ...ids]))
    const missing = visibleIds.value.filter((id) => !before.includes(id))
    if (missing.length) loadGroups(missing, true)
    else renderVisible()
  } else {
    visibleIds.value = visibleIds.value.filter((id) => !ids.includes(id))
    groups.value = groups.value.filter((g) => visibleIds.value.includes(g.module_id))
    renderVisible()
  }
}

async function loadModules() {
  try {
    modules.value = await moduleApi.brief()
    if (!selectedModuleId.value && modules.value.length) {
      selectedModuleId.value = modules.value[0].id
    }
    visibleIds.value = modules.value.map((m) => m.id)
    await loadFullModule()
  } catch (e) {
    toastError((e as Error).message || '加载模块失败')
  }
}

/** 拉取各模块字段定义，供地图属性卡把属性 key 显示成中文字段名；失败时回退为原始 key */
async function loadFieldLabels() {
  try {
    const res = await moduleApi.list({ page: 1, page_size: 500 })
    const labels: Record<number, Record<string, string>> = {}
    for (const m of res.items ?? []) {
      if (!m.fields?.length) continue
      labels[m.id] = Object.fromEntries(m.fields.map((f) => [f.key, f.label]))
    }
    fieldLabels.value = labels
  } catch {
    fieldLabels.value = {}
  }
}

async function loadFullModule() {
  const m = modules.value.find((x) => x.id === selectedModuleId.value)
  if (!m) {
    selectedModuleFull.value = null
    return
  }
  try {
    selectedModuleFull.value = await moduleApi.detail(m.id)
  } catch {
    selectedModuleFull.value = null
  }
}

async function loadGroups(ids?: number[], merge = false) {
  const targets = ids ?? visibleIds.value
  if (!targets.length) {
    groups.value = []
    mapRef.value?.renderGroups([])
    return
  }
  const view = mapRef.value?.getViewport() ?? null
  mapLoading.value = true
  try {
    // 按视野取数：col_feature 已 47 万余条，全量取会让大模块吃满额度、点位一条不剩
    const opts: { bbox?: [number, number, number, number]; perModule?: number } = {}
    if (view) {
      opts.bbox = view.bbox
      opts.perModule = perModuleByZoom(view.zoom)
    }
    const loaded = await featureApi.map(targets, opts)
    if (merge) {
      // 保持「模块列表」顺序作为图层压盖顺序，只替换本次取到的模块
      const byId = new Map(groups.value.map((g) => [g.module_id, g]))
      for (const g of loaded) byId.set(g.module_id, g)
      groups.value = modules.value
        .map((m) => byId.get(m.id))
        .filter((g): g is FeatureMapGroup => !!g)
    } else {
      groups.value = loaded
    }
    renderVisible()
  } catch (e) {
    toastError((e as Error).message || '加载地图数据失败')
  } finally {
    mapLoading.value = false
  }
}

/** 缩放级别越小视野越大，单模块取数上限相应收敛，避免一次拖图搬回几万个图形 */
function perModuleByZoom(zoom: number): number {
  if (zoom >= 17) return 1500
  if (zoom >= 15) return 600
  if (zoom >= 13) return 250
  if (zoom >= 11) return 120
  return 60
}

const mapLoading = ref(false)
const loadedCount = computed(() => groups.value.reduce((n, g) => n + (g.features?.length ?? 0), 0))
/** 地图左上角的状态条：视野内取了多少条、是否有图层被截断 */
const mapStatus = computed(() => {
  if (mapLoading.value) return '视野取数中…'
  if (!visibleIds.value.length) return '未勾选显示图层'
  if (!groups.value.length) return '当前视野内暂无采集数据'
  const cut = groups.value.filter((g) => g.truncated).length
  const base = `视野内 ${loadedCount.value} 条 · ${groups.value.length} 个图层`
  // 截断是因为单次响应有总量上限（按图层均分），缩小视野或减少勾选即可看全
  return cut ? `${base} · ${cut} 个图层数据较多，可放大地图或只勾选需要的图层` : base
})

/** 视野稳定后按新范围重新取数；拖拽/滚轮过程中不重复请求 */
let viewTimer: ReturnType<typeof setTimeout> | null = null
function onViewChange(_view: MapViewport) {
  if (viewTimer) clearTimeout(viewTimer)
  viewTimer = setTimeout(() => {
    viewTimer = null
    // 绘制或形状编辑进行中不重刷图层：重刷会替换正在编辑的图形对象，顶点手柄会失效
    if (drawing.value || shapingBusy.value || shapingNew.value || editingShapeId.value) return
    loadGroups()
  }, 420)
}
onBeforeUnmount(() => {
  if (viewTimer) clearTimeout(viewTimer)
  viewTimer = null
})

function renderVisible() {
  const visible = groups.value.filter((g) => visibleIds.value.includes(g.module_id))
  mapRef.value?.renderGroups(visible)
}

function toggleVisible(moduleId: number, checked: boolean) {
  if (checked) {
    if (visibleIds.value.includes(moduleId)) return
    visibleIds.value.push(moduleId)
    // 只补取这一个图层，避免为了一层重刷全部图层
    loadGroups([moduleId], true)
  } else {
    visibleIds.value = visibleIds.value.filter((id) => id !== moduleId)
    groups.value = groups.value.filter((g) => g.module_id !== moduleId)
    renderVisible()
  }
}

function onModuleChange() {
  if (shapingNew.value) pendingCancel()
  if (drawing.value) cancelDraw()
  if (editingShapeId.value) cancelShape()
  loadFullModule()
  reloadList()
}

// ---------------- 绘制 ----------------
const drawing = ref(false)
/** 面要素刚绘制完、尚未填写属性的形状确认状态（支持挖洞 / 飞地） */
const shapingNew = ref(false)
const shapingBusy = ref(false)

async function beginDraw() {
  const m = selectedModule.value
  if (!m || !mapRef.value) return
  if (shapingNew.value) pendingCancel()
  drawing.value = true
  try {
    const gj = await mapRef.value.startDraw(m.geom_type, m.color)
    if (!gj) return
    if (m.geom_type === 'polygon') {
      // 面要素先进入形状确认，可继续挖洞 / 添加飞地
      pendingGeometry.value = gj
      shapingNew.value = true
      mapRef.value.previewGeometry(gj, m.color)
    } else {
      openCreateForm(gj)
    }
  } catch (e) {
    toastError((e as Error).message || '绘制失败')
  } finally {
    drawing.value = false
  }
}
function cancelDraw() {
  mapRef.value?.cancelDraw()
  drawing.value = false
  shapingBusy.value = false
}

/** 新建要素：挖洞 */
async function pendingAddHole() {
  const m = selectedModule.value
  if (!pendingGeometry.value || !m || !mapRef.value) return
  shapingBusy.value = true
  try {
    const gj = await mapRef.value.startDrawHole(pendingGeometry.value, m.color)
    if (gj) pendingGeometry.value = gj
  } catch (e) {
    toastError((e as Error).message || '挖洞失败')
  } finally {
    shapingBusy.value = false
  }
}

/** 新建要素：添加飞地面片 */
async function pendingAddPart() {
  const m = selectedModule.value
  if (!pendingGeometry.value || !m || !mapRef.value) return
  shapingBusy.value = true
  try {
    const gj = await mapRef.value.startDrawPart(pendingGeometry.value, m.color)
    if (gj) pendingGeometry.value = gj
  } catch (e) {
    toastError((e as Error).message || '添加飞地失败')
  } finally {
    shapingBusy.value = false
  }
}

function pendingUndoRing() {
  const m = selectedModule.value
  if (!pendingGeometry.value || !m) return
  const gj = mapRef.value?.undoLastRing(pendingGeometry.value, m.color)
  if (gj) pendingGeometry.value = gj
}

function pendingFinish() {
  if (!pendingGeometry.value) return
  shapingNew.value = false
  openCreateForm(pendingGeometry.value)
}

function pendingCancel() {
  shapingNew.value = false
  pendingGeometry.value = null
  mapRef.value?.clearPreview()
}

// ---------------- 要素列表 ----------------
const listRows = ref<FeatureItem[]>([])
const listLoading = ref(false)
const listTotal = ref(0)
const listKeyword = ref('')
const listPagination = reactive({
  page: 1,
  pageSize: 10,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [5, 10, 20],
  onChange: (p: number) => {
    listPagination.page = p
    loadList()
  },
  onUpdatePageSize: (s: number) => {
    listPagination.pageSize = s
    listPagination.page = 1
    loadList()
  },
})

async function loadList() {
  if (!selectedModuleId.value) {
    listRows.value = []
    listTotal.value = 0
    return
  }
  listLoading.value = true
  try {
    const res = await featureApi.list({
      module_id: selectedModuleId.value,
      keyword: listKeyword.value || undefined,
      page: listPagination.page,
      page_size: listPagination.pageSize,
    })
    listRows.value = res.items
    listTotal.value = res.total
    listPagination.itemCount = res.total
  } catch (e) {
    toastError((e as Error).message || '加载要素列表失败')
  } finally {
    listLoading.value = false
  }
}
function reloadList() {
  listPagination.page = 1
  loadList()
}

const selectedFeatureId = ref<number | null>(null)
function rowProps(row: FeatureItem) {
  return {
    style: row.id === selectedFeatureId.value ? 'background:#e8f1ff' : '',
    onClick: () => focusFeature(row),
  }
}
function focusFeature(row: FeatureItem) {
  selectedFeatureId.value = row.id
  if (row.geometry) mapRef.value?.fitTo(row.geometry)
}
function locateFeature(row: FeatureItem) {
  selectedFeatureId.value = row.id
  if (row.center_lng != null && row.center_lat != null) {
    mapRef.value?.panTo(row.center_lng, row.center_lat, Math.max(mapZoom.value, 16))
  } else if (row.geometry) {
    mapRef.value?.fitTo(row.geometry)
  }
}

const listColumns = computed<DataTableColumns<FeatureItem>>(() => [
  {
    title: '要素',
    key: 'name',
    ellipsis: { tooltip: true },
    // 名称与编号合并显示，给右侧操作列留出足够宽度，避免按钮被裁切
    render: (r) =>
      h('div', { style: 'display:flex;flex-direction:column;gap:1px;min-width:0;line-height:1.35' }, [
        h(
          'span',
          { style: 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap' },
          r.name || r.code || `#${r.id}`,
        ),
        h(
          'span',
          { style: 'color:#98a1b0;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' },
          r.code || '—',
        ),
      ]),
  },
  {
    title: '状态',
    key: 'status',
    width: 58,
    render: (r) => (r.status === 'verified' ? '已核实' : r.status === 'draft' || !r.status ? '草稿' : r.status),
  },
  {
    title: '操作',
    key: 'actions',
    width: 148,
    // 标题与下方操作按钮统一右对齐
    align: 'right',
    titleAlign: 'right',
    render: (r) =>
      h('div', { style: 'display:flex;gap:2px;justify-content:flex-end' }, [
        can('feature:update')
          ? h(NButton, { size: 'tiny', quaternary: true, type: 'primary', title: '编辑属性', onClick: () => openEditForm(r) }, {
              icon: () => h(NIcon, null, { default: () => h(CreateOutline) }),
            })
          : null,
        can('feature:update')
          ? h(NButton, { size: 'tiny', quaternary: true, type: 'info', title: '编辑形状', onClick: () => beginShapeEdit(r) }, {
              icon: () => h(NIcon, null, { default: () => h(ShapesOutline) }),
            })
          : null,
        h(NButton, { size: 'tiny', quaternary: true, title: '定位', onClick: () => locateFeature(r) }, {
          icon: () => h(NIcon, null, { default: () => h(LocateOutline) }),
        }),
        can('feature:delete')
          ? h(NButton, { size: 'tiny', quaternary: true, type: 'error', title: '删除', onClick: () => removeFeature(r) }, {
              icon: () => h(NIcon, null, { default: () => h(TrashOutline) }),
            })
          : null,
      ]),
  },
])

function onMapFeatureClick(featureId: number, moduleId: number) {
  if (moduleId !== selectedModuleId.value) {
    selectedModuleId.value = moduleId
    reloadList()
  }
  const row = listRows.value.find((r) => r.id === featureId)
  if (row) focusFeature(row)
  else selectedFeatureId.value = featureId
}

// ---------------- 形状顶点编辑 ----------------
const editingShapeId = ref<number | null>(null)
const savingShape = ref(false)
const lastShapeGeojson = ref<Record<string, unknown> | null>(null)

/** 当前形状的面片数 / 洞数（用于界面提示） */
const shapeInfo = computed(() => {
  // 新建时看待保存图形，编辑时看编辑中的图形
  const source = editingShapeId.value ? lastShapeGeojson.value : pendingGeometry.value
  const geo = source as { type?: string; coordinates?: unknown } | null
  if (!geo?.coordinates) return { parts: 0, holes: 0 }
  const polygons = (
    geo.type === 'MultiPolygon' ? (geo.coordinates as unknown[][]) : [geo.coordinates as unknown[]]
  ) as unknown[][][]
  return {
    parts: polygons.length,
    holes: polygons.reduce((sum, polygon) => sum + Math.max(polygon.length - 1, 0), 0),
  }
})

function beginShapeEdit(row: FeatureItem) {
  const m = modules.value.find((x) => x.id === row.module_id)
  if (!m || !mapRef.value) return
  try {
    // 先记录当前形状，未拖动顶点直接保存时也能提交
    lastShapeGeojson.value = row.geometry ?? null
    mapRef.value.startVertexEditById(
      row.id,
      m.color,
      (gj) => {
        lastShapeGeojson.value = gj
      },
      row.geometry,
    )
    editingShapeId.value = row.id
    selectedFeatureId.value = row.id
    if (row.geometry) mapRef.value.fitTo(row.geometry)
  } catch (e) {
    toastError((e as Error).message || '打开形状编辑失败')
  }
}

/** 编辑已有要素：挖洞 */
async function editAddHole() {
  if (!mapRef.value) return
  shapingBusy.value = true
  try {
    await mapRef.value.addHoleToEditing(selectedModule.value?.color || '#2d6cdf')
  } catch (e) {
    toastError((e as Error).message || '挖洞失败')
  } finally {
    shapingBusy.value = false
  }
}

/** 编辑已有要素：添加飞地面片 */
async function editAddPart() {
  if (!mapRef.value) return
  shapingBusy.value = true
  try {
    await mapRef.value.addPartToEditing(selectedModule.value?.color || '#2d6cdf')
  } catch (e) {
    toastError((e as Error).message || '添加飞地失败')
  } finally {
    shapingBusy.value = false
  }
}

function editUndoRing() {
  mapRef.value?.undoEditingRing()
}

async function saveShape() {
  const id = editingShapeId.value
  const geometry = lastShapeGeojson.value
  if (!id || !geometry) return
  savingShape.value = true
  try {
    await featureApi.update(id, { geometry })
    toastSuccess('形状已保存')
    mapRef.value?.stopVertexEdit()
    editingShapeId.value = null
    lastShapeGeojson.value = null
    loadGroups()
  } catch (e) {
    toastError((e as Error).message || '保存形状失败')
  } finally {
    savingShape.value = false
  }
}
function cancelShape() {
  mapRef.value?.stopVertexEdit()
  editingShapeId.value = null
  lastShapeGeojson.value = null
  loadGroups()
}

// ---------------- 属性表单 ----------------
const showForm = ref(false)
const saving = ref(false)
const editingFeature = ref<FeatureItem | null>(null)
const pendingGeometry = ref<Record<string, unknown> | null>(null)
const formRef = ref<FormInst | null>(null)
const form = reactive({
  name: '',
  code: '',
  status: 'draft',
  declared_lng: null as number | null,
  declared_lat: null as number | null,
  remark: '',
  props: {} as Record<string, unknown>,
})

const formRules: FormRules = {
  name: { required: true, message: '请输入要素名称', trigger: ['blur', 'input'] },
}

function fieldRule(f: FieldDef) {
  return f.required ? { required: true, message: `${f.label}为必填项`, trigger: ['blur', 'change'] } : undefined
}

function centroidOf(gj: Record<string, unknown>): [number, number] | null {
  const type = gj?.type as string | undefined
  const coords = (gj as { coordinates?: unknown }).coordinates
  if (!type || !coords) return null
  if (type === 'Point') {
    const [lng, lat] = coords as [number, number]
    return [lng, lat]
  }
  const flat: number[][] = []
  const walk = (c: unknown) => {
    if (!Array.isArray(c)) return
    if (c.length === 2 && typeof c[0] === 'number' && typeof c[1] === 'number') flat.push(c as number[])
    else c.forEach(walk)
  }
  walk(coords)
  if (!flat.length) return null
  const lng = flat.reduce((s, p) => s + p[0], 0) / flat.length
  const lat = flat.reduce((s, p) => s + p[1], 0) / flat.length
  return [lng, lat]
}

async function openCreateForm(geometry: Record<string, unknown>) {
  const m = selectedModule.value
  if (!m) return
  if (selectedModuleFull.value?.id !== m.id) await loadFullModule()
  pendingGeometry.value = geometry
  editingFeature.value = null
  const center = centroidOf(geometry)
  form.name = ''
  form.code = ''
  form.status = 'draft'
  form.declared_lng = center ? Number(center[0].toFixed(8)) : null
  form.declared_lat = center ? Number(center[1].toFixed(8)) : null
  form.remark = ''
  form.props = {}
  try {
    const tpl = (await featureApi.blank(m.id)) as { properties?: Record<string, unknown> }
    form.props = { ...(tpl.properties ?? {}) }
  } catch {
    /* 模板拉取失败不影响填写 */
  }
  showForm.value = true
}

async function openEditForm(row: FeatureItem) {
  if (selectedModuleId.value !== row.module_id) {
    selectedModuleId.value = row.module_id
    await loadFullModule()
  } else if (!selectedModuleFull.value) {
    await loadFullModule()
  }
  editingFeature.value = row
  pendingGeometry.value = null
  shapingNew.value = false
  mapRef.value?.clearPreview()
  form.name = row.name ?? ''
  form.code = row.code ?? ''
  form.status = row.status ?? 'draft'
  form.declared_lng = row.declared_lng ?? null
  form.declared_lat = row.declared_lat ?? null
  form.remark = row.remark ?? ''
  form.props = { ...((row.properties as Record<string, unknown>) ?? {}) }
  showForm.value = true
}

async function saveFeature() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!selectedModule.value) return
  const payload: Record<string, unknown> = {
    name: form.name.trim(),
    status: form.status,
    declared_lng: form.declared_lng,
    declared_lat: form.declared_lat,
    remark: form.remark || null,
    properties: { ...form.props },
  }
  if (editingFeature.value) {
    payload.code = editingFeature.value.code ?? undefined
  } else {
    // 新建时允许自定义编号；留空则由后端自动生成
    payload.code = form.code.trim() || undefined
  }
  saving.value = true
  try {
    if (editingFeature.value) {
      await featureApi.update(editingFeature.value.id, payload)
      toastSuccess('采集数据已更新')
    } else {
      if (!pendingGeometry.value) {
        toastError('缺少空间图形')
        return
      }
      await featureApi.create({
        module_id: selectedModule.value.id,
        geometry: pendingGeometry.value,
        ...payload,
      })
      toastSuccess('采集数据已保存')
      // 已入库，移除绘制预览（正式图形由图层渲染）
      mapRef.value?.clearPreview()
      pendingGeometry.value = null
      shapingNew.value = false
    }
    showForm.value = false
    loadList()
    loadGroups()
  } catch (e) {
    toastError((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

/** 关闭属性表单：新建场景下放弃未保存的图形与预览 */
function closeForm() {
  showForm.value = false
  if (!editingFeature.value) {
    pendingGeometry.value = null
    shapingNew.value = false
    mapRef.value?.clearPreview()
  }
}

// 表单被 Esc / 遮罩关闭时同样清理未保存的图形预览
watch(showForm, (visible) => {
  if (!visible && !editingFeature.value) {
    pendingGeometry.value = null
    shapingNew.value = false
    mapRef.value?.clearPreview()
  }
})

function removeFeature(row: FeatureItem) {
  dialogConfirm(`确认删除要素「${row.name ?? row.code ?? row.id}」？`, async () => {
    try {
      await featureApi.remove(row.id)
      toastSuccess('已删除')
      reloadList()
      loadGroups()
    } catch (e) {
      toastError((e as Error).message || '删除失败')
    }
  })
}

// ---------------- 初始化 ----------------
onMounted(async () => {
  await loadModules()
  await Promise.all([loadGroups(), loadList(), loadFieldLabels()])
})
</script>

<style scoped>
/* 视野取数状态条：贴在地图左上角，说明当前视野内加载了多少、是否有图层被截断 */
.map-status {
  position: absolute;
  left: 14px;
  top: 14px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: min(460px, 72%);
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: var(--shadow-card);
  color: var(--ink-600);
  font-size: 12px;
  line-height: 1.6;
}
.map-status .status-dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #18a058;
}
.map-status.is-loading .status-dot {
  background: #f0a020;
}
.map-status .status-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 采集目标：标题 + 模块选择 + 几何类型合并为一行 */
.target-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.target-title {
  flex: none;
  white-space: nowrap;
}
.target-row :deep(.n-select) {
  flex: 1;
  min-width: 0;
}
.target-row .color-dot {
  width: 10px;
  height: 10px;
}
.color-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex: none;
}
.draw-btns {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.layer-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
}
.layer-toolbar :deep(.n-input) {
  flex: 1;
  min-width: 0;
}
.layer-toolbar :deep(.n-checkbox__label) {
  font-size: 12px;
  padding-left: 6px;
}
.layer-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}
.layer-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 2px;
  cursor: pointer;
  border-radius: 4px;
}
.layer-row:hover {
  background: #f2f5fa;
}
.layer-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty-hint {
  color: #999;
  font-size: 12px;
}
.list-section {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
/* 侧栏自身不整体滚动：图层区与要素列表各自内部滚动，
   避免模块变多时图层撑满整页、把要素列表挤成 0 高度 */
.side-panel {
  overflow: hidden;
}
.target-section {
  flex: none;
}
.layer-section {
  flex: none;
  max-height: min(320px, 38vh);
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: hidden;
}
.list-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}
.list-count {
  color: #999;
  font-weight: normal;
  font-size: 12px;
}
.list-toolbar {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
/* 绘制/编辑浮动工具条：左侧状态信息可压缩，右侧按钮始终单行不换行 */
.shape-bar {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  width: max-content;
  max-width: calc(100% - 24px);
  padding: 8px 12px;
  border: 1px solid #e3e8ef;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.12);
}
.shape-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 12px;
  color: #5b6577;
}
.shape-badge {
  flex: none;
  padding: 1px 8px;
  border-radius: 999px;
  background: #e8f0ff;
  color: #2d6cdf;
  font-size: 12px;
  line-height: 18px;
}
.shape-badge.is-warning {
  background: #fff4e0;
  color: #c47a00;
}
.shape-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.shape-count {
  flex: none;
  color: #98a1b0;
  font-variant-numeric: tabular-nums;
}
.shape-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
}
@media (max-width: 1080px) {
  .shape-text {
    display: none;
  }
}
.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
