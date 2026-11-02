<template>
  <div class="page">
    <div class="map-page">
      <div class="side-panel">
        <div class="panel-section">
          <div class="section-title">建筑物检索</div>
          <n-input
            v-model:value="keyword"
            size="small"
            placeholder="名称 / 编码 / 地址"
            clearable
            @keyup.enter="reload"
          />
          <div class="filter-row">
            <n-select
              v-model:value="filterStatus"
              :options="STATUS_OPTIONS"
              size="small"
              clearable
              placeholder="使用状态"
              @update:value="reload"
            />
            <n-button size="small" @click="reload">查询</n-button>
          </div>
          <n-button
            v-if="can('building:create')"
            type="primary"
            block
            :loading="drawing"
            :disabled="drawing"
            @click="beginCreate"
          >
            <template #icon><n-icon><AddOutline /></n-icon></template>
            在地图上绘制建筑物
          </n-button>
          <n-alert v-if="drawing" type="info" :show-icon="false" size="small">
            在地图上依次单击绘制轮廓，双击结束（Esc 取消）
          </n-alert>
        </div>

        <div class="panel-section list-section">
          <div class="section-title">
            建筑物列表
            <span class="list-count">共 {{ pagination.itemCount }} 条</span>
          </div>
          <div class="table-wrap">
            <n-data-table
              :columns="columns"
              :data="rows"
              :loading="loading"
              :pagination="pagination"
              :row-key="(r: BuildingItem) => r.id"
              :row-props="rowProps"
              size="small"
              remote
            />
          </div>
        </div>
      </div>

      <div class="map-panel">
        <MapView
          ref="mapRef"
          :center="mapCenter"
          :zoom="mapZoom"
          :max-zoom="mapMaxZoom"
        />
        <div class="map-legend">
          <span v-for="s in STATUS_OPTIONS" :key="s.value" class="legend-item">
            <span class="color-dot" :style="{ background: statusColor(s.value) }" />{{ s.label }}
          </span>
        </div>
      </div>
    </div>

    <!-- 建筑物表单 -->
    <n-modal
      v-model:show="showForm"
      preset="card"
      :title="formId ? '编辑建筑物' : '新增建筑物'"
      style="width: 720px; max-width: 94vw"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="formRules" label-placement="left" label-width="106">
        <n-grid :cols="2" :x-gap="16">
          <n-form-item-gi label="建筑物编码" path="code">
            <n-input v-model:value="form.code" placeholder="如 JZW-001">
              <template #suffix>
                <n-button text type="primary" size="tiny" @click="form.code = genCode()">生成</n-button>
              </template>
            </n-input>
          </n-form-item-gi>
          <n-form-item-gi label="建筑物名称" path="name">
            <n-input v-model:value="form.name" placeholder="如 1 号办公楼" />
          </n-form-item-gi>
          <n-form-item-gi label="使用状态">
            <n-select v-model:value="form.status" :options="STATUS_OPTIONS" />
          </n-form-item-gi>
          <n-form-item-gi label="建筑用途">
            <n-select v-model:value="form.usage" :options="USAGE_OPTIONS" clearable placeholder="选择用途" />
          </n-form-item-gi>
          <n-form-item-gi label="结构类型">
            <n-select
              v-model:value="form.structure_type"
              :options="STRUCTURE_OPTIONS"
              clearable
              placeholder="选择结构"
            />
          </n-form-item-gi>
          <n-form-item-gi label="权属性质">
            <n-select
              v-model:value="form.ownership"
              :options="OWNERSHIP_OPTIONS"
              clearable
              placeholder="选择权属"
            />
          </n-form-item-gi>
          <n-form-item-gi label="楼层数">
            <n-input-number v-model:value="form.floor_count" :min="0" :precision="0" style="width: 100%" />
          </n-form-item-gi>
          <n-form-item-gi label="建筑高度(米)">
            <n-input-number v-model:value="form.building_height" :min="0" :precision="2" style="width: 100%" />
          </n-form-item-gi>
          <n-form-item-gi label="建成年份">
            <n-input-number
              v-model:value="form.build_year"
              :min="1900"
              :max="2100"
              :precision="0"
              style="width: 100%"
            />
          </n-form-item-gi>
          <n-form-item-gi label="宗地代码">
            <n-input v-model:value="form.parcel_code" placeholder="可选" />
          </n-form-item-gi>
          <n-form-item-gi label="行政区代码">
            <n-input v-model:value="form.region_code" placeholder="可选" />
          </n-form-item-gi>
          <n-form-item-gi label="申报经度">
            <n-input-number v-model:value="form.declared_lng" :precision="8" placeholder="默认取轮廓形心" style="width: 100%" />
          </n-form-item-gi>
          <n-form-item-gi label="申报纬度">
            <n-input-number v-model:value="form.declared_lat" :precision="8" placeholder="默认取轮廓形心" style="width: 100%" />
          </n-form-item-gi>
        </n-grid>
        <n-form-item label="详细地址">
          <n-input v-model:value="form.address" placeholder="如 XX 路 XX 号" />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="form.remark" type="textarea" :rows="2" placeholder="备注信息（可选）" />
        </n-form-item>
        <n-form-item label="空间轮廓">
          <div class="geom-box">
            <n-tag :type="formGeometry ? 'success' : 'warning'" size="small">
              {{ formGeometry ? '已绘制轮廓' : '尚未绘制' }}
            </n-tag>
            <n-button size="small" @click="redrawGeometry">在地图上重绘</n-button>
            <span class="geom-hint">建筑物必须为面状空间信息</span>
          </div>
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="form-footer">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 建筑-单位关联 -->
    <n-modal
      v-model:show="showLink"
      preset="card"
      :title="linkBuilding ? `关联单位 - ${linkBuilding.name}` : '关联单位'"
      style="width: 860px; max-width: 94vw"
      :mask-closable="false"
    >
      <div class="link-summary" v-if="linkBuilding">
        <n-tag size="small" type="info">{{ linkBuilding.code }}</n-tag>
        <span>面积：{{ linkBuilding.area_m2 != null ? `${linkBuilding.area_m2} ㎡` : '-' }}</span>
        <span>
          中心坐标：
          {{ linkBuilding.center_lng != null && linkBuilding.center_lat != null
            ? `${linkBuilding.center_lng.toFixed(6)}, ${linkBuilding.center_lat.toFixed(6)}`
            : '-' }}
        </span>
      </div>

      <n-data-table
        :columns="unitColumns"
        :data="linkedUnits"
        :loading="linkLoading"
        size="small"
        :row-key="(r: UnitBrief) => r.relation_id"
      />

      <n-divider title-placement="left">新增关联</n-divider>
      <n-grid :cols="4" :x-gap="12" :y-gap="8">
        <n-form-item-gi label="单位" :show-label="true" label-placement="top" :span="2">
          <n-select
            v-model:value="linkForm.unit_id"
            :options="unitOptions"
            filterable
            remote
            clearable
            :loading="unitSearching"
            placeholder="输入单位名称搜索"
            @search="searchUnits"
          />
        </n-form-item-gi>
        <n-form-item-gi label="关系类型" label-placement="top">
          <n-select v-model:value="linkForm.relation_type" :options="RELATION_OPTIONS" />
        </n-form-item-gi>
        <n-form-item-gi label="占比(%)" label-placement="top">
          <n-input-number v-model:value="linkForm.share_ratio" :min="0" :max="100" :precision="2" style="width: 100%" />
        </n-form-item-gi>
      </n-grid>
      <div class="link-actions">
        <n-checkbox v-model:checked="linkForm.is_primary">设为主要使用单位</n-checkbox>
        <div class="spacer" />
        <n-button
          v-if="can('unit:link') || can('building:update')"
          type="primary"
          :loading="linking"
          :disabled="!linkForm.unit_id"
          @click="attachUnit"
        >
          关联
        </n-button>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NIcon, NTag, type DataTableColumns, type FormInst, type FormRules } from 'naive-ui'
