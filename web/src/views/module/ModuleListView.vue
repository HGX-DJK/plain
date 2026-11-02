<template>
  <div class="page">
    <div class="page-card">
      <div class="toolbar">
        <n-input
          v-model:value="keyword"
          placeholder="搜索模块名称/编码"
          clearable
          style="width: 220px"
          @keyup.enter="reload"
        />
        <n-select
          v-model:value="filterGeom"
          :options="GEOM_OPTIONS"
          clearable
          placeholder="空间类型"
          style="width: 130px"
          @update:value="reload"
        />
        <n-button @click="reload">查询</n-button>
        <div class="spacer" />
        <n-button v-if="can('module:create')" type="primary" @click="openCreate">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          新增信息模块
        </n-button>
      </div>

      <n-data-table
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="pagination"
        remote
        :row-key="(r: InfoModule) => r.id"
      />
    </div>

    <n-modal
      v-model:show="showForm"
      preset="card"
      :title="formId ? '编辑信息模块' : '新增信息模块'"
      style="width: 720px; max-width: 92vw"
      :content-style="{ maxHeight: 'calc(100vh - 220px)', overflowY: 'auto', paddingRight: '6px' }"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="formRules" label-placement="left" label-width="82">
        <n-grid :cols="2" :x-gap="16">
          <n-form-item-gi label="模块编码" path="code">
            <n-input v-model:value="form.code" placeholder="如 POI、YARD（字母数字下划线）" :disabled="!!formId" />
          </n-form-item-gi>
          <n-form-item-gi label="模块名称" path="name">
            <n-input v-model:value="form.name" placeholder="如 院落信息" />
          </n-form-item-gi>
          <n-form-item-gi label="空间类型" path="geom_type">
            <n-radio-group v-model:value="form.geom_type">
              <n-radio-button v-for="g in GEOM_OPTIONS" :key="g.value" :value="g.value">
                {{ g.label }}
              </n-radio-button>
            </n-radio-group>
          </n-form-item-gi>
          <n-form-item-gi label="分类" path="category">
            <n-input v-model:value="form.category" placeholder="可选，如 基础地理" />
          </n-form-item-gi>
          <n-form-item-gi label="图层颜色" path="color">
            <n-color-picker v-model:value="form.color" :show-alpha="false" :swatches="COLOR_SWATCHES" />
          </n-form-item-gi>
          <n-form-item-gi label="图层顺序" path="layer_order">
            <n-input-number v-model:value="form.layer_order" :min="0" :max="999" style="width: 100%" />
          </n-form-item-gi>
          <n-form-item-gi label="是否启用" path="is_active">
            <n-switch v-model:value="form.is_active" />
          </n-form-item-gi>
          <n-form-item-gi label="允许编辑" path="editable">
            <n-switch v-model:value="form.editable" />
          </n-form-item-gi>
        </n-grid>
        <n-form-item label="描述" path="description">
          <n-input v-model:value="form.description" type="textarea" :rows="1" placeholder="模块用途说明（可选）" />
        </n-form-item>

        <n-divider title-placement="left">属性字段（采集时动态生成表单）</n-divider>
        <div v-if="!form.fields.length" class="field-empty">暂未添加属性字段</div>
        <div v-for="(f, i) in form.fields" :key="i" class="field-box">
          <n-grid :cols="2" :x-gap="14" :y-gap="6">
            <n-form-item-gi label="编码" :path="`fields[${i}].key`">
              <n-input v-model:value="f.key" placeholder="name" />
            </n-form-item-gi>
            <n-form-item-gi label="名称" :path="`fields[${i}].label`">
              <n-input v-model:value="f.label" placeholder="要素名称" />
            </n-form-item-gi>
            <n-form-item-gi label="类型" :path="`fields[${i}].data_type`">
              <n-select v-model:value="f.data_type" :options="DATA_TYPE_OPTIONS" />
            </n-form-item-gi>
            <n-form-item-gi label="默认值">
              <n-input v-model:value="f.default_value" placeholder="可选" />
            </n-form-item-gi>
            <n-form-item-gi v-if="f.data_type === 'select'" label="选项" :span="2" :path="`fields[${i}].optionsText`">
              <n-input
                v-model:value="f.optionsText"
                type="textarea"
                :rows="2"
                placeholder="每行一个，格式：值=标签，如：1=一级"
              />
            </n-form-item-gi>
            <n-form-item-gi label="必填">
              <n-switch v-model:value="f.required" />
            </n-form-item-gi>
            <n-form-item-gi label="唯一值">
              <n-switch v-model:value="f.unique_value" />
            </n-form-item-gi>
            <n-form-item-gi label="列表显示">
              <n-switch v-model:value="f.show_in_list" />
            </n-form-item-gi>
            <n-form-item-gi label="顺序">
              <n-input-number v-model:value="f.sort_order" :min="0" size="small" style="width: 100%" />
            </n-form-item-gi>
          </n-grid>
          <div class="field-actions">
            <n-button size="tiny" quaternary type="primary" :disabled="i === 0" @click="moveField(i, -1)">上移</n-button>
            <n-button size="tiny" quaternary :disabled="i === form.fields.length - 1" @click="moveField(i, 1)">下移</n-button>
            <n-button size="tiny" quaternary type="error" @click="form.fields.splice(i, 1)">删除</n-button>
          </div>
        </div>
        <n-button dashed block type="primary" @click="addField">+ 添加属性字段</n-button>
      </n-form>

      <template #footer>
        <div class="form-footer">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NIcon, NTag, type DataTableColumns, type FormInst, type FormRules } from 'naive-ui'
