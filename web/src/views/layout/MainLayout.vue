<template>
  <div class="layout" :class="{ 'is-collapsed': collapsed }">
    <aside class="sider">
      <div class="brand">
        <div class="brand-mark">
          <n-icon :size="20"><LocationOutline /></n-icon>
        </div>
        <div v-if="!collapsed" class="brand-text">
          <span class="brand-name">一标六实</span>
          <span class="brand-sub">数据采集系统</span>
        </div>
      </div>

      <div class="nav">
        <n-menu
          inverted
          :value="activeKey"
          :options="menuOptions"
          :collapsed="collapsed"
          :collapsed-width="76"
          :collapsed-icon-size="20"
          @update:value="onMenuSelect"
        />
      </div>

      <div class="sider-foot">
        <button class="collapse-btn" type="button" :title="collapsed ? '展开菜单' : '收起菜单'" @click="collapsed = !collapsed">
          <n-icon :size="16">
            <ChevronForwardOutline v-if="collapsed" />
            <ChevronBackOutline v-else />
          </n-icon>
        </button>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="heading">
          <div v-if="isSystem" class="breadcrumb">
            <span>首页</span>
            <n-icon :size="12"><ChevronForwardOutline /></n-icon>
            <span>系统设置</span>
            <n-icon v-if="subTitle" :size="12"><ChevronForwardOutline /></n-icon>
            <span class="crumb-current">{{ subTitle }}</span>
          </div>
          <h2>{{ currentTitle }}</h2>
        </div>

        <div class="topbar-right">
          <span class="today">{{ todayText }}</span>
          <span class="divider"></span>
          <n-dropdown :options="userOptions" trigger="click" @select="onUserAction">
            <div class="user-chip">
              <n-avatar round :size="34" class="avatar">
                {{ (user.info?.real_name || user.info?.username || '?').slice(0, 1) }}
              </n-avatar>
              <div class="user-meta">
                <span class="name">{{ user.info?.real_name || user.info?.username }}</span>
                <span class="role">{{ roleText }}</span>
              </div>
              <n-icon :size="14" color="#94a3b8"><ChevronDownOutline /></n-icon>
            </div>
          </n-dropdown>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <n-modal v-model:show="passwordModal" preset="card" title="修改密码" style="width: 420px" :mask-closable="false">
      <n-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-placement="left" label-width="80">
        <n-form-item label="原密码" path="old_password">
          <n-input v-model:value="pwdForm.old_password" type="password" show-password-on="click" />
        </n-form-item>
        <n-form-item label="新密码" path="new_password">
          <n-input v-model:value="pwdForm.new_password" type="password" show-password-on="click" placeholder="至少 6 位" />
        </n-form-item>
        <n-form-item label="确认密码" path="confirm">
          <n-input v-model:value="pwdForm.confirm" type="password" show-password-on="click" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px">
          <n-button @click="passwordModal = false">取消</n-button>
          <n-button type="primary" :loading="pwdSaving" @click="changePassword">确定</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NIcon, type DropdownOption, type FormInst, type FormRules, type MenuOption } from 'naive-ui'
import {
  AppsOutline,
  BusinessOutline,
  ChevronBackOutline,
  ChevronDownOutline,
  ChevronForwardOutline,
  CompassOutline,
  DocumentTextOutline,
  ImagesOutline,
  KeyOutline,
  LayersOutline,
  LocationOutline,
  LogOutOutline,
  OptionsOutline,
  PencilOutline,
  PeopleOutline,
  SettingsOutline,
} from '@vicons/ionicons5'
import { authApi } from '@/api'
import { useUserStore } from '@/store/user'
import { dialogConfirm, toastError, toastSuccess } from '@/utils/naive'

const route = useRoute()
const router = useRouter()
const user = useUserStore()
const collapsed = ref(false)

function renderIcon(icon: unknown) {
  return () => h(NIcon, null, { default: () => h(icon as never) })
}

const menuOptions = computed<MenuOption[]>(() => {
  const options: MenuOption[] = [
    { label: '工作台', key: '/dashboard', icon: renderIcon(AppsOutline) },
  ]
  if (user.hasPerm('menu:module'))
    options.push({ label: '信息模块管理', key: '/modules', icon: renderIcon(LayersOutline) })
  if (user.hasPerm('menu:collect'))
    options.push({ label: '数据采集', key: '/collect', icon: renderIcon(PencilOutline) })
  if (user.hasPerm('menu:building'))
    options.push({ label: '建筑物采集', key: '/buildings', icon: renderIcon(BusinessOutline) })
  if (user.hasPerm('menu:facade'))
    options.push({ label: '建筑物外景', key: '/facade', icon: renderIcon(ImagesOutline) })
  if (user.hasPerm('menu:unit'))
    options.push({ label: '单位信息采集', key: '/units', icon: renderIcon(PeopleOutline) })
  if (user.hasPerm('menu:compare'))
    options.push({ label: '经纬度比对', key: '/compare', icon: renderIcon(CompassOutline) })
  if (user.hasPerm('menu:system')) {
    const children: MenuOption[] = [
      { label: '用户管理', key: '/system/users', icon: renderIcon(PeopleOutline) },
      { label: '角色权限', key: '/system/roles', icon: renderIcon(KeyOutline) },
    ]
    if (user.hasPerm('system:config'))
      children.push({ label: '系统参数', key: '/system/config', icon: renderIcon(OptionsOutline) })
    children.push({ label: '操作日志', key: '/system/logs', icon: renderIcon(DocumentTextOutline) })
    options.push({ label: '系统设置', key: '/system', icon: renderIcon(SettingsOutline), children })
  }
  return options
})