import { AddOutline, CreateOutline, LinkOutline, LocateOutline, TrashOutline } from '@vicons/ionicons5'
import {
  buildingApi,
  unitApi,
  type BuildingItem,
  type BuildingMapItem,
  type UnitBrief,
} from '@/api'
import MapView from '@/components/map/MapView.vue'
import { useUserStore } from '@/store/user'
import { dialogConfirm, toastError, toastSuccess } from '@/utils/naive'

const store = useUserStore()
const can = (code: string) => store.hasPerm(code)

const STATUS_OPTIONS = [
  { label: '在用', value: '在用' },
  { label: '闲置', value: '闲置' },
  { label: '在建', value: '在建' },
  { label: '待拆', value: '待拆' },
]
const USAGE_OPTIONS = [
  { label: '住宅', value: '住宅' },
  { label: '办公', value: '办公' },
  { label: '商业', value: '商业' },
  { label: '工业', value: '工业' },
  { label: '公共管理', value: '公共管理' },
  { label: '教育科研', value: '教育科研' },
  { label: '其他', value: '其他' },
]
const STRUCTURE_OPTIONS = [
  { label: '钢混', value: '钢混' },
  { label: '框架', value: '框架' },
  { label: '砖混', value: '砖混' },
  { label: '钢结构', value: '钢结构' },
  { label: '剪力墙', value: '剪力墙' },
  { label: '砖木', value: '砖木' },
  { label: '其他', value: '其他' },
]
const OWNERSHIP_OPTIONS = [
  { label: '国有', value: '国有' },
  { label: '集体', value: '集体' },
  { label: '私有', value: '私有' },
  { label: '混合', value: '混合' },
]
const RELATION_OPTIONS = [
  { label: '使用', value: '使用' },
  { label: '产权', value: '产权' },
  { label: '租赁', value: '租赁' },
  { label: '管理', value: '管理' },
]

