<template>
  <div class="page">
    <div class="page-card facade-page">
      <div class="toolbar">
        <n-select
          v-model:value="buildingId"
          :options="buildingOptions"
          filterable
          remote
          clearable
          :loading="buildingLoading"
          placeholder="搜索并选择建筑物"
          style="width: 268px"
          @search="searchBuildings"
          @update:value="onBuildingChange"
        />
        <n-select
          v-model:value="filterKind"
          :options="KIND_OPTIONS"
          clearable
          placeholder="影像类别"
          style="width: 132px"
          @update:value="reload"
        />
        <n-select
          v-model:value="filterFacade"
          :options="FACADE_OPTIONS"
          clearable
          placeholder="立面方位"
          style="width: 126px"
          @update:value="reload"
        />
        <n-input
          v-model:value="keyword"
          clearable
          placeholder="文件名 / 备注"
          style="width: 180px"
          @keyup.enter="reload"
        />
        <n-button @click="reload">查询</n-button>
        <div class="grow" />
        <n-button v-if="can('facade:create')" type="primary" :disabled="!buildingId" @click="openUpload">
          <template #icon>
            <n-icon><CloudUploadOutline /></n-icon>
          </template>
          上传外景影像
        </n-button>
      </div>

      <div v-if="buildingId" class="stat-row">
        <div v-for="chip in statChips" :key="chip.label" class="stat-chip">
          <span>{{ chip.label }}</span>
          <span class="stat-value">{{ chip.value }}</span>
        </div>
      </div>

      <div class="grid-wrap">
        <n-empty
          v-if="!buildingId"
          class="empty"
          description="先在上方选择建筑物，再查看或上传外景影像"
        />
        <n-empty
          v-else-if="!loading && !rows.length"
          class="empty"
          description="暂无外景影像，点击右上角「上传外景影像」开始采集"
        />
        <div v-else class="media-grid" :class="{ 'is-loading': loading }">
          <div v-for="item in rows" :key="item.id" class="media-card" @click="openViewer(item)">
            <div class="thumb">
              <img :src="fileUrl(item.thumb_url)" :alt="item.file_name" loading="lazy" />
              <span class="badge-kind" :class="`kind-${item.kind}`">
                {{ item.kind_label || KIND_LABELS[item.kind] || item.kind }}
              </span>
              <span v-if="item.kind === 'panorama'" class="badge-pano">360°</span>
              <span v-if="item.is_primary" class="badge-cover">封面</span>
            </div>
            <div class="meta">
              <div class="meta-title" :title="item.file_name">{{ item.file_name }}</div>
              <div class="meta-sub">
                <n-tag size="tiny" :bordered="false">
                  {{ item.facade_label || FACADE_LABELS[item.facade] || item.facade }}
                </n-tag>
                <span v-if="item.floor_no !== null && item.floor_no !== undefined">{{ item.floor_no }}F</span>
                <span>{{ formatSize(item.file_size) }}</span>
              </div>
              <div class="meta-sub">
                <span>{{ formatTime(item.taken_at || item.created_at) }}</span>
                <span v-if="item.uploader_name">· {{ item.uploader_name }}</span>
              </div>
            </div>
            <div class="card-actions" @click.stop>
              <n-button size="tiny" quaternary @click="openViewer(item)">查看</n-button>
              <n-dropdown
                v-if="can('facade:update') || can('facade:delete')"
                trigger="click"
                :options="actionOptions(item)"
                @select="(key: string) => onAction(key, item)"
              >
                <n-button size="tiny" quaternary>更多</n-button>
              </n-dropdown>
            </div>
          </div>
        </div>
      </div>

      <div v-if="buildingId && total > 0" class="pager">
        <n-pagination
          v-model:page="page"
          :page-size="pageSize"
          :item-count="total"
          @update:page="loadList"
        />
      </div>
    </div>

    <!-- 上传 -->
    <n-modal
      v-model:show="showUpload"
      preset="card"
      title="上传外景影像"
      style="width: 680px; max-width: 94vw"
      :mask-closable="false"
    >
      <n-form label-placement="left" label-width="88">
        <n-form-item label="建筑物">
          <span class="text-strong">{{ currentBuildingLabel || '-' }}</span>
        </n-form-item>
        <n-grid :cols="2" :x-gap="14" :y-gap="4">
          <n-form-item-gi label="影像类别">
            <n-select v-model:value="uploadForm.kind" :options="KIND_OPTIONS" />
          </n-form-item-gi>
          <n-form-item-gi label="立面方位">
            <n-select v-model:value="uploadForm.facade" :options="FACADE_OPTIONS" />
          </n-form-item-gi>
          <n-form-item-gi label="楼层">
            <n-input-number
              v-model:value="uploadForm.floor_no"
              :precision="0"
              clearable
              placeholder="负数为地下"
              style="width: 100%"
            />
          </n-form-item-gi>
          <n-form-item-gi label="拍摄时间">
            <n-date-picker
              v-model:formatted-value="uploadForm.taken_at"
              type="datetime"
              value-format="yyyy-MM-dd'T'HH:mm:ss"
              clearable
              style="width: 100%"
            />
          </n-form-item-gi>
        </n-grid>
        <n-form-item label="备注">
          <n-input
            v-model:value="uploadForm.remark"
            type="textarea"
            :rows="2"
            placeholder="采集说明（可选）"
          />
        </n-form-item>
        <n-form-item label="文件">
          <n-upload
            v-model:file-list="uploadFiles"
            multiple
            :default-upload="false"
            :accept="acceptForKind"
          >
            <n-button>选择文件</n-button>
          </n-upload>
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="form-footer">
          <span class="hint">{{ acceptHint }}</span>
          <n-button @click="showUpload = false">取消</n-button>
          <n-button
            type="primary"
            :loading="uploading"
            :disabled="!uploadFiles.length"
            @click="submitUpload"
          >
            {{ uploading ? `上传中 ${uploadPercent}%` : '开始上传' }}
          </n-button>
        </div>
      </template>
    </n-modal>

    <!-- 查看 -->
    <n-modal
      v-model:show="showViewer"
      preset="card"
      :title="viewer?.file_name || '影像预览'"
      style="width: 940px; max-width: 96vw"
      :content-style="{ padding: '12px' }"
    >
      <div v-if="viewer" class="viewer">
        <div class="viewer-stage">
          <PanoramaViewer
            v-if="viewer.kind === 'panorama'"
            :src="fileUrl(viewer.url) || ''"
            class="viewer-fill"
          />
          <img
            v-else-if="viewer.kind === 'photo'"
            :src="fileUrl(viewer.url) || ''"
            class="viewer-img"
            :alt="viewer.file_name"
          />
          <div v-else class="viewer-model">
            <n-icon :size="44"><CubeOutline /></n-icon>
            <div class="text-strong">{{ viewer.file_name }}</div>
            <div class="hint">
              三维模型文件（{{ formatSize(viewer.file_size) }}），可下载后在建模软件中查看
            </div>
            <n-button tag="a" :href="fileUrl(viewer.url) || ''" target="_blank" type="primary" size="small">
              下载模型
            </n-button>
          </div>
        </div>
        <div class="viewer-meta">
          <n-tag size="small">{{ viewer.facade_label || FACADE_LABELS[viewer.facade] }}</n-tag>
          <span>楼层：{{ viewer.floor_no ?? '-' }}</span>
          <span>拍摄：{{ formatTime(viewer.taken_at) }}</span>
          <span v-if="viewer.width && viewer.height">{{ viewer.width }}×{{ viewer.height }}</span>
          <span>上传：{{ viewer.uploader_name || '-' }}</span>
          <span class="grow" />
          <n-button size="small" tag="a" :href="fileUrl(viewer.url) || ''" target="_blank" quaternary>
            打开原图
          </n-button>
        </div>
      </div>
    </n-modal>

    <!-- 编辑 -->
    <n-modal
      v-model:show="showEdit"
      preset="card"
      title="编辑影像信息"
      style="width: 520px; max-width: 94vw"
      :mask-closable="false"
    >
      <n-form label-placement="left" label-width="82">
        <n-form-item label="立面方位">
          <n-select v-model:value="editForm.facade" :options="FACADE_OPTIONS" />
        </n-form-item>
        <n-form-item label="楼层">
          <n-input-number v-model:value="editForm.floor_no" :precision="0" clearable style="width: 100%" />
        </n-form-item>
        <n-form-item label="拍摄时间">
          <n-date-picker
            v-model:formatted-value="editForm.taken_at"
            type="datetime"
            value-format="yyyy-MM-dd'T'HH:mm:ss"
            clearable
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item label="备注">
          <n-input v-model:value="editForm.remark" type="textarea" :rows="2" />
        </n-form-item>
        <n-form-item label="封面">
          <n-switch v-model:value="editForm.is_primary" />
          <span class="hint ml-8">作为该建筑物的外景封面</span>
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="form-footer">
          <n-button @click="showEdit = false">取消</n-button>
          <n-button type="primary" :loading="editSaving" @click="submitEdit">保存</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { DropdownOption, UploadFileInfo } from 'naive-ui'