import { AddOutline, CreateOutline, TrashOutline } from '@vicons/ionicons5'
import { moduleApi, type FieldDef, type InfoModule } from '@/api'
import { useUserStore } from '@/store/user'
import { dialogConfirm, toastError, toastSuccess } from '@/utils/naive'

const store = useUserStore()
const can = (code: string) => store.hasPerm(code)

const GEOM_OPTIONS = [
  { label: '点', value: 'point' },
  { label: '线', value: 'line' },
  { label: '面', value: 'polygon' },
]
const GEOM_LABELS: Record<string, string> = { point: '点', line: '线', polygon: '面' }
const DATA_TYPE_OPTIONS = [
  { label: '文本', value: 'string' },
  { label: '整数', value: 'integer' },
  { label: '数字', value: 'number' },
  { label: '布尔', value: 'boolean' },
  { label: '日期', value: 'date' },
  { label: '下拉选择', value: 'select' },
]
const COLOR_SWATCHES = ['#2d8cf0', '#18a058', '#f0a020', '#d03050', '#8a2be2', '#0e7a80', '#f5222d', '#fa8c16', '#52c41a', '#1890ff']

interface FieldRow extends FieldDef {
  optionsText?: string
}

const keyword = ref('')
const filterGeom = ref<string | null>(null)
const rows = ref<InfoModule[]>([])
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
    const res = await moduleApi.list({
      keyword: keyword.value || undefined,
      geom_type: filterGeom.value || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    rows.value = res.items
    pagination.itemCount = res.total
  } catch (e) {
    toastError((e as Error).message || '加载失败')
  } finally {
    loading.value = false
  }
}
function reload() {
  pagination.page = 1
  load()
}

const columns = computed<DataTableColumns<InfoModule>>(() => [
  { title: '名称', key: 'name', minWidth: 140 },
  { title: '编码', key: 'code', width: 110 },
  {
    title: '空间类型',
    key: 'geom_type',
    width: 90,
    render: (r) => h(NTag, { size: 'small', type: 'info' }, { default: () => GEOM_LABELS[r.geom_type] ?? r.geom_type }),
  },
  { title: '分类', key: 'category', width: 100, render: (r) => r.category || '-' },
  {
    title: '颜色',
    key: 'color',
    width: 70,
    render: (r) =>
      h('span', {
        style: `display:inline-block;width:16px;height:16px;border-radius:4px;background:${r.color};vertical-align:middle`,
      }),
  },
  { title: '顺序', key: 'layer_order', width: 60 },
  { title: '字段', key: 'fields', width: 60, render: (r) => r.fields?.length ?? 0 },
  { title: '数据量', key: 'feature_count', width: 80, render: (r) => r.feature_count ?? 0 },
  {
    title: '状态',
    key: 'is_active',
    width: 90,
    render: (r) =>
      r.is_active
        ? h(NTag, { size: 'small', type: 'success' }, { default: () => '启用' })
        : h(NTag, { size: 'small', type: 'default' }, { default: () => '停用' }),
  },
  {
    title: '锁定',
    key: 'editable',
    width: 80,
    render: (r) => (r.editable ? '-' : h(NTag, { size: 'small', type: 'warning' }, { default: () => '已锁定' })),
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    render: (r) =>
      h('div', { style: 'display:flex;gap:6px' }, [
        can('module:update')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'primary', onClick: () => openEdit(r) },
              { icon: () => h(NIcon, null, { default: () => h(CreateOutline) }), default: () => '编辑' },
            )
          : null,
        can('module:delete')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'error', onClick: () => remove(r) },
              { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }), default: () => '删除' },
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
  code: '',
  name: '',
  geom_type: 'point' as string,
  category: null as string | null,
  color: '#2d8cf0',
  layer_order: 0,
  editable: true,
  is_active: true,
  description: null as string | null,
  fields: [] as FieldRow[],
})