function statusColor(status: string) {
  if (status === '在用') return '#18a058'
  if (status === '闲置') return '#f0a020'
  if (status === '在建') return '#2d6cdf'
  if (status === '待拆') return '#d03050'
  return '#8c8c8c'
}

// ---------------- 底图配置（瓦片地址见 public/js/config.js） ----------------
const mapCenter = computed<[number, number]>(() => store.bootstrap?.center ?? [116.397428, 39.90923])
const mapZoom = computed(() => store.bootstrap?.zoom ?? 15)
const mapMaxZoom = computed(() => store.bootstrap?.max_zoom ?? 18)

// ---------------- 列表 ----------------
const mapRef = ref<InstanceType<typeof MapView> | null>(null)
const keyword = ref('')
const filterStatus = ref<string | null>(null)
const rows = ref<BuildingItem[]>([])
const loading = ref(false)
const selectedId = ref<number | null>(null)
const pagination = reactive({
  page: 1,
  pageSize: 10,
  itemCount: 0,
  showSizePicker: false,
  pageSlot: 5,
  onChange: (p: number) => {
    pagination.page = p
    loadList()
  },
})

async function loadList() {
  loading.value = true
  try {
    const res = await buildingApi.list({
      keyword: keyword.value || undefined,
      status: filterStatus.value || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    rows.value = res.items
    pagination.itemCount = res.total
  } catch (e) {
    toastError((e as Error).message || '加载建筑物列表失败')
  } finally {
    loading.value = false
  }
}
function reload() {
  pagination.page = 1
  loadList()
}

const columns = computed<DataTableColumns<BuildingItem>>(() => [
  {
    title: '名称',
    key: 'name',
    minWidth: 110,
    ellipsis: { tooltip: true },
    render: (r) =>
      h('div', { style: 'display:flex;align-items:center;gap:6px' }, [
        h('span', {
          style: `width:8px;height:8px;border-radius:50%;flex:none;background:${statusColor(r.status)}`,
        }),
        h('span', { style: 'overflow:hidden;text-overflow:ellipsis' }, r.name),
      ]),
  },
  { title: '编码', key: 'code', width: 96, ellipsis: { tooltip: true } },
  {
    title: '操作',
    key: 'actions',
    width: 118,
    render: (r) =>
      h('div', { style: 'display:flex;gap:2px' }, [
        h(
          NButton,
          { size: 'tiny', quaternary: true, title: '定位', onClick: (e: Event) => { e.stopPropagation(); locate(r) } },
          { icon: () => h(NIcon, null, { default: () => h(LocateOutline) }) },
        ),
        can('building:update')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'primary', title: '编辑', onClick: (e: Event) => { e.stopPropagation(); openEdit(r) } },
              { icon: () => h(NIcon, null, { default: () => h(CreateOutline) }) },
            )
          : null,
        can('unit:link') || can('building:update')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'info', title: '关联单位', onClick: (e: Event) => { e.stopPropagation(); openLink(r) } },
              { icon: () => h(NIcon, null, { default: () => h(LinkOutline) }) },
            )
          : null,
        can('building:delete')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'error', title: '删除', onClick: (e: Event) => { e.stopPropagation(); remove(r) } },
              { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }) },
            )
          : null,
      ]),
  },
])

