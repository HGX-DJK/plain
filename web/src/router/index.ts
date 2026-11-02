import { createRouter, createWebHashHistory } from 'vue-router'
import { useUserStore } from '@/store/user'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    {
      path: '/',
      component: () => import('@/views/layout/MainLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          meta: { title: '工作台', perm: 'menu:dashboard' },
          component: () => import('@/views/dashboard/DashboardView.vue'),
        },
        {
          path: 'modules',
          name: 'modules',
          meta: { title: '信息模块管理', perm: 'menu:module' },
          component: () => import('@/views/module/ModuleListView.vue'),
        },
        {
          path: 'collect',
          name: 'collect',
          meta: { title: '数据采集', perm: 'menu:collect' },
          component: () => import('@/views/collect/CollectView.vue'),
        },
        {
          path: 'buildings',
          name: 'buildings',
          meta: { title: '建筑物采集', perm: 'menu:building' },
          component: () => import('@/views/building/BuildingListView.vue'),
        },
        {
          path: 'facade',
          name: 'facade',
          meta: { title: '建筑物外景', perm: 'menu:facade' },
          component: () => import('@/views/facade/FacadeView.vue'),
        },
        {
          path: 'units',
          name: 'units',
          meta: { title: '单位信息采集', perm: 'menu:unit' },
          component: () => import('@/views/unit/UnitListView.vue'),
        },
        {
          path: 'compare',
          name: 'compare',
          meta: { title: '经纬度比对', perm: 'menu:compare' },
          component: () => import('@/views/compare/CompareView.vue'),
        },
        {
          path: 'system/users',
          name: 'system-users',
          meta: { title: '用户管理', perm: 'system:view' },
          component: () => import('@/views/system/UserView.vue'),
        },
        {
          path: 'system/roles',
          name: 'system-roles',
          meta: { title: '角色权限', perm: 'system:view' },
          component: () => import('@/views/system/RoleView.vue'),
        },
        {
          path: 'system/config',
          name: 'system-config',
          meta: { title: '系统参数', perm: 'system:config' },
          component: () => import('@/views/system/ConfigView.vue'),
        },
        {
          path: 'system/logs',
          name: 'system-logs',
          meta: { title: '操作日志', perm: 'system:view' },
          component: () => import('@/views/system/LogView.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach(async (to) => {
  const user = useUserStore()
  if (to.name === 'login') return true
  if (!user.isLogin) return { name: 'login' }
  if (!user.info) {
    try {
      await user.fetchMe()
    } catch {
      return { name: 'login' }
    }
  }
  // 刷新页面后 store 会重置，这里补拉一次启动配置（地图底图、默认阈值等依赖它）
  if (!user.bootstrap) {
    try {
      await user.loadBootstrap()
    } catch {
      /* 启动配置拉取失败不阻塞进入页面 */
    }
  }
  const perm = to.meta.perm as string | undefined
  if (perm && !user.hasPerm(perm)) return { name: 'dashboard' }
  return true
})

export default router
