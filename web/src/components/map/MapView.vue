<template>
  <div class="map-view-wrap">
    <div ref="mapEl" class="map-view"></div>
    <Transition name="map-popup">
      <FeaturePopup v-if="popup" v-bind="popup" @close="closePopup" />
    </Transition>
    <div v-if="!hasBaseMap" class="map-tip">
      <span class="map-tip-title">底图服务未就绪</span>
      <span class="map-tip-desc">当前无法加载地图底图，请联系系统管理员</span>
    </div>
    <slot></slot>
  </div>
</template>

<script setup lang="ts">
/** 地图画布封装：内网自定义底图 + 矢量图层管理 + 绘制 + 顶点编辑。 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
// 运行时使用 iSpace（public/iSpace 下的本地构建），类型沿用 maptalks 的 d.ts（两者 API 一致）
import type * as Maptalks from 'maptalks'
import { ispace } from '@/utils/ispace'
import { mapTileConfig } from '@/utils/mapConfig'
import type { InfoModule } from '@/api'
import FeaturePopup from './FeaturePopup.vue'
import { coordHint, popupRows, type PopupData, type PopupPlacement } from './featurePopup'
import { toLonLatBbox, type MapViewport } from './viewport'

/**
 * Boolean 属性必须显式给默认值：Vue 对布尔 prop 做 casting，未传值时会被转成 false，
 * 之前 featurePopup 缺省会走到 `props.featurePopup === false` 这条“禁用弹窗”分支，
 * 导致所有地图要素点击都不弹属性卡。
 */
const props = withDefaults(
  defineProps<{
    center?: [number, number]
    zoom?: number
    maxZoom?: number
    onFeatureClick?: (featureId: number, moduleId: number) => void
    /** 视野停止变化后回调，采集图层按视野取数用（不传则不监听） */
    onViewChange?: (viewport: MapViewport) => void
    /** 模块字段定义（module_id → { 属性key: 中文字段名 }），用于弹窗展示可读字段名 */
    fieldLabels?: Record<number, Record<string, string>>
    /** 点击要素时是否弹出属性卡（默认 true） */
    featurePopup?: boolean
  }>(),
  {
    featurePopup: true,
    fieldLabels: () => ({}),
  },
)

/** 底图瓦片是否已配置（未配置时给出界面提示，地图本身仍可用） */
const hasBaseMap = !!mapTileConfig.url

const mapEl = ref<HTMLDivElement>()
let map: Maptalks.Map | null = null
const moduleLayers = new Map<number, Maptalks.VectorLayer>()
let drawTool: Maptalks.DrawTool | null = null
let drawResolve: ((value: Record<string, unknown> | null) => void) | null = null
let editCleanups: Array<() => void> = []

// ---------------- 底图 ----------------
/** 默认地图中心（WGS84/CGCS2000）：系统参数未配置时使用。 */
const DEFAULT_CENTER: [number, number] = [116.397428, 39.90923]

/**
 * 底图完全来自前端运行时配置（public/js/config.js 的 MAP_TILE_*），
 * 内网/离线部署不依赖天地图等公网服务。
 */
function makeTileLayer(): Maptalks.TileLayer {
  const useGl = mapTileConfig.renderer === 'gl'
  return new ispace.TileLayer('internal-base', {
    urlTemplate: mapTileConfig.url,
    subdomains: mapTileConfig.subdomains.length ? mapTileConfig.subdomains : [''],
    minZoom: mapTileConfig.minZoom,
    maxAvailableZoom: mapTileConfig.maxZoom,
    // gl：走 WebGL 贴图，支持倾斜/旋转视角（瓦片服务需返回 CORS 头）
    // canvas：2D 绘制，无 CORS 要求，但地图倾斜后瓦片不参与投影会消失
    renderer: mapTileConfig.renderer,
    crossOrigin: useGl ? 'anonymous' : undefined,
  })
}

function initMap(): void {
  if (!mapEl.value || map) return
  map = new ispace.Map(mapEl.value, {
    // 中心点直接使用系统参数中的经纬度，不做坐标系偏移
    center: props.center || DEFAULT_CENTER,
    zoom: props.zoom || 15,
    minZoom: mapTileConfig.minZoom,
    maxZoom: props.maxZoom || mapTileConfig.maxZoom,
    attribution: false,
    zoomControl: false,
    scaleControl: false,
  })
  map.addControl(
    new ispace.control.Zoom({
      position: 'bottom-right',
      slider: true,
      zoomLevel: true,
    } as ConstructorParameters<typeof ispace.control.Zoom>[0]),
  )
  map.addControl(new ispace.control.Scale({ position: 'bottom-left' }))
  map.setBaseLayer(
    mapTileConfig.url
      ? makeTileLayer()
      : new ispace.TileLayer('base', { urlTemplate: 'about:blank' }),
  )
  if (mapTileConfig.attribution) {
    // 放左下角与比例尺同侧，避免与右下角的缩放条重叠
    map.addControl(
      new ispace.control.Attribution({ position: 'bottom-left', content: mapTileConfig.attribution }),
    )
  }
  map.on('click', () => {
    // 同一次点击在要素上也会冒泡到地图，用时间戳避免刚弹出的属性卡被立刻关掉
    if (Date.now() - lastFeatureClickAt < 200) return
    closePopup()
  })
  // 视角变化时把属性卡贴回要素位置（可见性由 syncPopupPosition 判断）
  map.on('moving', syncPopupPosition)
  map.on('zooming', syncPopupPosition)
  map.on('moveend', syncPopupPosition)
  map.on('zoomend', syncPopupPosition)
  // 视野稳定后通知业务层按新范围取数（平移/缩放结束后各触发一次，拖拽过程中不打扰）
  map.on('moveend', notifyViewChange)
  map.on('zoomend', notifyViewChange)
  // 首帧布局稳定后再校正一次容器尺寸
  requestAnimationFrame(() => map?.checkSize(true))
}

/**
 * 当前视野（经纬度包围盒 + 缩放级别）；地图未初始化时返回 null。
 *
 * 包围盒按 toLonLatBbox 归一化成「度」，与后端 ST_MakeEnvelope(..., 4490) 的入参一致。
 */
function getViewport(): MapViewport | null {
  if (!map) return null
  const ext = map.getExtent()
  const { xmin, ymin, xmax, ymax } = ext ?? {}
  if (xmin == null || ymin == null || xmax == null || ymax == null) return null
  const zoom = map.getZoom()
  return {
    bbox: toLonLatBbox(xmin, ymin, xmax, ymax),
    zoom: typeof zoom === 'number' ? zoom : props.zoom ?? 15,
  }
}