function rowProps(row: BuildingItem) {
  return {
    style: row.id === selectedId.value ? 'background:#e8f1ff' : '',
    onClick: () => locate(row),
  }
}

function locate(row: BuildingItem) {
  selectedId.value = row.id
  if (row.geometry) mapRef.value?.fitTo(row.geometry)
  else if (row.center_lng != null && row.center_lat != null) {
    mapRef.value?.panTo(row.center_lng, row.center_lat, Math.max(mapZoom.value, 17))
  }
}

// ---------------- 地图 ----------------
async function loadMap() {
  try {
    const data = (await buildingApi.map(5000)) as BuildingMapItem[]
    const items = data
      .filter((b) => b.geometry)
      .map((b) => ({
        id: String(b.id),
        geometry: b.geometry as Record<string, unknown>,
        color: statusColor(b.status),
        label: `${b.name}（${b.code}）`,
        onClick: () => selectFromMap(b.id),
      }))
    mapRef.value?.renderPlain(items, 'buildings')
  } catch (e) {
    toastError((e as Error).message || '加载地图数据失败')
  }
}

function selectFromMap(id: number) {
  selectedId.value = id
  const row = rows.value.find((r) => r.id === id)
  if (row?.geometry) {
    mapRef.value?.fitTo(row.geometry)
    return
  }
  buildingApi
    .detail(id)
    .then((d) => {
      if (d.geometry) mapRef.value?.fitTo(d.geometry)
    })
    .catch(() => {
      /* 忽略定位异常 */
    })
}

// ---------------- 绘制与表单 ----------------
const drawing = ref(false)
const showForm = ref(false)
const saving = ref(false)
const formId = ref<number | null>(null)
const formRef = ref<FormInst | null>(null)
const formGeometry = ref<Record<string, unknown> | null>(null)

const form = reactive({
  code: '',
  name: '',
  address: '',
  parcel_code: '',
  region_code: '',
  floor_count: null as number | null,
  building_height: null as number | null,
  usage: null as string | null,
  structure_type: null as string | null,
  build_year: null as number | null,
  ownership: null as string | null,
  status: '在用',
  declared_lng: null as number | null,
  declared_lat: null as number | null,
  remark: '',
})

const formRules: FormRules = {
  code: [
    { required: true, message: '请输入建筑物编码', trigger: ['blur', 'input'] },
    { pattern: /^[A-Za-z0-9_-]+$/, message: '仅支持字母、数字、下划线、中划线', trigger: ['blur', 'input'] },
  ],
  name: { required: true, message: '请输入建筑物名称', trigger: ['blur', 'input'] },
}

