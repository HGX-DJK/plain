<template>
  <div class="login-page">
    <section class="login-visual">
      <div class="visual-glow glow-a"></div>
      <div class="visual-glow glow-b"></div>
      <div class="visual-grid"></div>

      <div class="visual-brand">
        <div class="brand-mark">
          <n-icon :size="22"><LocationOutline /></n-icon>
        </div>
        <div class="brand-text">
          <strong>{{ appName }}</strong>
          <span>PLAINS · SPATIAL DATA PLATFORM</span>
        </div>
      </div>

      <div class="visual-copy">
        <h1>空间数据采集<br />一体化工作台</h1>
        <p>从要素绘制到建筑建档、单位关联与经纬度比对，全流程在线留痕。</p>

        <ul class="visual-points">
          <li v-for="p in features" :key="p.title">
            <span class="point-icon">
              <n-icon :size="17"><component :is="p.icon" /></n-icon>
            </span>
            <span class="point-text">
              <strong>{{ p.title }}</strong>
              <small>{{ p.desc }}</small>
            </span>
          </li>
        </ul>
      </div>

      <div class="visual-foot">© 2026 Plains · 空间数据采集与分析平台</div>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="login-head">
          <h2>欢迎回来</h2>
          <p>请使用系统账号登录，继续你的采集工作</p>
        </div>

        <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" size="large">
          <n-form-item label="账号" path="username">
            <n-input v-model:value="form.username" placeholder="请输入账号" clearable @keyup.enter="onSubmit">
              <template #prefix>
                <n-icon :size="16" color="#94a3b8"><PersonOutline /></n-icon>
              </template>
            </n-input>
          </n-form-item>
          <n-form-item label="密码" path="password">
            <n-input
              v-model:value="form.password"
              type="password"
              show-password-on="click"
              placeholder="请输入密码"
              @keyup.enter="onSubmit"
            >
              <template #prefix>
                <n-icon :size="16" color="#94a3b8"><LockClosedOutline /></n-icon>
              </template>
            </n-input>
          </n-form-item>
        </n-form>

        <n-button type="primary" size="large" block :loading="loading" class="login-btn" @click="onSubmit">
          登 录
        </n-button>

        <div class="login-tip">
          <n-icon :size="13"><ShieldCheckmarkOutline /></n-icon>
          初始账号 admin / Admin@123，首次登录后请及时修改密码
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { type FormInst, type FormRules } from 'naive-ui'
import {
  CompassOutline,
  LayersOutline,
  LinkOutline,
  LocationOutline,
  LockClosedOutline,
  PencilOutline,
  PersonOutline,
  ShieldCheckmarkOutline,
} from '@vicons/ionicons5'
import { useUserStore } from '@/store/user'
import { toastError, toastSuccess } from '@/utils/naive'

const router = useRouter()
const store = useUserStore()

const formRef = ref<FormInst | null>(null)
const loading = ref(false)
const form = reactive({ username: 'admin', password: '' })

const rules: FormRules = {
  username: { required: true, message: '请输入账号', trigger: ['blur', 'input'] },
  password: { required: true, message: '请输入密码', trigger: ['blur', 'input'] },
}

const appName = computed(() => store.bootstrap?.app_name || '一标六实数据采集系统')

const features: Array<{ icon: Component; title: string; desc: string }> = [
  { icon: LayersOutline, title: '信息模块自定义', desc: '按业务定义图层几何类型与属性字段' },
  { icon: PencilOutline, title: '地图可视化采集', desc: '点线面在线绘制，属性即时入库' },
  { icon: LinkOutline, title: '建筑与单位关联', desc: '一栋多单位，占比与权属关系清晰' },
  { icon: CompassOutline, title: '经纬度智能比对', desc: '申报坐标与实测坐标自动核差' },
]

onMounted(() => {
  // 登录页提前拉取启动配置，用于展示系统名称
  store.loadBootstrap().catch(() => {
    /* 忽略启动配置拉取失败 */
  })
})

