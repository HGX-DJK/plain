<template>
  <div class="page">
    <div class="page-card">
      <div class="toolbar">
        <n-input
          v-model:value="keyword"
          placeholder="搜索操作人 / 操作对象"
          clearable
          style="width: 220px"
          @keyup.enter="reload"
        />
        <n-select
          v-model:value="filterAction"
          :options="ACTION_OPTIONS"
          filterable
          clearable
          placeholder="操作类型"
          style="width: 200px"
          @update:value="reload"
        />
        <n-button @click="reload">查询</n-button>
        <n-button quaternary @click="resetFilter">重置</n-button>
        <div class="spacer" />
        <n-button @click="load">
          <template #icon><n-icon><RefreshOutline /></n-icon></template>
          刷新
        </n-button>
      </div>

      <n-data-table
        size="small"
        flex-height
        style="flex: 1; min-height: 0"
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="pagination"
        remote
        :row-key="(r: LogItem) => r.id"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NIcon, NTag, type DataTableColumns } from 'naive-ui'
import { RefreshOutline } from '@vicons/ionicons5'
import { systemApi, type LogItem } from '@/api'
import { toastError } from '@/utils/naive'

const ACTION_LABELS: Record<string, string> = {
  login: '登录系统',
  logout: '退出登录',
  'user:create': '新增用户',
  'user:update': '编辑用户',
  'user:delete': '删除用户',
  'user:reset_password': '重置密码',
  'role:create': '新增角色',
  'role:update': '编辑角色',
  'role:set_permissions': '配置角色权限',
  'role:delete': '删除角色',
  'config:update': '修改系统参数',
  'config:delete': '删除系统参数',
  'module:create': '新增信息模块',
  'module:update': '编辑信息模块',
  'module:delete': '删除信息模块',
  'feature:create': '新增采集数据',
  'feature:update': '编辑采集数据',
  'feature:delete': '删除采集数据',
  'feature:batch_delete': '批量删除采集数据',
  'building:create': '新增建筑物',
  'building:update': '编辑建筑物',
  'building:delete': '删除建筑物',
  'building:attach_unit': '关联单位',
  'building:detach_unit': '解除单位关联',
  'unit:create': '新增单位',
  'unit:update': '编辑单位',
  'unit:delete': '删除单位',
  'compare:run': '发起比对',
  'compare:rerun': '重新比对',
  'compare:delete': '删除比对任务',
}

const ACTION_OPTIONS = Object.entries(ACTION_LABELS).map(([value, label]) => ({
  label: `${label}（${value}）`,
  value,
}))

const keyword = ref('')
const filterAction = ref<string | null>(null)
const rows = ref<LogItem[]>([])
const loading = ref(false)
const pagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
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
    const res = await systemApi.logs({
      keyword: keyword.value || undefined,
      action: filterAction.value || undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    rows.value = res.items
    pagination.itemCount = res.total
  } catch (e) {
    toastError((e as Error).message || '加载操作日志失败')
  } finally {
    loading.value = false
  }
}
function reload() {
  pagination.page = 1
  load()
}
function resetFilter() {
  keyword.value = ''
  filterAction.value = null
  reload()
}

function formatTime(t?: string) {
  if (!t) return '-'
  return t.replace('T', ' ').slice(0, 19)
}

function detailText(detail?: Record<string, unknown> | null) {
  if (!detail || !Object.keys(detail).length) return '-'
  try {
    return JSON.stringify(detail)
  } catch {
    return String(detail)
  }
}

const columns = computed<DataTableColumns<LogItem>>(() => [
  { title: '时间', key: 'created_at', width: 148, render: (r) => formatTime(r.created_at) },
  { title: '操作人', key: 'username', width: 96, ellipsis: { tooltip: true }, render: (r) => r.username || '-' },
  {
    title: '操作类型',
    key: 'action',
    width: 132,
    render: (r) =>
      h(
        NTag,
        { size: 'small', type: actionType(r.action) },
        { default: () => ACTION_LABELS[r.action] ?? r.action },
      ),
  },
  { title: '操作对象', key: 'target', minWidth: 110, ellipsis: { tooltip: true }, render: (r) => r.target || '-' },
  {
    title: '详情',
    key: 'detail',
    minWidth: 180,
    ellipsis: { tooltip: true },
    render: (r) => h('code', { style: 'font-size:12px;color:#666' }, detailText(r.detail)),
  },
  { title: 'IP', key: 'ip', width: 112, render: (r) => r.ip || '-' },
])

function actionType(action: string): 'success' | 'error' | 'warning' | 'info' | 'default' {
  if (action.endsWith(':delete') || action.includes('batch_delete')) return 'error'
  if (action.endsWith(':create')) return 'success'
  if (action.endsWith(':update') || action.includes('permissions') || action.includes('config')) return 'warning'
  return 'info'
}

onMounted(load)
</script>
