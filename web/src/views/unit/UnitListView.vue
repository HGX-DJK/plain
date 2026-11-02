<template>
  <div class="page">
    <div class="page-card">
      <div class="toolbar">
        <n-input
          v-model:value="keyword"
          placeholder="搜索单位名称 / 信用代码"
          clearable
          style="width: 260px"
          @keyup.enter="reload"
        />
        <n-select
          v-model:value="filterType"
          :options="typeOptions"
          clearable
          placeholder="单位类型"
          style="width: 150px"
          @update:value="reload"
        />
        <n-select
          v-model:value="filterLinked"
          :options="LINKED_OPTIONS"
          clearable
          placeholder="关联情况"
          style="width: 130px"
          @update:value="reload"
        />
        <n-button @click="reload">查询</n-button>
        <div class="spacer" />
        <n-button v-if="can('unit:create')" type="primary" @click="openCreate">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          新增单位
        </n-button>
      </div>

      <n-data-table
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="pagination"
        remote
        :row-key="(r: UnitItem) => r.id"
      />
    </div>

    <!-- 单位表单 -->
    <n-modal
      v-model:show="showForm"
      preset="card"
      :title="formId ? '编辑单位信息' : '新增单位信息'"
      style="width: 720px; max-width: 94vw"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="formRules" label-placement="left" label-width="122">
        <n-grid :cols="2" :x-gap="16">
          <n-form-item-gi label="单位名称" path="name" :span="2">
            <n-input v-model:value="form.name" placeholder="如 XX 物业管理有限公司" />
          </n-form-item-gi>
          <n-form-item-gi label="统一社会信用代码">
            <n-input v-model:value="form.credit_code" placeholder="18 位信用代码（可选）" />
          </n-form-item-gi>
          <n-form-item-gi label="单位类型">
            <n-select
              v-model:value="form.unit_type"
              :options="typeOptions"
              tag
              filterable
              clearable
              placeholder="选择或输入类型"
            />
          </n-form-item-gi>
          <n-form-item-gi label="法定代表人">
            <n-input v-model:value="form.legal_person" placeholder="法人姓名" />
          </n-form-item-gi>
          <n-form-item-gi label="联系人">
            <n-input v-model:value="form.contact_name" placeholder="联系人姓名" />
          </n-form-item-gi>
          <n-form-item-gi label="联系电话">
            <n-input v-model:value="form.phone" placeholder="手机或座机" />
          </n-form-item-gi>
          <n-form-item-gi label="电子邮箱">
            <n-input v-model:value="form.email" placeholder="选填" />
          </n-form-item-gi>
        </n-grid>
        <n-form-item label="单位地址">
          <n-input v-model:value="form.address" placeholder="详细地址" />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="form.remark" type="textarea" :rows="2" placeholder="备注信息（可选）" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="form-footer">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 关联建筑物 -->
    <n-modal
      v-model:show="showDetail"
      preset="card"
      :title="detailUnit ? `关联建筑物 - ${detailUnit.name}` : '关联建筑物'"
      style="width: 860px; max-width: 94vw"
    >
      <div v-if="detailUnit" class="detail-summary">
        <span>信用代码：{{ detailUnit.credit_code || '-' }}</span>
        <span>类型：{{ detailUnit.unit_type || '-' }}</span>
        <span>法定代表人：{{ detailUnit.legal_person || '-' }}</span>
        <span>联系电话：{{ detailUnit.phone || '-' }}</span>
      </div>
      <n-data-table
        :columns="buildingColumns"
        :data="detailBuildings"
        :loading="detailLoading"
        size="small"
        :row-key="(r: UnitBuilding) => r.relation_id"
      />
      <n-alert type="info" :show-icon="false" size="small" style="margin-top: 12px">
        建筑-单位关联关系在「建筑物采集」页面维护（选择建筑物后点击关联单位）。
      </n-alert>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NIcon, NTag, type DataTableColumns, type FormInst, type FormRules } from 'naive-ui'
import { AddOutline, CreateOutline, LinkOutline, TrashOutline } from '@vicons/ionicons5'
import { unitApi, type UnitBuilding, type UnitItem } from '@/api'
import { useUserStore } from '@/store/user'
import { dialogConfirm, toastError, toastSuccess } from '@/utils/naive'

const store = useUserStore()
const can = (code: string) => store.hasPerm(code)

const DEFAULT_TYPES = ['机关单位', '事业单位', '企业', '个体工商户', '社会团体', '其他']
const LINKED_OPTIONS = [
  { label: '已关联建筑', value: 'yes' },
  { label: '未关联建筑', value: 'no' },
]

const keyword = ref('')
const filterType = ref<string | null>(null)
const filterLinked = ref<string | null>(null)
const rows = ref<UnitItem[]>([])
const loading = ref(false)
const typeOptions = ref<{ label: string; value: string }[]>(DEFAULT_TYPES.map((t) => ({ label: t, value: t })))
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

async function loadTypes() {
  try {
    const used = await unitApi.types()
    const merged = new Map(DEFAULT_TYPES.map((t) => [t, { label: t, value: t }]))
    used.forEach((u) => {
      if (u.value) merged.set(u.value, { label: `${u.value}（${u.count}）`, value: u.value })
    })
    typeOptions.value = Array.from(merged.values())
  } catch {
    /* 类型接口失败时使用默认值 */
  }
}