function notifyViewChange(): void {
  const view = getViewport()
  if (view) props.onViewChange?.(view)
}

// ---------------- 要素属性弹窗 ----------------
const GEOM_LABELS: Record<string, string> = { point: '点要素', line: '线要素', polygon: '面要素' }
const STATUS_LABELS: Record<string, string> = { draft: '草稿', verified: '已核实' }
/** 比对图层的点位/连线类型 */
const KIND_LABELS: Record<string, string> = {
  declared: '申报点位',
  measured: '实测点位',
  measure: '偏差连线',
  point: '点位',
}

const popup = ref<PopupData | null>(null)
/** 最近一次要素点击时间，用于区分“点要素”与“点空白” */
let lastFeatureClickAt = 0

/** 当前高亮的要素（无要素 id 的通用图层为 null） */
let highlightedFeatureId: number | null = null
/** 高亮记录：保存被改写的几何与原符号，关闭弹窗时还原 */
let highlightItems: Array<{ geometry: Maptalks.Geometry; symbol: Record<string, unknown> }> = []

function geometriesOf(geometry: Maptalks.Geometry): Maptalks.Geometry[] {
  const children = (geometry as unknown as { getGeometries?: () => Maptalks.Geometry[] })
    .getGeometries?.()
  return children && children.length ? children : [geometry]
}

function readSymbol(geometry: Maptalks.Geometry): Record<string, unknown> {
  const symbol = (geometry as unknown as { getSymbol?: () => Record<string, unknown> }).getSymbol?.()
  return symbol ? { ...symbol } : {}
}

/** 高亮样式：沿用原符号做加粗/放大，避免改变要素本身的配色语义 */
function emphasizedSymbol(
  geometry: Maptalks.Geometry,
  symbol: Record<string, unknown>,
): Record<string, unknown> {
  const type = geometry.getType()
  if (type === 'Point' || type === 'MultiPoint') {
    const size = Math.max(Number(symbol.markerWidth) || 12, 12) + 6
    return { ...symbol, markerWidth: size, markerHeight: size, markerLineWidth: 3 }
  }
  const width = Number(symbol.lineWidth) || 2
  if (type === 'LineString' || type === 'MultiLineString') {
    return { ...symbol, lineWidth: width + 3 }
  }
  return {
    ...symbol,
    lineWidth: width + 1.5,
    polygonOpacity: Math.max(Number(symbol.polygonOpacity) || 0.35, 0.5),
  }
}

function clearHighlight(): void {
  highlightItems.forEach(({ geometry, symbol }) => geometry.setSymbol(symbol))
  highlightItems = []
  highlightedFeatureId = null
}

function highlightGeometries(
  geometries: Maptalks.Geometry[],
  featureId: number | null = null,
): void {
  clearHighlight()
  highlightedFeatureId = featureId
  for (const geometry of geometries) {
    for (const target of geometriesOf(geometry)) {
      const symbol = readSymbol(target)
      if (!Object.keys(symbol).length) continue
      highlightItems.push({ geometry: target, symbol })
      target.setSymbol(emphasizedSymbol(target, symbol))
    }
  }
}

/** 弹窗默认宽度（与 FeaturePopup 保持一致），用于边缘避让 */
const POPUP_WIDTH = 292
const POPUP_GAP = 12

interface PopupOptions {
  containerPoint?: { x: number; y: number }
  lng?: number
  lat?: number
  accent?: string
  title: string
  subtitle?: string | null
  badges?: Array<string | undefined>
  properties?: Record<string, unknown> | null
  labels?: Record<string, string> | null
}

/** 依据锚点像素位置计算弹窗落点与弹出方向（含边缘避让） */
function anchorPlacement(
  point: { x: number; y: number },
  box: HTMLElement,
): { x: number; y: number; placement: PopupPlacement } {
  const width = box.clientWidth
  const height = box.clientHeight
  // 水平方向按弹窗宽度做边缘避让，避免贴边被裁掉
  const half = POPUP_WIDTH / 2
  const minX = Math.min(half + POPUP_GAP, width / 2)
  const maxX = Math.max(width - half - POPUP_GAP, width / 2)
  return {
    x: Math.min(Math.max(point.x, minX), maxX),
    y: Math.min(Math.max(point.y, POPUP_GAP), height - POPUP_GAP),
    // 锚点靠近顶部时改为向下弹出
    placement: point.y < 220 ? 'bottom' : 'top',
  }
}

/** 弹窗锚点的地图坐标：视角变化后据此重新定位 */
let popupAnchor: { lng: number; lat: number } | null = null

/** 在点击位置弹出要素属性卡；无内容可展示时返回 false */
function openPopup(options: PopupOptions): boolean {
  if (props.featurePopup === false) return false
  const box = mapEl.value
  const point = options.containerPoint
  if (!box || !point) return false
  const rows = popupRows(options.properties, options.labels)
  const subtitle = options.subtitle?.trim() || undefined
  if (!rows.length && !subtitle) return false
  if (!box.clientWidth || !box.clientHeight) return false

  popupAnchor =
    typeof options.lng === 'number' && typeof options.lat === 'number'
      ? { lng: options.lng, lat: options.lat }
      : null

  popup.value = {
    ...anchorPlacement(point, box),
    accent: options.accent || '#2d6cdf',
    title: options.title,
    subtitle,
    badges: (options.badges ?? []).filter((badge): badge is string => !!badge),
    rows,
    hint: coordHint(options.lng, options.lat),
  }
  return true
}

/** 平移/缩放结束后把弹窗贴回要素位置；锚点跑出可视区则收起 */
function syncPopupPosition(): void {
  if (!popup.value || !popupAnchor || !map || !mapEl.value) return
  const box = mapEl.value
  const point = map.coordinateToContainerPoint(
    new ispace.Coordinate(popupAnchor.lng, popupAnchor.lat),
  )
  if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) {
    closePopup()
    return
  }
  const margin = 80
  if (
    point.x < -margin ||
    point.y < -margin ||
    point.x > box.clientWidth + margin ||
    point.y > box.clientHeight + margin
  ) {
    closePopup()
    return
  }
  popup.value = { ...popup.value, ...anchorPlacement(point, box) }
}

function closePopup(): void {
  popup.value = null
  popupAnchor = null
  clearHighlight()
}

/** Esc 关闭属性卡；绘制/编辑中的 Esc 由各自工具处理，这里只在有弹窗时响应 */
function handlePopupEscape(event: KeyboardEvent): void {
  if (event.key !== 'Escape' || !popup.value) return
  closePopup()
}