function genCode(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `JZW${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

function centroidOf(gj: Record<string, unknown>): [number, number] | null {
  const coords = (gj as { coordinates?: unknown }).coordinates
  if (!coords) return null
  const flat: number[][] = []
  const walk = (c: unknown) => {
    if (!Array.isArray(c)) return
    if (c.length >= 2 && typeof c[0] === 'number' && typeof c[1] === 'number') flat.push(c as number[])
    else c.forEach(walk)
  }
  walk(coords)
  if (!flat.length) return null
  return [
    flat.reduce((s, p) => s + p[0], 0) / flat.length,
    flat.reduce((s, p) => s + p[1], 0) / flat.length,
  ]
}

function resetForm() {
  Object.assign(form, {
    code: genCode(),
    name: '',
    address: '',
    parcel_code: '',
    region_code: '',
    floor_count: null,
    building_height: null,
    usage: null,
    structure_type: null,
    build_year: null,
    ownership: null,
    status: '在用',
    declared_lng: null,
    declared_lat: null,
    remark: '',
  })
}

async function beginCreate() {
  if (drawing.value) return
  drawing.value = true
  try {
    const gj = await mapRef.value?.startDraw('polygon', '#2d6cdf')
    if (!gj) return
    formId.value = null
    formGeometry.value = gj
    resetForm()
    const center = centroidOf(gj)
    if (center) {
      form.declared_lng = Number(center[0].toFixed(8))
      form.declared_lat = Number(center[1].toFixed(8))
    }
    showForm.value = true
  } catch (e) {
    toastError((e as Error).message || '绘制失败')
  } finally {
    drawing.value = false
  }
}

function openEdit(row: BuildingItem) {
  formId.value = row.id
  formGeometry.value = row.geometry
  Object.assign(form, {
    code: row.code,
    name: row.name,
    address: row.address ?? '',
    parcel_code: row.parcel_code ?? '',
    region_code: row.region_code ?? '',
    floor_count: row.floor_count ?? null,
    building_height: row.building_height ?? null,
    usage: row.usage ?? null,
    structure_type: row.structure_type ?? null,
    build_year: row.build_year ?? null,
    ownership: row.ownership ?? null,
    status: row.status || '在用',
    declared_lng: row.declared_lng ?? null,
    declared_lat: row.declared_lat ?? null,
    remark: row.remark ?? '',
  })
  showForm.value = true
  if (row.geometry) mapRef.value?.fitTo(row.geometry)
}

async function redrawGeometry() {
  try {
    const gj = await mapRef.value?.startDraw('polygon', '#f0a020')
    if (!gj) return
    formGeometry.value = gj
    const center = centroidOf(gj)
    if (center) {
      form.declared_lng = Number(center[0].toFixed(8))
      form.declared_lat = Number(center[1].toFixed(8))
    }
    toastSuccess('已更新轮廓，保存后生效')
  } catch (e) {
    toastError((e as Error).message || '绘制失败')
  }
}

async function save() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!formGeometry.value) {
    toastError('请先在地图上绘制建筑物轮廓')
    return
  }
  const payload: Record<string, unknown> = {
    code: form.code.trim(),
    name: form.name.trim(),
    address: form.address || null,
    parcel_code: form.parcel_code || null,
    region_code: form.region_code || null,
    geometry: formGeometry.value,
    declared_lng: form.declared_lng,
    declared_lat: form.declared_lat,
    floor_count: form.floor_count,
    building_height: form.building_height,
    usage: form.usage,
    structure_type: form.structure_type,
    build_year: form.build_year,
    ownership: form.ownership,
    status: form.status,
    remark: form.remark || null,
  }
  saving.value = true
  try {
    if (formId.value) {
      await buildingApi.update(formId.value, payload)
      toastSuccess('建筑物已更新')
    } else {
      await buildingApi.create(payload)
      toastSuccess('建筑物已保存')
    }
    showForm.value = false
    reload()
    loadMap()
  } catch (e) {
    toastError((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

function remove(row: BuildingItem) {
  dialogConfirm(`删除建筑物「${row.name}」将同时解除其单位关联，确认继续？`, async () => {
    try {
      await buildingApi.remove(row.id)
      toastSuccess('已删除')
      reload()
      loadMap()
    } catch (e) {
      toastError((e as Error).message || '删除失败')
    }
  })
}

// ---------------- 单位关联 ----------------
const showLink = ref(false)
const linkLoading = ref(false)
const linking = ref(false)
const linkBuilding = ref<BuildingItem | null>(null)
const linkedUnits = ref<UnitBrief[]>([])
const unitOptions = ref<{ label: string; value: number }[]>([])
const unitSearching = ref(false)
const linkForm = reactive({
  unit_id: null as number | null,
  relation_type: '使用',
  share_ratio: null as number | null,
  is_primary: false,
})

const unitColumns: DataTableColumns<UnitBrief> = [
  { title: '单位名称', key: 'name', minWidth: 140, ellipsis: { tooltip: true } },
  { title: '信用代码', key: 'credit_code', width: 160, render: (r) => r.credit_code || '-' },
  { title: '关系', key: 'relation_type', width: 70 },
  {
    title: '占比',
    key: 'share_ratio',
    width: 70,
    render: (r) => (r.share_ratio != null ? `${r.share_ratio}%` : '-'),
  },
  {
    title: '主要',
    key: 'is_primary',
    width: 60,
    render: (r) => (r.is_primary ? h(NTag, { size: 'tiny', type: 'success' }, { default: () => '是' }) : '-'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    render: (r) =>
      h(
        NButton,
        { size: 'tiny', quaternary: true, type: 'error', onClick: () => detachUnit(r) },
        { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }) },
      ),
  },
]

async function openLink(row: BuildingItem) {
  linkBuilding.value = row
  linkedUnits.value = []
  linkForm.unit_id = null
  linkForm.relation_type = '使用'
  linkForm.share_ratio = null
  linkForm.is_primary = false
  showLink.value = true
  await Promise.all([loadLinkedUnits(row.id), searchUnits('')])
  if (row.geometry) mapRef.value?.fitTo(row.geometry)
}

async function loadLinkedUnits(buildingId: number) {
  linkLoading.value = true
  try {
    const detail = await buildingApi.detail(buildingId)
    linkedUnits.value = detail.units ?? []
    linkBuilding.value = detail
  } catch (e) {
    toastError((e as Error).message || '加载关联单位失败')
  } finally {
    linkLoading.value = false
  }
}

async function searchUnits(query: string) {
  unitSearching.value = true
  try {
    const res = await unitApi.list({ keyword: query || undefined, page: 1, page_size: 20 })
    unitOptions.value = res.items.map((u) => ({
      label: u.credit_code ? `${u.name}（${u.credit_code}）` : u.name,
      value: u.id,
    }))
  } catch {
    unitOptions.value = []
  } finally {
    unitSearching.value = false
  }
}

async function attachUnit() {
  const building = linkBuilding.value
  if (!building || !linkForm.unit_id) return
  linking.value = true
  try {
    await buildingApi.attachUnit(building.id, {
      building_id: building.id,
      unit_id: linkForm.unit_id,
      relation_type: linkForm.relation_type,
      share_ratio: linkForm.share_ratio,
      is_primary: linkForm.is_primary,
    })
    toastSuccess('已关联单位')
    linkForm.unit_id = null
    linkForm.share_ratio = null
    linkForm.is_primary = false
    await loadLinkedUnits(building.id)
  } catch (e) {
    toastError((e as Error).message || '关联失败')
  } finally {
    linking.value = false
  }
}

function detachUnit(unit: UnitBrief) {
  const building = linkBuilding.value
  if (!building) return
  dialogConfirm(`确认解除与「${unit.name}」的关联？`, async () => {
    try {
      await buildingApi.detachUnit(building.id, unit.relation_id)
      toastSuccess('已解除关联')
      await loadLinkedUnits(building.id)
    } catch (e) {
      toastError((e as Error).message || '解除关联失败')
    }
  })
}

// ---------------- 初始化 ----------------
onMounted(async () => {
  await Promise.all([loadList(), loadMap()])
})
</script>

<style scoped>
.side-panel {
  width: 380px;
}
.panel-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.list-count {
  color: #999;
  font-weight: normal;
  font-size: 12px;
}
.filter-row {
  display: flex;
  gap: 6px;
}
.filter-row :deep(.n-select) {
  flex: 1;
}
.list-section {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.table-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.map-legend {
  position: absolute;
  left: 14px;
  top: 14px;
  z-index: 10;
  display: flex;
  gap: 12px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 7px 12px;
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
.color-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.geom-box {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.geom-hint {
  color: #999;
  font-size: 12px;
}
.link-summary {
  display: flex;
  align-items: center;
  gap: 16px;
  color: #666;
  font-size: 13px;
  margin-bottom: 10px;
}
.link-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}
.link-actions .spacer {
  flex: 1;
}
</style>