async function onSubmit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  loading.value = true
  try {
    await store.login(form.username.trim(), form.password)
    try {
      await store.loadBootstrap()
    } catch {
      /* 启动配置拉取失败不阻塞登录 */
    }
    toastSuccess('登录成功')
    router.replace('/dashboard')
  } catch (e) {
    toastError((e as Error).message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-page {
  display: flex;
  min-height: 100vh;
  background: #f3f5fa;
}

/* ---------------- 左侧品牌区 ---------------- */
.login-visual {
  width: 52%;
  max-width: 720px;
  position: relative;
  overflow: hidden;
  padding: 48px 56px;
  display: flex;
  flex-direction: column;
  color: #fff;
  background:
    radial-gradient(90% 60% at 15% 0%, #1e3468 0%, rgba(30, 52, 104, 0) 60%),
    linear-gradient(160deg, #0d1730 0%, #0f1c39 45%, #0a1224 100%);
}

.visual-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.55;
  pointer-events: none;
}
.glow-a {
  width: 420px;
  height: 420px;
  top: -160px;
  right: -80px;
  background: #2f6bff;
}
.glow-b {
  width: 340px;
  height: 340px;
  bottom: -140px;
  left: -60px;
  background: #18a0b8;
  opacity: 0.35;
}

.visual-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(80% 70% at 30% 30%, #000 0%, transparent 80%);
  pointer-events: none;
}

.visual-brand {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #4a86ff, #1f55dc);
  box-shadow: 0 14px 28px -14px rgba(74, 134, 255, 0.9);
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}
.brand-text strong {
  font-size: 16px;
  letter-spacing: 0.5px;
}
.brand-text span {
  font-size: 10px;
  letter-spacing: 1.4px;
  color: rgba(255, 255, 255, 0.4);
}

.visual-copy {
  position: relative;
  margin-top: auto;
  margin-bottom: auto;
  padding: 40px 0;
}

.visual-copy h1 {
  margin: 0 0 16px;
  font-size: 38px;
  line-height: 1.28;
  font-weight: 600;
  letter-spacing: 1px;
}

.visual-copy > p {
  margin: 0 0 32px;
  max-width: 420px;
  font-size: 14px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.62);
}

.visual-points {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 22px;
  max-width: 560px;
}

.visual-points li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.point-icon {
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 9px;
  display: grid;
  place-items: center;
  color: #9dc0ff;
  background: rgba(84, 137, 255, 0.14);
  border: 1px solid rgba(120, 166, 255, 0.22);
}

.point-text {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.point-text strong {
  font-size: 13.5px;
  font-weight: 600;
}
.point-text small {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.45);
  line-height: 1.5;
}

.visual-foot {
  position: relative;
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.32);
  letter-spacing: 0.4px;
}

/* ---------------- 右侧表单区 ---------------- */
.login-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  background:
    radial-gradient(60% 50% at 80% 10%, rgba(47, 107, 255, 0.08) 0%, rgba(47, 107, 255, 0) 70%),
    radial-gradient(50% 40% at 10% 90%, rgba(24, 160, 184, 0.08) 0%, rgba(24, 160, 184, 0) 70%);
}

.login-card {
  width: 100%;
  max-width: 420px;
  padding: 40px 38px 32px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 20px;
  box-shadow:
    0 2px 4px rgba(15, 23, 42, 0.02),
    0 30px 60px -40px rgba(15, 23, 42, 0.5);
}

.login-head {
  margin-bottom: 26px;
}
.login-head h2 {
  margin: 0 0 8px;
  font-size: 26px;
  font-weight: 600;
  color: var(--ink-900);
  letter-spacing: 0.4px;
}
.login-head p {
  margin: 0;
  font-size: 13px;
  color: var(--ink-500);
}

.login-btn {
  margin-top: 8px;
  height: 46px;
  font-size: 15px;
  font-weight: 500;
  letter-spacing: 2px;
  border-radius: 10px;
  box-shadow: 0 14px 28px -18px rgba(47, 107, 255, 0.95);
}

.login-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 20px;
  font-size: 12px;
  color: var(--ink-400);
}

@media (max-width: 960px) {
  .login-visual {
    display: none;
  }
  .login-panel {
    width: 100%;
  }
}
</style>