/** 要素点击统一入口：高亮 + 属性卡，业务回调由调用方补充 */
function showFeaturePopup(
  event: unknown,
  geometry: Maptalks.Geometry,
  options: Omit<PopupOptions, 'containerPoint' | 'lng' | 'lat'>,
  featureId: number | null = null,
): void {
  // 编辑状态下点击用于插入顶点，不弹窗
  if (editingGeometry === geometry) return
  lastFeatureClickAt = Date.now()
  const param = event as {
    containerPoint?: { x: number; y: number }
    coordinate?: { x: number; y: number }
  }
  const coordinate = param?.coordinate
  // 个别引擎版本不返回 containerPoint，用点击坐标反算屏幕位置兜底
  const containerPoint =
    param?.containerPoint ??
    (coordinate && map
      ? map.coordinateToContainerPoint(new ispace.Coordinate(coordinate.x, coordinate.y))
      : undefined)
  const shown = openPopup({
    ...options,
    containerPoint,
    lng: coordinate?.x,
    lat: coordinate?.y,
  })
  if (shown) highlightGeometries([geometry], featureId)
  else clearHighlight()
}

function statusBadge(status: unknown): string | undefined {
  if (typeof status !== 'string' || !status) return undefined
  return STATUS_LABELS[status] ?? status
}

// ---------------- 图层 ----------------
function getModuleLayer(module: Pick<InfoModule, 'id'>): Maptalks.VectorLayer {
  if (!map) throw new Error('map not ready')
  let layer = moduleLayers.get(module.id)
  if (!layer) {
    layer = new ispace.VectorLayer(`module-${module.id}`, { enableSimplify: false })
    layer.addTo(map)
    moduleLayers.set(module.id, layer)
  }
  return layer
}

function symbolFor(geomType: string, color: string): Record<string, unknown> {
  if (geomType === 'point') {
    return {
      markerType: 'ellipse',
      markerFill: color,
      markerFillOpacity: 0.85,
      markerWidth: 12,
      markerHeight: 12,
      markerLineWidth: 2,
      markerLineColor: '#ffffff',
    }
  }
  if (geomType === 'line') {
    return { lineColor: color, lineWidth: 3 }
  }
  return { lineColor: color, lineWidth: 2, polygonFill: color, polygonOpacity: 0.35 }
}

/** 要素 id → 几何对象，供顶点编辑快速定位（不依赖 iSpace config 的读取语义） */
const featureGeometries = new Map<number, Maptalks.Geometry>()

function clearModuleLayers(): void {
  moduleLayers.forEach((l) => {
    l.clear()
  })
  featureGeometries.clear()
}

function removeModuleLayer(moduleId: number): void {
  const layer = moduleLayers.get(moduleId)
  if (layer) {
    layer.remove()
    moduleLayers.delete(moduleId)
  }
}

/** 按模块分组渲染要素。groups = [{module_id, module_name, geom_type, color, features:[...]}] */
function renderGroups(groups: unknown[]): void {
  clearModuleLayers()
  for (const group of groups as Array<{
    module_id: number
    module_name?: string | null
    geom_type: string
    color: string
    features: Array<{ id: number; geometry: Record<string, unknown>; properties: Record<string, unknown> }>
  }>) {
    const layer = getModuleLayer({ id: group.module_id })
    const symbol = symbolFor(group.geom_type, group.color)
    for (const f of group.features) {
      if (!f.geometry) continue
      // 业务坐标原样渲染，不做坐标系偏移
      const geo = ispace.GeoJSON.toGeometry(f.geometry) as
        | Maptalks.Geometry
        | Maptalks.Geometry[]
      const geometries = Array.isArray(geo) ? geo : [geo]
      for (const g of geometries) {
        g.setSymbol(symbol)
        g.config('featureId', f.id)
        featureGeometries.set(f.id, g)
        // 未进入形状编辑前禁止拖动，避免误移图形；拖动能力由顶点编辑开启
        g.config('draggable', false)
        // 点击弹出要素属性卡（自定义弹窗），同时通知业务层选中/定位
        const onClick = (event: unknown) => {
          showFeaturePopup(
            event,
            g,
            {
              accent: group.color,
              title: (f.properties?.name as string) || (f.properties?.code as string) || `要素 ${f.id}`,
              subtitle: group.module_name,
              badges: [GEOM_LABELS[group.geom_type], statusBadge(f.properties?.status)],
              properties: f.properties,
              labels: props.fieldLabels?.[group.module_id],
            },
            f.id,
          )
          if (editingGeometry !== g) props.onFeatureClick?.(f.id, group.module_id)
        }
        g.on('click', onClick)
        // 飞地（MultiPolygon）的点击事件来自子面片，需要一并绑定
        const children = (g as unknown as { getGeometries?: () => Maptalks.Geometry[] }).getGeometries?.()
        children?.forEach((child) => child.on('click', onClick))
        layer.addGeometry(g)
      }
    }
  }
  // 图层重建后原几何已销毁：按要素 id 找回被选中的要素并还原高亮，
  // 要素已不在当前图层里（如模块被隐藏）则收起弹窗
  const activeId = highlightedFeatureId
  // 通用图层（建筑物/比对）的高亮几何不随模块图层重建，保持原状
  if (activeId === null) return
  highlightItems = []
  const geometry = featureGeometries.get(activeId)
  if (geometry) highlightGeometries([geometry], activeId)
  else closePopup()
}

/** 渲染一套通用 GeoJSON（点/线/面，带颜色与标签），用于建筑物、比对页等。 */
function renderPlain(items: Array<{
  id: string
  geometry: Record<string, unknown>
  color?: string
  label?: string
  kind?: string
  clickId?: number
  /** 弹窗标题/副标题与属性（不传则不弹属性卡） */
  popupTitle?: string
  popupSubtitle?: string
  popupBadges?: string[]
  properties?: Record<string, unknown> | null
  labels?: Record<string, string> | null
  onClick?: (id: string) => void
}>, layerName = 'plain'): void {
  if (!map) return
  let layer = map.getLayer(layerName) as Maptalks.VectorLayer | null
  if (layer) layer.remove()
  layer = new ispace.VectorLayer(layerName)
  layer.addTo(map)
  for (const item of items) {
    const geo = ispace.GeoJSON.toGeometry(item.geometry) as
      | Maptalks.Geometry
      | Maptalks.Geometry[]
    const geometries = Array.isArray(geo) ? geo : [geo]
    for (const g of geometries) {
      const isPoint = item.geometry?.type === 'Point'
      const color = item.color || '#d03050'
      g.setSymbol(
        isPoint
          ? {
              markerType: 'ellipse',
              markerFill: color,
              markerFillOpacity: 0.9,
              markerWidth: item.kind === 'measured' ? 14 : 11,
              markerHeight: item.kind === 'measured' ? 14 : 11,
              markerLineWidth: 2,
              markerLineColor: '#fff',
            }
          : item.kind === 'measure'
            ? { lineColor: color, lineWidth: 2, lineDasharray: [6, 4] }
            : { lineColor: color, lineWidth: 2, polygonFill: color, polygonOpacity: 0.3 },
      )
      g.on('click', (event: unknown) => {
        showFeaturePopup(event, g, {
          accent: color,
          title: item.popupTitle || item.label || '要素信息',
          subtitle: item.popupSubtitle ?? KIND_LABELS[item.kind ?? ''],
          badges: item.popupBadges,
          properties: item.properties,
          labels: item.labels,
        })
        item.onClick?.(item.id)
      })
      layer!.addGeometry(g)
    }
  }
}

