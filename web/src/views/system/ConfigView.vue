<template>
  <div class="page">
    <div class="page-card config-card">
      <div class="toolbar">
        <div class="section-title">系统参数</div>
        <span class="config-hint">修改后立即生效</span>
      </div>

      <div class="config-body">
        <n-spin :show="loading">
          <n-tabs v-model:value="activeGroup" type="line" animated>
            <n-tab-pane v-for="g in groups" :key="g.group" :name="g.group" :tab="g.label">
              <p v-if="GROUP_HINTS[g.group]" class="group-hint">{{ GROUP_HINTS[g.group] }}</p>
              <n-form label-placement="left" label-width="150" class="config-form">
                <n-form-item v-for="item in g.items" :key="item.key" :label="item.label || item.key">
                  <div class="config-row">
                    <div class="config-control">
                      <n-switch
                        v-if="item.value_type === 'boolean'"
                        :value="values[item.key] === 'true'"
                        :disabled="!can('system:config')"
                        @update:value="(v: boolean) => (values[item.key] = v ? 'true' : 'false')"
                      />
                      <n-input-number
                        v-else-if="item.value_type === 'number'"
                        :value="numberValue(item.key)"
                        :disabled="!can('system:config')"
                        :precision="undefined"
                        @update:value="(v: number | null) => (values[item.key] = v == null ? '' : String(v))"
                      />
                      <n-input
                        v-else
                        v-model:value="values[item.key]"
                        :disabled="!can('system:config')"
                        :placeholder="item.label || item.key"
                      />
                    </div>
                    <div class="config-meta">
                      <span v-if="item.description" class="config-desc">{{ item.description }}</span>
                      <span class="config-key">{{ item.key }}</span>
                    </div>
                  </div>
                </n-form-item>
                <n-empty v-if="!g.items.length" description="暂无参数" size="small" />
              </n-form>
            </n-tab-pane>
          </n-tabs>
        </n-spin>
      </div>

      <div v-if="can('system:config')" class="save-bar">
        <n-button @click="load">重置</n-button>
        <n-button type="primary" :loading="saving" @click="save">保存当前分组</n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { systemApi, type ConfigItem } from '@/api'
import { useUserStore } from '@/store/user'
import { toastError, toastSuccess } from '@/utils/naive'

const store = useUserStore()
const can = (code: string) => store.hasPerm(code)

const GROUP_LABELS: Record<string, string> = {
  general: '基础设置',
  map: '地图设置',
  compare: '比对设置',
  collect: '采集设置',
}

const GROUP_HINTS: Record<string, string> = {
  general: '系统名称等基础信息，保存后全站生效。',
  map: '中心点与缩放级别按 WGS84/CGCS2000 填写，地图显示时会自动适配底图坐标系。',
  compare: '经纬度比对的默认超差阈值（米），可按项目精度要求调整。',
  collect: '采集入库时的默认行为设置。',
}

const loading = ref(false)
const saving = ref(false)
const configs = ref<ConfigItem[]>([])
const values = reactive<Record<string, string>>({})
const activeGroup = ref('')

const groups = computed(() => {
  const order = ['general', 'map', 'compare', 'collect']
  const map = new Map<string, ConfigItem[]>()
  configs.value.forEach((c) => {
    const list = map.get(c.group) ?? []
    list.push(c)
    map.set(c.group, list)
  })
  const keys = Array.from(map.keys()).sort((a, b) => {
    const ia = order.indexOf(a)
    const ib = order.indexOf(b)
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  })
  return keys.map((group) => ({
    group,
    label: GROUP_LABELS[group] ?? group,
    items: map.get(group) ?? [],
  }))
})

function numberValue(key: string): number | null {
  const raw = values[key]
  if (raw === undefined || raw === '') return null
  const n = Number(raw)
  return Number.isNaN(n) ? null : n
}

async function load() {
  loading.value = true
  try {
    configs.value = await systemApi.configs()
    Object.keys(values).forEach((k) => delete values[k])
    configs.value.forEach((c) => {
      values[c.key] = c.value ?? ''
    })
    if (!groups.value.some((g) => g.group === activeGroup.value)) {
      activeGroup.value = groups.value[0]?.group ?? ''
    }
  } catch (e) {
    toastError((e as Error).message || '加载系统参数失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  const current = groups.value.find((g) => g.group === activeGroup.value)
  if (!current) return
  const payload = current.items.map((item) => ({
    key: item.key,
    value: values[item.key] ?? '',
    label: item.label,
    group: item.group,
    value_type: item.value_type,
  }))
  saving.value = true
  try {
    await systemApi.saveConfigs(payload)
    toastSuccess('参数已保存')
    await store.loadBootstrap()
    await load()
  } catch (e) {
    toastError((e as Error).message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* 卡片内固定头部 + 可滚动内容区 + 底部操作栏，避免内容超出卡片 */
.config-card {
  overflow: hidden;
}
.config-hint {
  color: #98a1b0;
  font-size: 12.5px;
}
.config-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.config-body :deep(.n-spin-container),
.config-body :deep(.n-spin-content) {
  height: 100%;
}
.config-form {
  max-width: 940px;
  padding: 2px 0 6px;
}
.group-hint {
  max-width: 940px;
  margin: 4px 0 14px;
  color: #98a1b0;
  font-size: 12.5px;
  line-height: 1.6;
}
.config-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  width: 100%;
}
.config-control {
  flex: 0 0 320px;
  display: flex;
  align-items: center;
}
.config-control :deep(.n-input),
.config-control :deep(.n-input-number) {
  width: 100%;
}
.config-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 8px;
}
.config-desc {
  color: #8f98a8;
  font-size: 12px;
  line-height: 1.55;
}
.config-key {
  color: #c6ccd6;
  font-size: 11.5px;
  font-family: Consolas, Monaco, monospace;
}
.save-bar {
  flex: none;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}
@media (max-width: 960px) {
  .config-row {
    flex-direction: column;
    gap: 6px;
  }
  .config-control {
    flex: 1 1 100%;
    width: 100%;
  }
  .config-meta {
    padding-top: 0;
  }
}
</style>