import { CloudUploadOutline, CubeOutline } from '@vicons/ionicons5'
import { facadeApi, type FacadeItem, type FacadeStats } from '@/api'
import PanoramaViewer from '@/components/media/PanoramaViewer.vue'
import { useUserStore } from '@/store/user'
import { dialogConfirm, toastError, toastSuccess } from '@/utils/naive'
import { formatDateTime } from '@/utils/time'

const user = useUserStore()
const can = (code: string) => user.hasPerm(code)

const KIND_LABELS: Record<string, string> = {
  photo: '外景照片',
  panorama: '全景图',
  model: '三维模型',
}
const FACADE_LABELS: Record<string, string> = {
  east: '东立面',
  south: '南立面',
  west: '西立面',
  north: '北立面',
  top: '屋顶',
  other: '其他',
}

const KIND_OPTIONS = [
  { label: '外景照片', value: 'photo' },
  { label: '全景图（360°）', value: 'panorama' },
  { label: '三维模型', value: 'model' },
]
const FACADE_OPTIONS = [
  { label: '东立面', value: 'east' },
  { label: '南立面', value: 'south' },
  { label: '西立面', value: 'west' },
  { label: '北立面', value: 'north' },
  { label: '屋顶', value: 'top' },
  { label: '其他', value: 'other' },
]