function clearLayer(layerName: string): void {
  map?.getLayer(layerName)?.remove()
}

// ---------------- 面状几何（挖洞 / 飞地） ----------------
type LngLat = [number, number]
type Ring = LngLat[]
/** 一个面片：第 0 个环是外环，其后是洞（内环） */
type PolygonParts = Ring[][]

const CLOSE_EPS = 1e-12

/** 去掉 Feature 外壳，只要裸几何 */
function unwrapGeometry(gj: unknown): Record<string, unknown> | null {
  const obj = gj as Record<string, unknown> | null
  if (!obj || typeof obj !== 'object') return null
  if (obj.type === 'Feature') {
    return (obj.geometry as Record<string, unknown>) ?? null
  }
  return obj
}

function samePoint(a: LngLat, b: LngLat): boolean {
  return Math.abs(a[0] - b[0]) < CLOSE_EPS && Math.abs(a[1] - b[1]) < CLOSE_EPS
}

function closeRing(ring: Ring): Ring {
  if (ring.length < 3) return ring
  if (samePoint(ring[0], ring[ring.length - 1])) return ring
  return [...ring, [ring[0][0], ring[0][1]]]
}

function cloneParts(parts: PolygonParts): PolygonParts {
  return parts.map((polygon) => polygon.map((ring) => ring.map((p) => [p[0], p[1]] as LngLat)))
}

/** GeoJSON（Polygon / MultiPolygon）-> 面片数组 */
function geometryParts(gj: unknown): PolygonParts {
  const geo = unwrapGeometry(gj)
  if (!geo) return []
  const coords = geo.coordinates
  if (!Array.isArray(coords)) return []
  if (geo.type === 'Polygon') {
    return [(coords as unknown[]).map((r) => (r as unknown[]).map((p) => toLngLat(p)))]
  }
  if (geo.type === 'MultiPolygon') {
    return (coords as unknown[]).map((polygon) =>
      (polygon as unknown[]).map((r) => (r as unknown[]).map((p) => toLngLat(p))),
    )
  }
  return []
}

/** 面片数组 -> GeoJSON（1 个面片用 Polygon，多个用 MultiPolygon） */
function partsToGeojson(parts: PolygonParts): Record<string, unknown> {
  const polygons = parts
    .filter((polygon) => polygon.length && polygon[0].length >= 3)
    .map((polygon) => polygon.map((ring) => closeRing(ring)))
  if (!polygons.length) return { type: 'Polygon', coordinates: [] }
  if (polygons.length === 1) return { type: 'Polygon', coordinates: polygons[0] }
  return { type: 'MultiPolygon', coordinates: polygons }
}

/** 环内点：射线法 */
function pointInRing(pt: LngLat, ring: Ring): boolean {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]
    const [xj, yj] = ring[j]
    if (yi > pt[1] !== yj > pt[1] && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}

function ringCenter(ring: Ring): LngLat {
  const pts = ring.length > 1 && samePoint(ring[0], ring[ring.length - 1]) ? ring.slice(0, -1) : ring
  const n = Math.max(pts.length, 1)
  return [
    pts.reduce((s, p) => s + p[0], 0) / n,
    pts.reduce((s, p) => s + p[1], 0) / n,
  ]
}

/** 校验面片结构（洞在外环内、洞不嵌套、飞地面片不互相包含），返回错误提示 */
function validateParts(parts: PolygonParts): string | null {
  const polys = parts.filter((polygon) => polygon.length)
  if (!polys.length) return '至少需要一个面片'
  for (const polygon of polys) {
    if (polygon[0].length < 4) return '面的外环至少需要 3 个顶点'
    for (let i = 1; i < polygon.length; i++) {
      const hole = polygon[i]
      if (hole.length < 4) return '洞至少需要 3 个顶点'
      if (!hole.every((pt) => pointInRing(pt, polygon[0]))) return '洞必须位于外环内部'
      for (let j = 1; j < polygon.length; j++) {
        if (i === j) continue
        if (hole.every((pt) => pointInRing(pt, polygon[j]))) return '洞不能嵌套在其它洞内'
      }
    }
  }
  for (let i = 0; i < polys.length; i++) {
    for (let j = 0; j < polys.length; j++) {
      if (i === j) continue
      if (polys[i][0].every((pt) => pointInRing(pt, polys[j][0]))) return '飞地面片不能相互包含'
    }
  }
  return null
}

/** 把一个新环并入为洞，环必须完整落在某个面片内且不落在已有洞中 */
function mergeHole(parts: PolygonParts, ring: Ring): PolygonParts | null {
  const shell = closeRing(ring)
  if (shell.length < 4) return null
  const center = ringCenter(shell)
  let hit = -1
  for (let i = 0; i < parts.length; i++) {
    const outer = parts[i][0]
    if (!outer || outer.length < 4) continue
    if (parts[i].slice(1).some((hole) => pointInRing(center, hole))) return null
    if (hit < 0 && shell.every((pt) => pointInRing(pt, outer))) hit = i
  }
  if (hit < 0) return null
  return parts.map((polygon, i) => (i === hit ? [...polygon, shell] : polygon))
}

/** 把一个新环并入为独立面片（飞地） */
function mergePart(parts: PolygonParts, ring: Ring): PolygonParts | null {
  const shell = closeRing(ring)
  if (shell.length < 4) return null
  const center = ringCenter(shell)
  // 落在已有面片内部的环应作为洞处理，避免产生嵌套面片
  if (parts.some((polygon) => polygon[0] && pointInRing(center, polygon[0]))) return null
  return [...parts, [shell]]
}

