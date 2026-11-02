/** 地图要素点击弹窗的数据结构与属性格式化工具。 */

export type PopupPlacement = 'top' | 'bottom'

export interface PopupRow {
  label: string
  value: string
}

export interface PopupData {
  /** 锚点：相对地图容器的像素坐标 */
  x: number
  y: number
  /** 弹窗相对锚点的方向 */
  placement: PopupPlacement
  /** 主题色，取模块颜色 */
  accent: string
  title: string
  subtitle?: string
  badges?: string[]
  rows: PopupRow[]
  hint?: string
}

/** 拿不到模块字段定义时使用的兜底字段名 */
const FALLBACK_LABELS: Record<string, string> = {
  code: '编号',
  name: '名称',
  status: '状态',
  addr: '地址',
  address: '地址',
  phone: '联系电话',
  type2: '分类',
  area: '面积(㎡)',
  height: '高度(m)',
  road: '所属道路',
  width: '宽度(m)',
  cls: '等级',
  usage: '用途',
  floor_count: '层数',
  building_height: '建筑高度(m)',
  structure_type: '结构类型',
  build_year: '建成年份',
  ownership: '权属',
  parcel_code: '地块编号',
  region_code: '区域编码',
  declared_lng: '申报经度',
  declared_lat: '申报纬度',
  center_lng: '中心经度',
  center_lat: '中心纬度',
  area_m2: '面积(㎡)',
  length_m: '长度(m)',
  created_at: '创建时间',
  updated_at: '更新时间',
  remark: '备注',
  module_name: '所属模块',
}

/** 不在弹窗里展示的键（几何、内部主键等） */
const HIDDEN_KEYS = new Set(['id', 'geometry', 'geom', 'wkt', 'properties', 'feature_id'])

/** 属性值 -> 展示文本；空值返回空串（调用方据此跳过该行） */
export function formatPopupValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return ''
    return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100)
  }
  if (Array.isArray(value)) {
    return value.map((v) => formatPopupValue(v)).filter(Boolean).join('、')
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return ''
    }
  }
  return String(value).trim()
}

/** 要素属性 -> 弹窗行（字段名优先取模块字段定义，其次兜底字典，最后用原始 key） */
export function popupRows(
  properties: Record<string, unknown> | null | undefined,
  labels?: Record<string, string> | null,
): PopupRow[] {
  if (!properties) return []
  const rows: PopupRow[] = []
  for (const [key, raw] of Object.entries(properties)) {
    if (HIDDEN_KEYS.has(key)) continue
    const value = formatPopupValue(raw)
    if (!value) continue
    rows.push({ label: labels?.[key] || FALLBACK_LABELS[key] || key, value })
  }
  return rows
}

/** 十六进制颜色 -> rgba()，用于主题色的浅色底 */
export function withAlpha(hex: string, alpha: number): string {
  const raw = (hex || '').replace('#', '').trim()
  if (raw.length !== 6 || /[^0-9a-f]/i.test(raw)) return `rgba(45, 108, 223, ${alpha})`
  const r = Number.parseInt(raw.slice(0, 2), 16)
  const g = Number.parseInt(raw.slice(2, 4), 16)
  const b = Number.parseInt(raw.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** 拾取点坐标提示 */
export function coordHint(lng?: number, lat?: number): string | undefined {
  if (typeof lng !== 'number' || typeof lat !== 'number') return undefined
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return undefined
  return `经度 ${lng.toFixed(6)}　纬度 ${lat.toFixed(6)}`
}
