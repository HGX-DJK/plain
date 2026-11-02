<template>
  <div class="page">
    <div class="page-card">
      <div class="toolbar">
        <n-input v-model:value="keyword" placeholder="搜索角色名称 / 编码" clearable style="width: 220px" />
        <n-button @click="reload">刷新</n-button>
        <div class="spacer" />
        <n-button v-if="can('system:role')" type="primary" @click="openCreate">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          新增角色
        </n-button>
      </div>

      <n-data-table
        flex-height
        style="flex: 1; min-height: 0"
        :columns="columns"
        :data="filteredRoles"
        :loading="loading"
        :row-key="(r: RoleItem) => r.id"
        :pagination="{ pageSize: 20, showSizePicker: false }"
      />
    </div>

    <!-- 角色表单 -->
    <n-modal
      v-model:show="showForm"
      preset="card"
      :title="formId ? '编辑角色' : '新增角色'"
      style="width: 560px; max-width: 94vw"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="formRules" label-placement="left" label-width="90">
        <n-form-item label="角色编码" path="code">
          <n-input
            v-model:value="form.code"
            :disabled="formBuiltin"
            placeholder="如 collector（字母数字下划线）"
          />
        </n-form-item>
        <n-form-item label="角色名称" path="name">
          <n-input v-model:value="form.name" placeholder="如 采集员" />
        </n-form-item>
        <n-form-item label="角色说明">
          <n-input v-model:value="form.description" type="textarea" :rows="2" placeholder="角色职责说明（可选）" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="form-footer">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 权限配置 -->
    <n-modal
      v-model:show="showPerm"
      preset="card"
      :title="permRole ? `配置权限 - ${permRole.name}` : '配置权限'"
      style="width: 860px; max-width: 94vw"
      :mask-closable="false"
    >
      <n-alert v-if="permRole?.code === 'super_admin'" type="warning" :show-icon="false" size="small">
        超级管理员默认拥有全部权限，不支持在此修改。
      </n-alert>
      <n-checkbox-group v-model:value="checkedIds">
        <div class="perm-section">
          <div class="perm-section-title">
            <n-checkbox
              :checked="allChecked(menuIds)"
              :indeterminate="indeterminate(menuIds)"
              :disabled="permReadonly"
              @update:checked="(v: boolean) => toggleGroup(menuIds, v)"
            >
              菜单权限
            </n-checkbox>
            <span class="perm-tip">控制左侧菜单可见性</span>
          </div>
          <div class="perm-items">
            <n-checkbox v-for="p in menuPerms" :key="p.id" :value="p.id" :disabled="permReadonly">
              {{ p.name }}
            </n-checkbox>
          </div>
        </div>

        <div v-for="g in actionGroups" :key="g.module" class="perm-section">
          <div class="perm-section-title">
            <n-checkbox
              :checked="allChecked(g.ids)"
              :indeterminate="indeterminate(g.ids)"
              :disabled="permReadonly"
              @update:checked="(v: boolean) => toggleGroup(g.ids, v)"
            >
              {{ g.label }}
            </n-checkbox>
            <span class="perm-tip">{{ g.items.length }} 项操作权限</span>
          </div>
          <div class="perm-items">
            <n-checkbox v-for="p in g.items" :key="p.id" :value="p.id" :disabled="permReadonly">
              {{ p.name }}
            </n-checkbox>
          </div>
        </div>
      </n-checkbox-group>

      <template #footer>
        <div class="form-footer">
          <n-button @click="showPerm = false">取消</n-button>
          <n-button type="primary" :loading="permSaving" :disabled="permReadonly" @click="savePermissions">
            保存权限
          </n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NIcon, NTag, type DataTableColumns, type FormInst, type FormRules } from 'naive-ui'
import { AddOutline, CreateOutline, KeyOutline, TrashOutline } from '@vicons/ionicons5'
import { systemApi, type PermissionItem, type RoleItem } from '@/api'
import { useUserStore } from '@/store/user'
import { dialogConfirm, toastError, toastSuccess } from '@/utils/naive'

const store = useUserStore()
const can = (code: string) => store.hasPerm(code)

const MODULE_LABELS: Record<string, string> = {
  module: '信息模块',
  feature: '数据采集',
  building: '建筑物采集',
  unit: '单位信息采集',
  compare: '经纬度比对',
  system: '系统设置',
}

const keyword = ref('')
const roles = ref<RoleItem[]>([])
const permissions = ref<PermissionItem[]>([])
const loading = ref(false)

const filteredRoles = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return roles.value
  return roles.value.filter(
    (r) => r.name.toLowerCase().includes(kw) || r.code.toLowerCase().includes(kw),
  )
})

async function loadRoles() {
  loading.value = true
  try {
    roles.value = await systemApi.roles()
  } catch (e) {
    toastError((e as Error).message || '加载角色失败')
  } finally {
    loading.value = false
  }
}

async function loadPermissions() {
  try {
    permissions.value = await systemApi.permissions()
  } catch (e) {
    toastError((e as Error).message || '加载权限点失败')
  }
}

function reload() {
  loadRoles()
}