// ---------------- 建筑选择 ----------------
const buildingId = ref<number | null>(null)
const buildingList = ref<{ id: number; code: string; name: string; address?: string | null }[]>([])
const buildingLoading = ref(false)
const buildingOptions = computed(() =>
  buildingList.value.map((b) => ({
    label: `${b.name}（${b.code}）`,
    value: b.id,
  })),
)
const currentBuildingLabel = computed(() => {
  const hit = buildingList.value.find((b) => b.id === buildingId.value)
  return hit ? `${hit.name}（${hit.code}）` : ''
})

async function searchBuildings(query: string) {
  buildingLoading.value = true
  try {
    buildingList.value = await facadeApi.buildings(query)
  } catch (e) {
    toastError((e as Error).message || '建筑物加载失败')
  } finally {
    buildingLoading.value = false
  }
}

// ---------------- 列表 ----------------
const rows = ref<FacadeItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 24
const loading = ref(false)
const keyword = ref('')
const filterKind = ref<string | null>(null)
const filterFacade = ref<string | null>(null)
const stats = ref<FacadeStats | null>(null)

const statChips = computed(() => {
  const s = stats.value
  return [
    { label: '总计', value: s?.total ?? 0 },
    ...FACADE_OPTIONS.map((o) => ({
      label: o.label.replace('立面', ''),
      value: s?.by_facade?.[o.value] ?? 0,
    })),
    { label: '全景', value: s?.by_kind?.panorama ?? 0 },
    { label: '模型', value: s?.by_kind?.model ?? 0 },
  ]
})