/** 去掉最后一个洞；若最后一个面片没有洞则去掉该面片 */
function dropLastRing(parts: PolygonParts): PolygonParts | null {
  if (!parts.length) return null
  const next = cloneParts(parts)
  const last = next[next.length - 1]
  if (last.length > 1) {
    last.pop()
    return next
  }
  if (next.length > 1) {
    next.pop()
    return next
  }
  return null
}

// ---------------- 绘制 ----------------
const MODE_MAP: Record<string, string> = { point: 'Point', line: 'LineString', polygon: 'Polygon' }

/** 用 iSpace 绘制工具画一个几何，返回裸 GeoJSON 几何；取消时为 null */
function drawWithTool(
  mode: string,
  symbol: Record<string, unknown>,
): Promise<Record<string, unknown> | null> {
  if (!map) return Promise.reject(new Error('map not ready'))
  cancelDraw()
  const tool = new ispace.DrawTool({
    mode,
    symbol,
    // 绘制期间屏蔽几何事件，避免点到已有要素触发选中
    blockGeometryEvents: true,
  } as ConstructorParameters<typeof ispace.DrawTool>[0]).addTo(map) as unknown as Maptalks.DrawTool
  tool.disable()
  drawTool = tool
  return new Promise((resolve) => {
    let settled = false
    function finish(value: Record<string, unknown> | null): void {
      if (settled) return
      settled = true
      document.removeEventListener('keydown', esc)
      drawResolve = null
      cleanupDraw()
      resolve(value)
    }
    function esc(e: KeyboardEvent): void {
      if (e.key === 'Escape') finish(null)
    }
    drawResolve = finish
    tool.on('drawend', (param: unknown) => {
      const geometry = (param as { geometry?: Maptalks.Geometry }).geometry
      finish(geometry ? unwrapGeometry(geometry.toGeoJSON()) : null)
    })
    document.addEventListener('keydown', esc)
    editCleanups.push(() => document.removeEventListener('keydown', esc))
    tool.enable()
  })
}

async function startDraw(geomType: string, color: string): Promise<Record<string, unknown> | null> {
  // 绘制结果直接回调给业务层，不做坐标系转换
  return drawWithTool(MODE_MAP[geomType] || 'Point', symbolFor(geomType, color))
}

/** 画一个环（用于挖洞 / 添加飞地），返回环坐标 */
async function drawRing(color: string): Promise<Ring | null> {
  const gj = await drawWithTool('Polygon', {
    lineColor: color,
    lineWidth: 2,
    lineDasharray: [6, 4],
    polygonFill: color,
    polygonOpacity: 0.12,
  })
  if (!gj) return null
  const ring = geometryParts(gj)[0]?.[0]
  return ring && ring.length >= 4 ? ring : null
}

/** 在给定面要素上挖洞，返回新的 GeoJSON；取消返回 null */
async function startDrawHole(
  base: Record<string, unknown>,
  color: string,
): Promise<Record<string, unknown> | null> {
  const ring = await drawRing(color)
  if (!ring) return null
  const parts = geometryParts(base)
  const merged = mergeHole(parts, ring)
  if (!merged) throw new Error('挖洞失败：洞需完整绘制在某个面片内部，且不能与已有洞重叠')
  const error = validateParts(merged)
  if (error) throw new Error(`挖洞失败：${error}`)
  const gj = partsToGeojson(merged)
  previewGeometryRaw(gj, color)
  return gj
}

/** 在给定面要素上添加一个飞地面片，返回新的 GeoJSON；取消返回 null */
async function startDrawPart(
  base: Record<string, unknown>,
  color: string,
): Promise<Record<string, unknown> | null> {
  const ring = await drawRing(color)
  if (!ring) return null
  const parts = geometryParts(base)
  const merged = mergePart(parts, ring)
  if (!merged) throw new Error('添加飞地失败：新面片不能落在已有面片内部（面内区域请用「挖洞」）')
  const error = validateParts(merged)
  if (error) throw new Error(`添加飞地失败：${error}`)
  const gj = partsToGeojson(merged)
  previewGeometryRaw(gj, color)
  return gj
}

/** 撤销最后一个洞（没有洞时撤销最后一个面片） */
function undoLastRing(
  base: Record<string, unknown>,
  color?: string,
): Record<string, unknown> | null {
  const next = dropLastRing(geometryParts(base))
  if (!next) return null
  const gj = partsToGeojson(next)
  previewGeometryRaw(gj, color)
  return gj
}

function cleanupDraw(): void {
  drawTool?.remove()
  drawTool = null
}

function cancelDraw(): void {
  const fn = drawResolve
  drawResolve = null
  fn?.(null)
  cleanupDraw()
}

// ---------------- 新建要素的预览图层 ----------------
let previewLayer: Maptalks.VectorLayer | null = null
let previewColor = '#2d6cdf'

/** 对外接口：预览尚未保存的面要素（坐标原样绘制） */
function previewGeometry(gj: Record<string, unknown> | null, color?: string): void {
  previewGeometryRaw(gj, color)
}

/** 内部实现：预览面要素（含洞与飞地） */
function previewGeometryRaw(gj: Record<string, unknown> | null, color?: string): void {
  if (color) previewColor = color
  if (!map) return
  if (!previewLayer) {
    previewLayer = new ispace.VectorLayer('collect-preview', { zIndex: 250 })
    previewLayer.addTo(map)
  }
  previewLayer.clear()
  if (!gj) return
  const coords = (gj as { coordinates?: unknown }).coordinates
  if (!Array.isArray(coords) || !coords.length) return
  const geo = ispace.GeoJSON.toGeometry(gj) as Maptalks.Geometry | Maptalks.Geometry[]
  const geometries = Array.isArray(geo) ? geo : [geo]
  for (const g of geometries) {
    g.setSymbol({
      lineColor: previewColor,
      lineWidth: 2,
      polygonFill: previewColor,
      polygonOpacity: 0.3,
    })
    g.config('draggable', false)
    previewLayer.addGeometry(g)
  }
}

function clearPreview(): void {
  previewLayer?.clear()
  previewLayer?.remove()
  previewLayer = null
}

// ---------------- 顶点编辑 ----------------
let vertexMarkers: Maptalks.Marker[] = []
let editLayer: Maptalks.VectorLayer | null = null
/** 编辑层中的几何副本（原地编辑会污染要素图层，故用副本） */
let editingGeometry: Maptalks.Geometry | null = null
/** 被编辑要素的原始几何，编辑期间隐藏 */
let editingSource: Maptalks.Geometry | null = null
let editingFeatureId: number | null = null
let editingKind: 'point' | 'line' | 'polygon' = 'polygon'
/** 面要素的工作副本（面片 = 外环 + 洞） */
let editingParts: PolygonParts = []
/** 点/线要素的工作副本 */
let editingSimple: LngLat[] = []
let editingSymbol: Record<string, unknown> = {}
let editingColor = '#2d6cdf'
let editingOnChange: ((geojson: Record<string, unknown>) => void) | null = null

