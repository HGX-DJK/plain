<template>
  <div class="page">
    <div class="page-card">
      <div class="toolbar">
        <n-input
          v-model:value="keyword"
          placeholder="搜索登录名 / 姓名 / 部门"
          clearable
          style="width: 220px"
          @keyup.enter="reload"
        />
        <n-select
          v-model:value="filterRole"
          :options="roleOptions"
          clearable
          placeholder="所属角色"
          style="width: 150px"
          @update:value="reload"
        />
        <n-select
          v-model:value="filterActive"
          :options="ACTIVE_OPTIONS"
          clearable
          placeholder="账号状态"
          style="width: 130px"
          @update:value="reload"
        />
        <n-button @click="reload">查询</n-button>
        <div class="spacer" />
        <n-button v-if="can('system:user')" type="primary" @click="openCreate">
          <template #icon><n-icon><PersonAddOutline /></n-icon></template>
          新增用户
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
        :row-key="(r: UserItem) => r.id"
      />
    </div>

    <!-- 用户表单 -->
    <n-modal
      v-model:show="showForm"
      preset="card"
      :title="formId ? '编辑用户' : '新增用户'"
      style="width: 680px; max-width: 94vw"
      :mask-closable="false"
    >
      <n-form ref="formRef" :model="form" :rules="formRules" label-placement="left" label-width="92">
        <n-grid :cols="2" :x-gap="16">
          <n-form-item-gi label="登录名" path="username">
            <n-input v-model:value="form.username" :disabled="!!formId" placeholder="2-64 位，登录使用" />
          </n-form-item-gi>
          <n-form-item-gi :label="formId ? '重置密码' : '登录密码'" path="password">
            <n-input
              v-model:value="form.password"
              type="password"
              show-password-on="click"
              :placeholder="formId ? '留空则不修改' : '至少 6 位'"
            />
          </n-form-item-gi>
          <n-form-item-gi label="姓名">
            <n-input v-model:value="form.real_name" placeholder="真实姓名" />
          </n-form-item-gi>
          <n-form-item-gi label="所属部门">
            <n-input v-model:value="form.dept" placeholder="如 数据采集科" />
          </n-form-item-gi>
          <n-form-item-gi label="手机号">
            <n-input v-model:value="form.phone" placeholder="选填" />
          </n-form-item-gi>
          <n-form-item-gi label="邮箱" path="email">
            <n-input v-model:value="form.email" placeholder="选填" />
          </n-form-item-gi>
          <n-form-item-gi label="角色" :span="2">
            <n-select
              v-model:value="form.role_ids"
              :options="roleOptions"
              multiple
              clearable
              placeholder="选择角色（决定菜单与操作权限）"
            />
          </n-form-item-gi>
        </n-grid>
        <n-form-item label="账号状态">
          <n-switch v-model:value="form.is_active">
            <template #checked>启用</template>
            <template #unchecked>停用</template>
          </n-switch>
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="form.remark" type="textarea" :rows="2" placeholder="备注（可选）" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="form-footer">
          <n-button @click="showForm = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </div>
      </template>
    </n-modal>

    <!-- 重置密码 -->
    <n-modal
      v-model:show="showReset"
      preset="card"
      :title="resetUser ? `重置密码 - ${resetUser.username}` : '重置密码'"
      style="width: 420px"
      :mask-closable="false"
    >
      <n-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-placement="left" label-width="80">
        <n-form-item label="新密码" path="new_password">
          <n-input v-model:value="resetForm.new_password" type="password" show-password-on="click" placeholder="至少 6 位" />
        </n-form-item>
        <n-form-item label="确认密码" path="confirm">
          <n-input v-model:value="resetForm.confirm" type="password" show-password-on="click" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="form-footer">
          <n-button @click="showReset = false">取消</n-button>
          <n-button type="primary" :loading="resetting" @click="doReset">确定</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { NButton, NIcon, NTag, type DataTableColumns, type FormInst, type FormRules } from 'naive-ui'
import { CreateOutline, KeyOutline, PersonAddOutline, TrashOutline } from '@vicons/ionicons5'
import { systemApi, type RoleItem, type UserItem } from '@/api'
import { useUserStore } from '@/store/user'
import { dialogConfirm, toastError, toastSuccess } from '@/utils/naive'
import { formatDateTime } from '@/utils/time'

const store = useUserStore()
const can = (code: string) => store.hasPerm(code)

const ACTIVE_OPTIONS = [
  { label: '启用', value: 'yes' },
  { label: '停用', value: 'no' },
]

const keyword = ref('')
const filterRole = ref<number | null>(null)
const filterActive = ref<string | null>(null)
const rows = ref<UserItem[]>([])
const roles = ref<RoleItem[]>([])
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

const roleOptions = computed(() => roles.value.map((r) => ({ label: r.name, value: r.id })))
const roleNameOf = (code: string) => roles.value.find((r) => r.code === code)?.name ?? code

async function loadRoles() {
  try {
    roles.value = await systemApi.roles()
  } catch (e) {
    toastError((e as Error).message || '加载角色失败')
  }
}