async function load() {
  loading.value = true
  try {
    const res = await unitApi.list({
      keyword: keyword.value || undefined,
      unit_type: filterType.value || undefined,
      has_building:
        filterLinked.value === 'yes' ? true : filterLinked.value === 'no' ? false : undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    rows.value = res.items
    pagination.itemCount = res.total
  } catch (e) {
    toastError((e as Error).message || '加载单位列表失败')
  } finally {
    loading.value = false
  }
}
function reload() {
  pagination.page = 1
  load()
}

const columns = computed<DataTableColumns<UnitItem>>(() => [
  { title: '单位名称', key: 'name', minWidth: 180, ellipsis: { tooltip: true } },
  {
    title: '统一社会信用代码',
    key: 'credit_code',
    width: 180,
    render: (r) => r.credit_code || '-',
  },
  {
    title: '单位类型',
    key: 'unit_type',
    width: 110,
    render: (r) =>
      r.unit_type
        ? h(NTag, { size: 'small', type: 'info' }, { default: () => r.unit_type })
        : '-',
  },
  { title: '法定代表人', key: 'legal_person', width: 100, render: (r) => r.legal_person || '-' },
  {
    title: '联系方式',
    key: 'contact',
    width: 150,
    render: (r) => {
      const text = [r.contact_name, r.phone].filter(Boolean).join(' / ')
      return text || '-'
    },
  },
  { title: '地址', key: 'address', minWidth: 160, ellipsis: { tooltip: true }, render: (r) => r.address || '-' },
  {
    title: '关联建筑',
    key: 'building_count',
    width: 90,
    render: (r) =>
      h(
        NTag,
        { size: 'small', type: r.building_count ? 'success' : 'default' },
        { default: () => `${r.building_count ?? 0} 栋` },
      ),
  },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    render: (r) =>
      h('div', { style: 'display:flex;gap:4px;align-items:center' }, [
        h(
          NButton,
          { size: 'tiny', quaternary: true, type: 'info', onClick: () => openDetail(r) },
          { icon: () => h(NIcon, null, { default: () => h(LinkOutline) }), default: () => '关联建筑' },
        ),
        can('unit:update')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'primary', title: '编辑', onClick: () => openEdit(r) },
              { icon: () => h(NIcon, null, { default: () => h(CreateOutline) }) },
            )
          : null,
        can('unit:delete')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'error', title: '删除', onClick: () => remove(r) },
              { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }) },
            )
          : null,
      ]),
  },
])

// ---------------- 表单 ----------------
const showForm = ref(false)
const saving = ref(false)
const formId = ref<number | null>(null)
const formRef = ref<FormInst | null>(null)
const form = reactive({
  name: '',
  credit_code: '',
  unit_type: null as string | null,
  legal_person: '',
  contact_name: '',
  phone: '',
  email: '',
  address: '',
  remark: '',
})

const formRules: FormRules = {
  name: { required: true, message: '请输入单位名称', trigger: ['blur', 'input'] },
  email: { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'input'] },
}

function openCreate() {
  formId.value = null
  Object.assign(form, {
    name: '',
    credit_code: '',
    unit_type: null,
    legal_person: '',
    contact_name: '',
    phone: '',
    email: '',
    address: '',
    remark: '',
  })
  showForm.value = true
}

function openEdit(row: UnitItem) {
  formId.value = row.id
  Object.assign(form, {
    name: row.name,
    credit_code: row.credit_code ?? '',
    unit_type: row.unit_type ?? null,
    legal_person: row.legal_person ?? '',
    contact_name: row.contact_name ?? '',
    phone: row.phone ?? '',
    email: row.email ?? '',
    address: row.address ?? '',
    remark: row.remark ?? '',
  })
  showForm.value = true
}

async function save() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  const payload = {
    name: form.name.trim(),
    credit_code: form.credit_code.trim() || null,
    unit_type: form.unit_type || null,
    legal_person: form.legal_person || null,
    contact_name: form.contact_name || null,
    phone: form.phone || null,
    email: form.email || null,
    address: form.address || null,
    remark: form.remark || null,
  }
  saving.value = true
  try {
    if (formId.value) {
      await unitApi.update(formId.value, payload)
      toastSuccess('单位信息已更新')
    } else {
      await unitApi.create(payload)
      toastSuccess('单位已创建')
    }
    showForm.value = false
    load()
    loadTypes()
  } catch (e) {
    toastError((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

function remove(row: UnitItem) {
  const tip = row.building_count
    ? `该单位已关联 ${row.building_count} 栋建筑物，删除后关联将一并解除，确认继续？`
    : `确认删除单位「${row.name}」？`
  dialogConfirm(tip, async () => {
    try {
      await unitApi.remove(row.id)
      toastSuccess('已删除')
      reload()
      loadTypes()
    } catch (e) {
      toastError((e as Error).message || '删除失败')
    }
  })
}

// ---------------- 关联建筑物 ----------------
const showDetail = ref(false)
const detailLoading = ref(false)
const detailUnit = ref<UnitItem | null>(null)
const detailBuildings = ref<UnitBuilding[]>([])

const buildingColumns: DataTableColumns<UnitBuilding> = [
  { title: '建筑编码', key: 'building_code', width: 130 },
  { title: '建筑物名称', key: 'building_name', minWidth: 150, ellipsis: { tooltip: true } },
  { title: '地址', key: 'address', minWidth: 160, ellipsis: { tooltip: true }, render: (r) => String(r.address ?? '-') },
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
]

async function openDetail(row: UnitItem) {
  showDetail.value = true
  detailUnit.value = row
  detailBuildings.value = []
  detailLoading.value = true
  try {
    const detail = await unitApi.detail(row.id)
    detailUnit.value = detail
    detailBuildings.value = detail.buildings ?? []
  } catch (e) {
    toastError((e as Error).message || '加载关联建筑失败')
  } finally {
    detailLoading.value = false
  }
}

onMounted(async () => {
  await loadTypes()
  await load()
})
</script>

<style scoped>
.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.detail-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: #666;
  font-size: 13px;
  margin-bottom: 10px;
}
</style>