function geometryOptions(g: Maptalks.Geometry): Record<string, unknown> {
  return ((g as unknown as { options?: Record<string, unknown> }).options || {}) as Record<string, unknown>
}

/** iSpace 的坐标可能是 [x,y] 数组，也可能是 Coordinate 对象，统一成数组 */
function toLngLat(c: unknown): [number, number] {
  if (Array.isArray(c)) return [Number(c[0]), Number(c[1])]
  const o = c as { x?: number; y?: number }
  return [Number(o?.x), Number(o?.y)]
}

function geometryCoords(g: Maptalks.Geometry): [number, number][] {
  const c = g.getCoordinates?.()
  if (!c) return []
  const type = g.getType()
  if (type === 'Point') return [toLngLat(c)]
  if (type === 'LineString') return (c as unknown[]).map(toLngLat)
  if (type === 'Polygon') return ((c as unknown[][])[0] || []).map(toLngLat)
  return []
}

/** 编辑中的 GeoJSON（面要素包含洞与飞地） */
function currentEditingGeojson(): Record<string, unknown> {
  if (editingKind === 'polygon') return partsToGeojson(editingParts)
  if (editingKind === 'line') return { type: 'LineString', coordinates: editingSimple }
  return { type: 'Point', coordinates: editingSimple[0] ?? [] }
}

/** 用编辑中的坐标重建编辑层几何（避免直接改 MultiPolygon 子几何导致样式丢失） */
function rebuildEditingGeometry(): void {
  if (!editLayer) return
  const old = editingGeometry
  if (old) {
    old.off('click', handleEditGeometryClick)
    old.off('dragend', handleEditDragEnd)
    editLayer.removeGeometry(old)
  }
  const gj = currentEditingGeojson()
  const geo = ispace.GeoJSON.toGeometry(gj) as Maptalks.Geometry | Maptalks.Geometry[]
  const next = Array.isArray(geo) ? geo[0] : geo
  if (!next) {
    editingGeometry = null
    return
  }
  next.setSymbol(editingSymbol)
  next.config('draggable', true)
  editLayer.addGeometry(next)
  next.on('click', handleEditGeometryClick)
  next.on('dragend', handleEditDragEnd)
  editingGeometry = next
  if (editingFeatureId !== null) featureGeometries.set(editingFeatureId, next)
}

/** 应用面片修改：校验 → 重建几何 → 重建手柄 → 通知上层；返回错误提示 */
function applyParts(parts: PolygonParts): string | null {
  const error = validateParts(parts)
  if (error) return error
  editingParts = parts.map((polygon) => polygon.map(closeRing))
  rebuildEditingGeometry()
  buildVertexMarkers()
  editingOnChange?.(currentEditingGeojson())
  return null
}

/** 点击位置到线段的距离（单位为“度”，仅用于阈值判断） */
function pointToSegment(p: [number, number], a: [number, number], b: [number, number]): number {
  const vx = b[0] - a[0]
  const vy = b[1] - a[1]
  const wx = p[0] - a[0]
  const wy = p[1] - a[1]
  const len2 = vx * vx + vy * vy
  let t = len2 ? (wx * vx + wy * vy) / len2 : 0
  t = Math.max(0, Math.min(1, t))
  const dx = wx - t * vx
  const dy = wy - t * vy
  return Math.sqrt(dx * dx + dy * dy)
}

/** 拖动一个顶点后的处理：洞用橙色手柄区分 */
function moveVertex(
  partIndex: number,
  ringIndex: number,
  pointIndex: number,
  marker: Maptalks.Marker,
): void {
  const mc = marker.getCoordinates()
  const pt: LngLat = [mc.x, mc.y]
  if (editingKind === 'polygon') {
    const parts = cloneParts(editingParts)
    const ring = parts[partIndex]?.[ringIndex]
    if (!ring) return
    ring[pointIndex] = pt
    if (pointIndex === 0) ring[ring.length - 1] = [pt[0], pt[1]]
    const error = validateParts(parts)
    if (error) {
      buildVertexMarkers()
      return
    }
    editingParts = parts
  } else {
    const coords = editingSimple.map((p) => [p[0], p[1]] as LngLat)
    coords[pointIndex] = pt
    editingSimple = coords
  }
  // 延后重建，避免在标记自身的 dragend 中移除该标记
  window.setTimeout(() => {
    if (!editingGeometry || !editLayer) return
    rebuildEditingGeometry()
    buildVertexMarkers()
    editingOnChange?.(currentEditingGeojson())
  }, 0)
}

/** 按当前几何重建顶点手柄（面的每个环、每条飞地面片都会生成） */
function buildVertexMarkers(): void {
  vertexMarkers.forEach((m) => m.remove())
  vertexMarkers = []
  if (!editingGeometry || !editLayer) return
  const symbolForRing = (isHole: boolean) => ({
    markerType: 'ellipse',
    markerFill: '#ffffff',
    markerFillOpacity: 1,
    markerWidth: 11,
    markerHeight: 11,
    markerLineWidth: 3,
    markerLineColor: isHole ? '#f0a020' : editingColor,
    cursor: 'move',
  })

  const addMarker = (
    point: LngLat,
    isHole: boolean,
    onDrag: (marker: Maptalks.Marker) => void,
  ) => {
    const marker = new ispace.Marker(point, {
      symbol: symbolForRing(isHole),
      cursor: 'move',
      draggable: true,
    })
    marker.on('dragend', () => onDrag(marker))
    marker.addTo(editLayer!)
    vertexMarkers.push(marker)
  }

  if (editingKind === 'polygon') {
    editingParts.forEach((polygon, partIndex) => {
      polygon.forEach((ring, ringIndex) => {
        // 闭合环的最后一个点与第一个点重合，不再重复生成手柄
        const count = Math.max(ring.length - 1, 0)
        for (let index = 0; index < count; index++) {
          const point = ring[index]
          addMarker(point, ringIndex > 0, (marker) => moveVertex(partIndex, ringIndex, index, marker))
        }
      })
    })
    return
  }

  editingSimple.forEach((point, index) => {
    addMarker(point, false, (marker) => moveVertex(0, 0, index, marker))
  })
}