async function loadList() {
  if (!buildingId.value) {
    rows.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const res = await facadeApi.list({
      building_id: buildingId.value,
      page: page.value,
      page_size: pageSize,
      kind: filterKind.value || undefined,
      facade: filterFacade.value || undefined,
      keyword: keyword.value || undefined,
    })
    rows.value = res.items
    total.value = res.total
  } catch (e) {
    toastError((e as Error).message || '影像列表加载失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  if (!buildingId.value) {
    stats.value = null
    return
  }
  try {
    stats.value = await facadeApi.stats(buildingId.value)
  } catch {
    stats.value = null
  }
}

function reload() {
  page.value = 1
  loadList()
  loadStats()
}

function onBuildingChange() {
  reload()
}

// ---------------- 上传 ----------------
const showUpload = ref(false)
const uploading = ref(false)
const uploadPercent = ref(0)
const uploadFiles = ref<UploadFileInfo[]>([])
const uploadForm = reactive({
  kind: 'photo',
  facade: 'south',
  floor_no: null as number | null,
  taken_at: null as string | null,
  remark: '',
})

const acceptForKind = computed(() =>
  uploadForm.kind === 'model' ? '.glb,.gltf,.zip' : 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp',
)
const acceptHint = computed(() =>
  uploadForm.kind === 'model'
    ? '支持 .glb / .gltf / .zip，单个文件不超过 60MB'
    : '支持 JPG / PNG / WebP；全景图请上传等距柱状（2:1）全景图，单文件不超过 60MB',
)

function openUpload() {
  uploadForm.kind = 'photo'
  uploadForm.facade = 'south'
  uploadForm.floor_no = null
  uploadForm.taken_at = null
  uploadForm.remark = ''
  uploadFiles.value = []
  uploadPercent.value = 0
  showUpload.value = true
}

async function submitUpload() {
  if (!buildingId.value) return
  const files = uploadFiles.value
    .map((item) => item.file)
    .filter((file): file is File => Boolean(file))
  if (!files.length) {
    toastError('请先选择要上传的文件')
    return
  }
  uploading.value = true
  uploadPercent.value = 0
  try {
    const created = await facadeApi.upload(
      {
        building_id: buildingId.value,
        kind: uploadForm.kind,
        facade: uploadForm.facade,
        floor_no: uploadForm.floor_no,
        taken_at: uploadForm.taken_at,
        remark: uploadForm.remark || null,
        files,
      },
      (percent) => {
        uploadPercent.value = percent
      },
    )
    toastSuccess(`已上传 ${created.length} 个文件`)
    showUpload.value = false
    uploadFiles.value = []
    reload()
  } catch (e) {
    toastError((e as Error).message || '上传失败')
  } finally {
    uploading.value = false
  }
}

// ---------------- 查看 ----------------
const showViewer = ref(false)
const viewer = ref<FacadeItem | null>(null)

function openViewer(item: FacadeItem) {
  viewer.value = item
  showViewer.value = true
}

// ---------------- 编辑 / 删除 ----------------
const showEdit = ref(false)
const editSaving = ref(false)
const editItem = ref<FacadeItem | null>(null)
const editForm = reactive({
  facade: 'other',
  floor_no: null as number | null,
  taken_at: null as string | null,
  remark: '',
  is_primary: false,
})

function actionOptions(item: FacadeItem): DropdownOption[] {
  const options: DropdownOption[] = [
    { label: '打开原图', key: 'open' },
    { label: '下载', key: 'download' },
  ]
  if (can('facade:update')) {
    options.push({ label: '编辑信息', key: 'edit' })
    options.push({ label: item.is_primary ? '取消封面' : '设为封面', key: 'cover' })
  }
  if (can('facade:delete')) {
    options.push({ type: 'divider', key: 'd1' })
    options.push({ label: '删除', key: 'delete' })
  }
  return options
}

async function onAction(key: string, item: FacadeItem) {
  if (key === 'open') {
    window.open(fileUrl(item.url), '_blank')
    return
  }
  if (key === 'download') {
    const link = document.createElement('a')
    link.href = fileUrl(item.url)
    link.download = item.file_name
    link.target = '_blank'
    link.click()
    return
  }
  if (key === 'edit') {
    editItem.value = item
    editForm.facade = item.facade
    editForm.floor_no = item.floor_no ?? null
    editForm.taken_at = item.taken_at || null
    editForm.remark = item.remark || ''
    editForm.is_primary = item.is_primary
    showEdit.value = true
    return
  }
  if (key === 'cover') {
    try {
      await facadeApi.update(item.id, { is_primary: !item.is_primary })
      toastSuccess(item.is_primary ? '已取消封面' : '已设为封面')
      reload()
    } catch (e) {
      toastError((e as Error).message || '设置封面失败')
    }
    return
  }
  if (key === 'delete') {
    dialogConfirm(`确定删除「${item.file_name}」吗？文件将一并删除。`, async () => {
      try {
        await facadeApi.remove(item.id)
        toastSuccess('已删除')
        reload()
      } catch (e) {
        toastError((e as Error).message || '删除失败')
      }
    }, '删除影像')
  }
}

async function submitEdit() {
  const item = editItem.value
  if (!item) return
  editSaving.value = true
  try {
    await facadeApi.update(item.id, {
      facade: editForm.facade,
      floor_no: editForm.floor_no,
      taken_at: editForm.taken_at,
      remark: editForm.remark || null,
      is_primary: editForm.is_primary,
    })
    toastSuccess('已保存')
    showEdit.value = false
    reload()
  } catch (e) {
    toastError((e as Error).message || '保存失败')
  } finally {
    editSaving.value = false
  }
}

// ---------------- 工具 ----------------
function fileUrl(url?: string | null): string {
  return facadeApi.fileUrl(url)
}

function formatTime(value?: string | null): string {
  return formatDateTime(value, false)
}

function formatSize(bytes?: number | null): string {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

onMounted(async () => {
  await searchBuildings('')
  if (!buildingId.value && buildingList.value.length) {
    buildingId.value = buildingList.value[0].id
    reload()
  }
})
</script>

<style scoped>
.facade-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.grow {
  flex: 1;
}

.stat-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-chip {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid #eef2f7;
  border-radius: 6px;
  background: #f8fafc;
  font-size: 12px;
  color: #64748b;
}

.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
}

.grid-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.empty {
  padding: 60px 0;
}

.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  padding: 2px;
}