const columns = computed<DataTableColumns<RoleItem>>(() => [
  { title: '角色编码', key: 'code', width: 150 },
  { title: '角色名称', key: 'name', width: 140 },
  { title: '说明', key: 'description', minWidth: 200, ellipsis: { tooltip: true }, render: (r) => r.description || '-' },
  {
    title: '权限数',
    key: 'permission_ids',
    width: 90,
    render: (r) => r.permission_ids?.length ?? 0,
  },
  { title: '用户数', key: 'user_count', width: 80 },
  {
    title: '类型',
    key: 'is_builtin',
    width: 90,
    render: (r) =>
      r.is_builtin
        ? h(NTag, { size: 'small', type: 'info' }, { default: () => '内置' })
        : h(NTag, { size: 'small' }, { default: () => '自定义' }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    render: (r) =>
      h('div', { style: 'display:flex;gap:4px' }, [
        can('system:role')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'primary', onClick: () => openEdit(r) },
              { icon: () => h(NIcon, null, { default: () => h(CreateOutline) }), default: () => '编辑' },
            )
          : null,
        can('system:role')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'info', onClick: () => openPerm(r) },
              { icon: () => h(NIcon, null, { default: () => h(KeyOutline) }), default: () => '权限' },
            )
          : null,
        can('system:role') && !r.is_builtin
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'error', onClick: () => remove(r) },
              { icon: () => h(NIcon, null, { default: () => h(TrashOutline) }), default: () => '删除' },
            )
          : null,
      ]),
  },
])

// ---------------- 角色表单 ----------------
const showForm = ref(false)
const saving = ref(false)
const formId = ref<number | null>(null)
const formBuiltin = ref(false)
const formRef = ref<FormInst | null>(null)
const form = reactive({ code: '', name: '', description: '' })
const formRules: FormRules = {
  code: [
    { required: true, message: '请输入角色编码', trigger: ['blur', 'input'] },
    { pattern: /^[A-Za-z0-9_-]+$/, message: '仅支持字母、数字、下划线、中划线', trigger: ['blur', 'input'] },
  ],
  name: { required: true, message: '请输入角色名称', trigger: ['blur', 'input'] },
}

function openCreate() {
  formId.value = null
  formBuiltin.value = false
  Object.assign(form, { code: '', name: '', description: '' })
  showForm.value = true
}

function openEdit(row: RoleItem) {
  formId.value = row.id
  formBuiltin.value = row.is_builtin
  Object.assign(form, { code: row.code, name: row.name, description: row.description ?? '' })
  showForm.value = true
}

async function save() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  const payload = {
    code: form.code.trim(),
    name: form.name.trim(),
    description: form.description || null,
  }
  saving.value = true
  try {
    if (formId.value) {
      await systemApi.updateRole(formId.value, payload)
      toastSuccess('角色已更新')
    } else {
      await systemApi.createRole({ ...payload, permission_ids: [] })
      toastSuccess('角色已创建，请继续配置权限')
    }
    showForm.value = false
    loadRoles()
  } catch (e) {
    toastError((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

function remove(row: RoleItem) {
  dialogConfirm(`确认删除角色「${row.name}」？`, async () => {
    try {
      await systemApi.removeRole(row.id)
      toastSuccess('已删除')
      loadRoles()
    } catch (e) {
      toastError((e as Error).message || '删除失败')
    }
  })
}

// ---------------- 权限配置 ----------------
const showPerm = ref(false)
const permSaving = ref(false)
const permRole = ref<RoleItem | null>(null)
const checkedIds = ref<number[]>([])

const permReadonly = computed(() => permRole.value?.code === 'super_admin')
const menuPerms = computed(() => permissions.value.filter((p) => p.perm_type === 'menu'))
const menuIds = computed(() => menuPerms.value.map((p) => p.id))
const actionGroups = computed(() => {
  const groups = new Map<string, PermissionItem[]>()
  permissions.value
    .filter((p) => p.perm_type !== 'menu')
    .forEach((p) => {
      const list = groups.get(p.module) ?? []
      list.push(p)
      groups.set(p.module, list)
    })
  return Array.from(groups.entries()).map(([module, items]) => ({
    module,
    label: MODULE_LABELS[module] ?? module,
    items,
    ids: items.map((i) => i.id),
  }))
})

function allChecked(ids: number[]) {
  return ids.length > 0 && ids.every((id) => checkedIds.value.includes(id))
}
function indeterminate(ids: number[]) {
  const hit = ids.filter((id) => checkedIds.value.includes(id)).length
  return hit > 0 && hit < ids.length
}
function toggleGroup(ids: number[], checked: boolean) {
  if (permReadonly.value) return
  if (checked) {
    checkedIds.value = Array.from(new Set([...checkedIds.value, ...ids]))
  } else {
    checkedIds.value = checkedIds.value.filter((id) => !ids.includes(id))
  }
}

async function openPerm(row: RoleItem) {
  if (!permissions.value.length) await loadPermissions()
  permRole.value = row
  checkedIds.value = [...(row.permission_ids ?? [])]
  showPerm.value = true
}

async function savePermissions() {
  const role = permRole.value
  if (!role) return
  permSaving.value = true
  try {
    const updated = await systemApi.setRolePermissions(role.id, checkedIds.value)
    toastSuccess('权限已保存')
    showPerm.value = false
    const idx = roles.value.findIndex((r) => r.id === role.id)
    if (idx >= 0) roles.value[idx] = updated
  } catch (e) {
    toastError((e as Error).message || '保存权限失败')
  } finally {
    permSaving.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadRoles(), loadPermissions()])
})
</script>

<style scoped>
.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.perm-section {
  border: 1px solid #eef0f3;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.perm-section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  margin-bottom: 8px;
}
.perm-tip {
  color: #999;
  font-size: 12px;
  font-weight: normal;
}
.perm-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  padding-left: 24px;
}
</style>