/** 在距点击位置最近的一条线段上插入顶点（线/面要素，面要素含洞与飞地） */
function insertVertexAt(click: LngLat): void {
  if (!editingGeometry || !map || editingKind === 'point') return
  type RingRef = { partIndex: number; ringIndex: number; ring: Ring; closed: boolean }
  const rings: RingRef[] = []
  if (editingKind === 'polygon') {
    editingParts.forEach((polygon, partIndex) => {
      polygon.forEach((ring, ringIndex) => {
        rings.push({ partIndex, ringIndex, ring, closed: true })
      })
    })
  } else {
    rings.push({ partIndex: 0, ringIndex: 0, ring: editingSimple, closed: false })
  }

  let best: RingRef | null = null
  let bestIndex = -1
  let bestDist = Infinity
  for (const ref of rings) {
    const path = ref.closed ? ref.ring.slice(0, -1) : ref.ring.slice()
    if (path.length < 2) continue
    const segCount = ref.closed ? path.length : path.length - 1
    for (let i = 0; i < segCount; i++) {
      const d = pointToSegment(click, path[i], path[(i + 1) % path.length])
      if (d < bestDist) {
        bestDist = d
        best = ref
        bestIndex = i
      }
    }
  }
  if (!best || bestIndex < 0) return
  // 只在靠近线/面的边上才算“插入”，避免图内任意点击都加点
  const resolution = map.getResolution() || 1
  if (bestDist * 111320 > resolution * 14) return

  if (editingKind === 'polygon') {
    const parts = cloneParts(editingParts)
    parts[best.partIndex][best.ringIndex].splice(bestIndex + 1, 0, click)
    applyParts(parts)
    return
  }
  const coords = editingSimple.map((p) => [p[0], p[1]] as LngLat)
  coords.splice(bestIndex + 1, 0, click)
  editingSimple = coords
  rebuildEditingGeometry()
  buildVertexMarkers()
  editingOnChange?.(currentEditingGeojson())
}

function handleEditGeometryClick(param: unknown): void {
  const coordinate = (param as { coordinate?: { x: number; y: number } }).coordinate
  if (!coordinate) return
  insertVertexAt([coordinate.x, coordinate.y])
}

function handleEditDragEnd(): void {
  const geometry = editingGeometry
  if (!geometry) return
  // 整体移动后把最新坐标同步到工作副本，并让手柄跟着走
  if (editingKind === 'polygon') {
    const parts = geometryParts(geometry.toGeoJSON())
    if (parts.length) editingParts = parts.map((polygon) => polygon.map(closeRing))
  } else {
    editingSimple = geometryCoords(geometry)
  }
  buildVertexMarkers()
  editingOnChange?.(currentEditingGeojson())
}

/** 设置几何显隐（飞地要连子面片一起设置） */
function setGeometryVisible(g: Maptalks.Geometry, visible: boolean): void {
  g.config('visible', visible)
  const children = (g as unknown as { getGeometries?: () => Maptalks.Geometry[] }).getGeometries?.()
  children?.forEach((child) => child.config('visible', visible))
}

function stopVertexEdit(): void {
  vertexMarkers.forEach((m) => m.remove())
  vertexMarkers = []
  editingGeometry?.off('click', handleEditGeometryClick)
  editingGeometry?.off('dragend', handleEditDragEnd)
  // 恢复原始要素显示与登记，取消编辑时仍能正常交互
  if (editingSource) {
    setGeometryVisible(editingSource, true)
    if (editingFeatureId !== null) featureGeometries.set(editingFeatureId, editingSource)
  }
  editingGeometry = null
  editingSource = null
  editingFeatureId = null
  editingParts = []
  editingSimple = []
  editingOnChange = null
  editLayer?.remove()
  editLayer = null
}

/** 打开顶点编辑：drag 顶点改形状、单击边线插点、拖动图形整体移动（支持洞与飞地）。 */
function startVertexEdit(
  geometry: Maptalks.Geometry,
  color: string,
  onChange: (geojson: Record<string, unknown>) => void,
  featureId?: number | null,
): void {
  // 进入编辑后原要素被隐藏，属性卡会失去锚点，先收起
  closePopup()
  stopVertexEdit()
  if (!map) return
  const type = geometry.getType()
  editingKind = type === 'Polygon' || type === 'MultiPolygon' ? 'polygon' : type === 'LineString' ? 'line' : 'point'
  if (editingKind === 'polygon') {
    const parts = geometryParts(geometry.toGeoJSON())
    if (!parts.length || !parts[0]?.[0]?.length) throw new Error('该要素没有可编辑的顶点')
    editingParts = parts.map((polygon) => polygon.map(closeRing))
  } else {
    const coords = geometryCoords(geometry)
    if (!coords.length) throw new Error('该要素没有可编辑的顶点')
    editingSimple = coords
  }

  editLayer = new ispace.VectorLayer('vertex-edit', { zIndex: 300 })
  editLayer.addTo(map)

  editingColor = color
  // 编辑结果直接回调业务层，不做坐标系转换
  editingOnChange = onChange
  editingFeatureId = featureId ?? null
  const sourceSymbol = (geometry as unknown as { getSymbol?: () => Record<string, unknown> }).getSymbol?.()
  editingSymbol =
    sourceSymbol && Object.keys(sourceSymbol).length ? sourceSymbol : symbolFor(editingKind, color)

  // 编辑层中放一份副本，原要素暂时隐藏，避免叠影与图层数据被中途改坏
  if (geometry.getLayer()) {
    editingSource = geometry
    setGeometryVisible(geometry, false)
  }
  rebuildEditingGeometry()
  buildVertexMarkers()
  onChange(currentEditingGeojson())
}

/**
 * 按要素 id 打开顶点编辑。
 * 优先使用渲染时登记的几何对象；找不到时用要素 GeoJSON 兜底，
 * 避免因图层未渲染（模块隐藏、图层刷新中）无法编辑形状。
 */
function startVertexEditById(
  featureId: number,
  color: string,
  onChange: (geojson: Record<string, unknown>) => void,
  fallbackGeojson?: Record<string, unknown> | null,
): void {
  let found: Maptalks.Geometry | null = featureGeometries.get(featureId) ?? null
  if (!found) {
    for (const layer of moduleLayers.values()) {
      for (const g of layer.getGeometries() as Maptalks.Geometry[]) {
        if (geometryOptions(g).featureId === featureId) {
          found = g
          break
        }
      }
      if (found) break
    }
  }
  if (!found && fallbackGeojson) {
    const geo = ispace.GeoJSON.toGeometry(fallbackGeojson) as
      | Maptalks.Geometry
      | Maptalks.Geometry[]
    found = Array.isArray(geo) ? geo[0] : geo
    if (found) {
      const type = found.getType()
      found.setSymbol(
        type === 'Point'
          ? {
              markerType: 'ellipse',
              markerFill: color,
              markerFillOpacity: 0.85,
              markerWidth: 12,
              markerHeight: 12,
              markerLineWidth: 2,
              markerLineColor: '#fff',
            }
          : { lineColor: color, lineWidth: 2, polygonFill: color, polygonOpacity: 0.25 },
      )
      featureGeometries.set(featureId, found)
    }
  }
  if (!found) throw new Error('未找到该要素图形，请刷新图层后重试')
  startVertexEdit(found, color, onChange, featureId)
}