.media-grid.is-loading {
  opacity: 0.6;
  pointer-events: none;
}

.media-card {
  display: flex;
  flex-direction: column;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.15s;
}

.media-card:hover {
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.12);
  transform: translateY(-1px);
}

.thumb {
  position: relative;
  aspect-ratio: 4 / 3;
  background: #eef2f7;
}

.thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.badge-kind {
  position: absolute;
  left: 6px;
  top: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #fff;
  background: rgba(37, 99, 235, 0.88);
}

.badge-kind.kind-panorama {
  background: rgba(124, 58, 237, 0.9);
}

.badge-kind.kind-model {
  background: rgba(15, 118, 110, 0.9);
}

.badge-pano {
  position: absolute;
  right: 6px;
  top: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #fff;
  background: rgba(124, 58, 237, 0.9);
}

.badge-cover {
  position: absolute;
  right: 6px;
  bottom: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  color: #fff;
  background: rgba(234, 88, 12, 0.9);
}

.meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px 2px;
}

.meta-title {
  font-size: 13px;
  color: #1f2d3d;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-sub {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #8492a6;
  overflow: hidden;
  white-space: nowrap;
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  padding: 0 6px 4px;
}

.pager {
  display: flex;
  justify-content: flex-end;
}

.viewer {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.viewer-stage {
  height: 58vh;
  min-height: 300px;
  background: #0b0f16;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.viewer-fill {
  width: 100%;
  height: 100%;
}

.viewer-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.viewer-model {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #e2e8f0;
  padding: 24px;
  text-align: center;
}

.viewer-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #64748b;
}

.form-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.hint {
  font-size: 12px;
  color: #8492a6;
}

.ml-8 {
  margin-left: 8px;
}

.text-strong {
  color: #1f2d3d;
  font-weight: 500;
}
</style>