async function load() {
  loading.value = true
  try {
    const res = await systemApi.users({
      keyword: keyword.value || undefined,
      role_id: filterRole.value || undefined,
      is_active:
        filterActive.value === 'yes' ? true : filterActive.value === 'no' ? false : undefined,
      page: pagination.page,
      page_size: pagination.pageSize,
    })
    rows.value = res.items
    pagination.itemCount = res.total
  } catch (e) {
    toastError((e as Error).message || '加载用户列表失败')
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

const columns = computed<DataTableColumns<UserItem>>(() => [
  { title: '登录名', key: 'username', width: 130 },
  { title: '姓名', key: 'real_name', width: 110, render: (r) => r.real_name || '-' },
  { title: '部门', key: 'dept', width: 130, ellipsis: { tooltip: true }, render: (r) => r.dept || '-' },
  {
    title: '角色',
    key: 'roles',
    minWidth: 180,
    render: (r) =>
      h(
        'div',
        { style: 'display:flex;flex-wrap:wrap;gap:4px' },
        (r.roles?.length ? r.roles : ['-']).map((code) =>
          h(NTag, { size: 'small', type: code === 'super_admin' ? 'error' : 'info' }, {
            default: () => roleNameOf(code),
          }),
        ),
      ),
  },
  { title: '手机号', key: 'phone', width: 130, render: (r) => r.phone || '-' },
  {
    title: '状态',
    key: 'is_active',
    width: 80,
    render: (r) =>
      r.is_active
        ? h(NTag, { size: 'small', type: 'success' }, { default: () => '启用' })
        : h(NTag, { size: 'small', type: 'default' }, { default: () => '停用' }),
  },
  { title: '最后登录', key: 'last_login_at', width: 160, render: (r) => formatTime(r.last_login_at) },
  {
    title: '操作',
    key: 'actions',
    width: 210,
    render: (r) =>
      h('div', { style: 'display:flex;gap:4px' }, [
        can('system:user')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'primary', onClick: () => openEdit(r) },
              { icon: () => h(NIcon, null, { default: () => h(CreateOutline) }), default: () => '编辑' },
            )
          : null,
        can('system:user')
          ? h(
              NButton,
              { size: 'tiny', quaternary: true, type: 'info', onClick: () => openReset(r) },
              { icon: () => h(NIcon, null, { default: () => h(KeyOutline) }), default: () => '重置密码' },
            )
          : null,
        can('system:user')
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
  username: '',
  password: '',
  real_name: '',
  dept: '',
  phone: '',
  email: '',
  role_ids: [] as number[],
  is_active: true,
  remark: '',
})

const formRules: FormRules = {
  username: [
    { required: true, message: '请输入登录名', trigger: ['blur', 'input'] },
    { min: 2, message: '登录名至少 2 位', trigger: ['blur', 'input'] },
  ],
  password: [
    {
      validator: (_rule, value: string) => {
        if (!formId.value && !value) return new Error('请输入登录密码')
        if (value && value.length < 6) return new Error('密码至少 6 位')
        return true
      },
      trigger: ['blur', 'input'],
    },
  ],
  email: { type: 'email', message: '邮箱格式不正确', trigger: ['blur', 'input'] },
}

function openCreate() {
  formId.value = null
  Object.assign(form, {
    username: '',
    password: '',
    real_name: '',
    dept: '',
    phone: '',
    email: '',
    role_ids: [],
    is_active: true,
    remark: '',
  })
  showForm.value = true
}

function openEdit(row: UserItem) {
  formId.value = row.id
  Object.assign(form, {
    username: row.username,
    password: '',
    real_name: row.real_name ?? '',
    dept: row.dept ?? '',
    phone: row.phone ?? '',
    email: row.email ?? '',
    role_ids: (row.roles ?? [])
      .map((code) => roles.value.find((r) => r.code === code)?.id)
      .filter((id): id is number => typeof id === 'number'),
    is_active: row.is_active,
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
  saving.value = true
  try {
    if (formId.value) {
      await systemApi.updateUser(formId.value, {
        real_name: form.real_name || null,
        dept: form.dept || null,
        phone: form.phone || null,
        email: form.email || null,
        role_ids: form.role_ids,
        is_active: form.is_active,
        remark: form.remark || null,
        ...(form.password ? { password: form.password } : {}),
      })
      toastSuccess('用户已更新')
    } else {
      await systemApi.createUser({
        username: form.username.trim(),
        password: form.password,
        real_name: form.real_name || null,
        dept: form.dept || null,
        phone: form.phone || null,
        email: form.email || null,
        role_ids: form.role_ids,
        is_active: form.is_active,
        remark: form.remark || null,
      })
      toastSuccess('用户已创建')
    }
    showForm.value = false
    load()
  } catch (e) {
    toastError((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

function remove(row: UserItem) {
  dialogConfirm(`确认删除用户「${row.real_name || row.username}」？`, async () => {
    try {
      await systemApi.removeUser(row.id)
      toastSuccess('已删除')
      reload()
    } catch (e) {
      toastError((e as Error).message || '删除失败')
    }
  })
}

// ---------------- 重置密码 ----------------
const showReset = ref(false)
const resetting = ref(false)
const resetUser = ref<UserItem | null>(null)
const resetFormRef = ref<FormInst | null>(null)
const resetForm = reactive({ new_password: '', confirm: '' })
const resetRules: FormRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: ['blur', 'input'] },
    { min: 6, message: '密码至少 6 位', trigger: ['blur', 'input'] },
  ],
  confirm: {
    validator: (_rule, value: string) => {
      if (!value) return new Error('请再次输入新密码')
      if (value !== resetForm.new_password) return new Error('两次输入不一致')
      return true
    },
    trigger: ['blur', 'input'],
  },
}

function openReset(row: UserItem) {
  resetUser.value = row
  resetForm.new_password = ''
  resetForm.confirm = ''
  showReset.value = true
}

async function doReset() {
  try {
    await resetFormRef.value?.validate()
  } catch {
    return
  }
  if (!resetUser.value) return
  resetting.value = true
  try {
    await systemApi.resetPassword(resetUser.value.id, resetForm.new_password)
    toastSuccess('密码已重置')
    showReset.value = false
  } catch (e) {
    toastError((e as Error).message || '重置失败')
  } finally {
    resetting.value = false
  }
}

onMounted(async () => {
  await loadRoles()
  await load()
})
</script>

<style scoped>
.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