// ---------------- 形状编辑中的挖洞 / 飞地 ----------------
/** 在当前编辑的面要素上挖一个洞 */
async function addHoleToEditing(color?: string): Promise<void> {
  if (!editingGeometry || editingKind !== 'polygon') throw new Error('仅面要素支持挖洞')
  const ring = await drawRing(color || editingColor)
  if (!ring || !editingGeometry) return
  const merged = mergeHole(editingParts, ring)
  if (!merged) throw new Error('挖洞失败：洞需完整绘制在某个面片内部，且不能与已有洞重叠')
  const error = applyParts(merged)
  if (error) throw new Error(`挖洞失败：${error}`)
}

/** 在当前编辑的面要素上添加一个飞地面片 */
async function addPartToEditing(color?: string): Promise<void> {
  if (!editingGeometry || editingKind !== 'polygon') throw new Error('仅面要素支持飞地')
  const ring = await drawRing(color || editingColor)
  if (!ring || !editingGeometry) return
  const merged = mergePart(editingParts, ring)
  if (!merged) throw new Error('添加飞地失败：新面片不能落在已有面片内部（面内区域请用「挖洞」）')
  const error = applyParts(merged)
  if (error) throw new Error(`添加飞地失败：${error}`)
}

/** 撤销编辑中最后一个洞（没有洞时撤销最后一个飞地面片） */
function undoEditingRing(): void {
  if (!editingGeometry || editingKind !== 'polygon') return
  const next = dropLastRing(editingParts)
  if (!next) return
  applyParts(next)
}

/** 当前编辑中的面片统计（用于界面提示） */
function getEditingShapeInfo(): { parts: number; holes: number } {
  if (editingKind !== 'polygon') return { parts: 0, holes: 0 }
  return {
    parts: editingParts.length,
    holes: editingParts.reduce((sum, polygon) => sum + Math.max(polygon.length - 1, 0), 0),
  }
}

// ---------------- 视图 ----------------
function fitTo(geojson: Record<string, unknown> | null, zoom?: number): void {
  if (!map || !geojson) return
  try {
    map.fitExtent(ispace.GeoJSON.toGeometry(geojson).getExtent(), 0, {
      animation: true,
      duration: 400,
      paddingLeft: 0,
      paddingRight: 0,
      paddingTop: 0,
      paddingBottom: 0,
    })
    if (zoom) map.setZoom(zoom)
  } catch {
    /* 忽略异常几何 */
  }
}

function panTo(lng: number, lat: number, zoom?: number): void {
  map?.animateTo({ center: [lng, lat], zoom: zoom ?? map.getZoom() }, { duration: 400 })
}

/** 缩放到一组坐标点的整体范围（用于比对结果等散点场景）。 */
function fitPoints(points: Array<[number, number]>, padding = 40): void {
  if (!map || !points.length) return
  const coords = points
  if (coords.length === 1) {
    map.animateTo({ center: coords[0] }, { duration: 400 })
    return
  }
  let minX = coords[0][0]
  let maxX = minX
  let minY = coords[0][1]
  let maxY = minY
  for (const [x, y] of coords) {
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  map.fitExtent(new ispace.Extent(minX, minY, maxX, maxY), 0, {
    animation: true,
    duration: 400,
    paddingLeft: padding,
    paddingRight: padding,
    paddingTop: padding,
    paddingBottom: padding,
  })
}

// ---------------- 生命周期 ----------------
let sizeObserver: ResizeObserver | null = null
let sizeRaf = 0

onMounted(() => {
  initMap()
  document.addEventListener('keydown', handlePopupEscape)
  // 侧边栏收起/窗口尺寸变化时通知地图重算画布，避免瓦片与控制条错位
  if (mapEl.value && typeof ResizeObserver !== 'undefined') {
    sizeObserver = new ResizeObserver(() => {
      if (sizeRaf) return
      sizeRaf = requestAnimationFrame(() => {
        sizeRaf = 0
        map?.checkSize(true)
      })
    })
    sizeObserver.observe(mapEl.value)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handlePopupEscape)
  sizeObserver?.disconnect()
  sizeObserver = null
  if (sizeRaf) cancelAnimationFrame(sizeRaf)
  cancelDraw()
  stopVertexEdit()
  clearPreview()
  editCleanups.forEach((fn) => fn())
  editCleanups = []
  map?.remove()
  map = null
})

defineExpose({
  getMap: () => map,
  getViewport,
  getModuleLayer,
  closePopup,
  renderGroups,
  renderPlain,
  clearLayer,
  clearModuleLayers,
  removeModuleLayer,
  startDraw,
  cancelDraw,
  previewGeometry,
  clearPreview,
  startDrawHole,
  startDrawPart,
  undoLastRing,
  startVertexEdit,
  startVertexEditById,
  stopVertexEdit,
  addHoleToEditing,
  addPartToEditing,
  undoEditingRing,
  getEditingShapeInfo,
  fitTo,
  panTo,
  fitPoints,
})
</script>

<style scoped lang="scss">
.map-view-wrap {
  position: relative;
  width: 100%;
  height: 100%;
}
.map-view {
  width: 100%;
  height: 100%;
  /* 无底图时也有明确的画布底色，避免出现空白区域 */
  background: #eef1f6;
}
/* 要素属性卡的出现/消失：只做透明度过渡，避免与定位用的 transform 冲突 */
.map-popup-enter-active,
.map-popup-leave-active {
  transition: opacity 0.16s ease;
}
.map-popup-enter-from,
.map-popup-leave-to {
  opacity: 0;
}
/* 底图未配置时的提示（仅提示，不影响要素绘制） */
.map-tip {
  /* 放在底部中间，避免与绘制/编辑浮动工具条重叠 */
  position: absolute;
  bottom: 14px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 16px;
  border-radius: 10px;
  border: 1px solid #f0c36d;
  background: rgba(255, 247, 230, 0.96);
  color: #8a5a00;
  font-size: 12px;
  line-height: 1.45;
  text-align: center;
  pointer-events: none;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
}
.map-tip-title {
  font-size: 13px;
  font-weight: 600;
}
.map-tip-desc {
  opacity: 0.85;
}
</style>