const formRules: FormRules = {
  code: [
    { required: true, message: '请输入模块编码', trigger: ['blur', 'input'] },
    { pattern: /^[A-Za-z0-9_-]+$/, message: '仅支持字母、数字、下划线、中划线', trigger: ['blur', 'input'] },
  ],
  name: { required: true, message: '请输入模块名称', trigger: ['blur', 'input'] },
  geom_type: { required: true, message: '请选择空间类型' },
}

function addField() {
  form.fields.push({
    key: '',
    label: '',
    data_type: 'string',
    required: false,
    unique_value: false,
    options: null,
    default_value: null,
    placeholder: null,
    help_text: null,
    show_in_list: true,
    searchable: false,
    sort_order: form.fields.length,
    optionsText: '',
  })
}
function moveField(i: number, delta: number) {
  const j = i + delta
  if (j < 0 || j >= form.fields.length) return
  const [item] = form.fields.splice(i, 1)
  form.fields.splice(j, 0, item)
}

function parseOptions(text?: string): { label: string; value: string }[] | null {
  if (!text || !text.trim()) return null
  return text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      const idx = l.indexOf('=')
      if (idx < 0) return { label: l, value: l }
      return { value: l.slice(0, idx).trim(), label: l.slice(idx + 1).trim() || l.slice(0, idx).trim() }
    })
}

function openCreate() {
  formId.value = null
  Object.assign(form, {
    code: '',
    name: '',
    geom_type: 'point',
    category: null,
    color: '#2d8cf0',
    layer_order: 0,
    editable: true,
    is_active: true,
    description: null,
    fields: [],
  })
  showForm.value = true
}
function openEdit(row: InfoModule) {
  formId.value = row.id
  Object.assign(form, {
    code: row.code,
    name: row.name,
    geom_type: row.geom_type,
    category: row.category,
    color: row.color,
    layer_order: row.layer_order,
    editable: row.editable,
    is_active: row.is_active,
    description: row.description,
    fields: (row.fields ?? []).map((f) => ({
      ...f,
      optionsText: (f.options ?? []).map((o) => `${o.value}=${o.label}`).join('\n'),
    })),
  })
  showForm.value = true
}

async function save() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  for (const f of form.fields) {
    if (!f.key.trim() || !f.label.trim()) {
      toastError('属性字段的编码与名称不能为空')
      return
    }
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(f.key.trim())) {
      toastError(`属性字段编码「${f.key}」仅支持字母、数字、下划线，且不能以数字开头`)
      return
    }
  }
  const keys = form.fields.map((f) => f.key.trim())
  if (new Set(keys).size !== keys.length) {
    toastError('属性字段编码不能重复')
    return
  }
  const payload = {
    code: form.code.trim(),
    name: form.name.trim(),
    geom_type: form.geom_type as InfoModule['geom_type'],
    category: form.category || null,
    color: form.color,
    layer_order: form.layer_order,
    editable: form.editable,
    is_active: form.is_active,
    description: form.description || null,
    fields: form.fields.map((f, i) => ({
      id: f.id ?? null,
      key: f.key.trim(),
      label: f.label.trim(),
      data_type: f.data_type,
      required: f.required,
      unique_value: f.unique_value,
      options: f.data_type === 'select' ? parseOptions(f.optionsText) : null,
      default_value: f.default_value || null,
      placeholder: f.placeholder || null,
      help_text: f.help_text || null,
      validation: f.validation ?? null,
      show_in_list: f.show_in_list,
      searchable: f.searchable ?? false,
      sort_order: i,
    })),
  }
  saving.value = true
  try {
    if (formId.value) {
      await moduleApi.update(formId.value, payload)
      toastSuccess('信息模块已更新')
    } else {
      await moduleApi.create(payload)
      toastSuccess('信息模块已创建，可开始采集该模块数据')
    }
    showForm.value = false
    load()
  } catch (e) {
    toastError((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

function remove(row: InfoModule) {
  dialogConfirm(`删除模块「${row.name}」将连同其全部采集数据一起删除，确认继续？`, async () => {
    try {
      await moduleApi.remove(row.id)
      toastSuccess('已删除')
      reload()
    } catch (e) {
      toastError((e as Error).message || '删除失败')
    }
  })
}

onMounted(load)
</script>

<style scoped>
.field-empty {
  color: #999;
  font-size: 13px;
  margin-bottom: 10px;
}
.field-box {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  padding: 10px 12px 0;
  margin-bottom: 10px;
  position: relative;
}
.field-actions {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
  padding-bottom: 6px;
}
.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