const activeKey = computed(() => route.path)
const currentTitle = computed(() => (route.meta.title as string) || '')
const isSystem = computed(() => route.path.startsWith('/system'))
const subTitle = computed(() => (isSystem.value ? currentTitle.value : ''))

const ROLE_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  collector: '采集员',
  auditor: '审核员',
  viewer: '只读用户',
}
const roleText = computed(() => {
  const roles = user.info?.roles ?? []
  if (!roles.length) return '未分配角色'
  return roles.map((r) => ROLE_LABELS[r] ?? r).join(' / ')
})

const todayText = computed(() => {
  const d = new Date()
  const week = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()]
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 ${week}`
})

const userOptions: DropdownOption[] = [
  { label: '修改密码', key: 'password', icon: renderIcon(KeyOutline) },
  { type: 'divider', key: 'd1' },
  { label: '退出登录', key: 'logout', icon: renderIcon(LogOutOutline) },
]

function onMenuSelect(key: string) {
  router.push(key)
}

async function onUserAction(key: string) {
  if (key === 'logout') {
    dialogConfirm('确定退出当前账号吗？', () => user.logout(), '退出登录')
  } else if (key === 'password') {
    passwordModal.value = true
  }
}

// ---------------- 修改密码 ----------------
const passwordModal = ref(false)
const pwdSaving = ref(false)
const pwdFormRef = ref<FormInst | null>(null)
const pwdForm = reactive({ old_password: '', new_password: '', confirm: '' })
const pwdRules: FormRules = {
  old_password: { required: true, message: '请输入原密码', trigger: ['blur', 'input'] },
  new_password: [
    { required: true, message: '请输入新密码', trigger: ['blur', 'input'] },
    { min: 6, message: '新密码至少 6 位', trigger: ['blur', 'input'] },
  ],
  confirm: {
    validator: (_rule, value: string) => {
      if (!value) return new Error('请再次输入新密码')
      if (value !== pwdForm.new_password) return new Error('两次输入的新密码不一致')
      return true
    },
    trigger: ['blur', 'input'],
  },
}

async function changePassword() {
  try {
    await pwdFormRef.value?.validate()
  } catch {
    return
  }
  pwdSaving.value = true
  try {
    await authApi.changePassword({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    toastSuccess('密码已修改，请重新登录')
    passwordModal.value = false
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm = ''
    await user.logout()
  } catch (e) {
    toastError((e as Error).message || '修改失败')
  } finally {
    pwdSaving.value = false
  }
}
</script>

<style scoped lang="scss">
.layout {
  display: flex;
  height: 100vh;
  background: var(--bg);
}

/* ---------------- 侧边栏 ---------------- */
.sider {
  width: 232px;
  flex: none;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(120% 70% at 8% 0%, #1d3157 0%, rgba(29, 49, 87, 0) 60%),
    linear-gradient(180deg, #121d33 0%, #0d1526 55%, #0a111f 100%);
  transition: width 0.22s ease;
  overflow: hidden;
}

.layout.is-collapsed .sider {
  width: 76px;
}

.brand {
  height: 72px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 20px;
  flex: none;
}

.layout.is-collapsed .brand {
  padding: 0 20px;
}

.brand-mark {
  width: 36px;
  height: 36px;
  flex: none;
  border-radius: 11px;
  display: grid;
  place-items: center;
  color: #fff;
  background: linear-gradient(135deg, #4a86ff, #1f55dc);
  box-shadow: 0 10px 20px -10px rgba(74, 134, 255, 0.95);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
}

.brand-name {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.brand-sub {
  color: rgba(255, 255, 255, 0.42);
  font-size: 11px;
  letter-spacing: 0.4px;
}

.nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px 8px 12px;
}

.nav :deep(.n-menu-item-content) {
  position: relative;
  border-radius: 10px;
  margin: 2px 0;
}

.nav :deep(.n-menu-item-content-header) {
  font-size: 13.5px;
  font-weight: 500;
}

.nav :deep(.n-menu-item-content:not(.n-menu-item-content--selected):hover) {
  background-color: rgba(255, 255, 255, 0.07) !important;
}

.nav :deep(.n-menu-item-content--selected) {
  box-shadow: 0 10px 22px -14px rgba(47, 107, 255, 0.95);
}

.nav :deep(.n-submenu .n-menu-item-content-header) {
  font-size: 13.5px;
}

.sider-foot {
  flex: none;
  padding: 10px 12px 14px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.layout.is-collapsed .sider-foot {
  justify-content: center;
}

.collapse-btn {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  border: none;
  cursor: pointer;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.65);
  display: grid;
  place-items: center;
  transition: 0.15s;
}
.collapse-btn:hover {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}

/* ---------------- 右侧主体 ---------------- */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  height: 72px;
  flex: none;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--line);
}

.heading h2 {
  margin: 2px 0 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--ink-900);
  letter-spacing: 0.2px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--ink-400);
}

.crumb-current {
  color: var(--ink-500);
}

.topbar-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 14px;
}

.today {
  font-size: 12.5px;
  color: var(--ink-500);
}

.divider {
  width: 1px;
  height: 22px;
  background: var(--line-strong);
}

.user-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 10px 5px 5px;
  border-radius: 12px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: 0.15s;
}
.user-chip:hover {
  background: #f4f7fd;
  border-color: var(--line);
}

.avatar {
  background: linear-gradient(135deg, #4a86ff, #1f55dc) !important;
  font-weight: 600;
}

.user-meta {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}
.user-meta .name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-800);
}
.user-meta .role {
  font-size: 11px;
  color: var(--ink-400);
}

.content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
