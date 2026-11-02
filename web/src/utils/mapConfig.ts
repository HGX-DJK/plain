/**
 * 底图运行时配置（来自 public/js/config.js）。
 *
 * 内网/离线部署时只需修改 config.js 里的 MAP_TILE_* 项，刷新浏览器即可生效，
 * 不需要重新构建前端，也不再依赖天地图等公网服务。
 */
export type MapTileCrs = 'gcj02' | 'wgs84'
/** 瓦片渲染器：gl 支持倾斜/旋转，canvas 仅 2D（瓦片服务不带 CORS 头时使用） */
export type MapTileRenderer = 'gl' | 'canvas'

export interface MapTileConfig {
  /** 瓦片模板，支持 {z}/{x}/{y} 与 {s} */
  url: string
  /** 子域列表，模板中没有 {s} 时为空 */
  subdomains: string[]
  minZoom: number
  maxZoom: number
  /** 瓦片坐标系（仅用于界面说明，业务坐标不做偏移转换） */
  crs: MapTileCrs
  /** 坐标系中文说明，供界面展示 */
  crsLabel: string
  renderer: MapTileRenderer
  attribution: string
}

function toNumber(value: unknown, fallback: number): number {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

function toSubdomains(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((v) => String(v).trim()).filter(Boolean)
  if (typeof value === 'string') {
    return value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return []
}

function toText(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function parse(): MapTileConfig {
  const raw = (typeof window !== 'undefined' ? window._config : undefined) ?? {}
  const crs: MapTileCrs = toText(raw.MAP_TILE_CRS).toLowerCase() === 'wgs84' ? 'wgs84' : 'gcj02'
  const renderer: MapTileRenderer =
    toText(raw.MAP_TILE_RENDERER).toLowerCase() === 'canvas' ? 'canvas' : 'gl'
  return {
    url: toText(raw.MAP_TILE_URL),
    subdomains: toSubdomains(raw.MAP_TILE_SUBDOMAINS),
    minZoom: toNumber(raw.MAP_TILE_MIN_ZOOM, 3),
    maxZoom: toNumber(raw.MAP_TILE_MAX_ZOOM, 18),
    crs,
    crsLabel: crs === 'gcj02' ? 'GCJ-02（高德/火星坐标）' : 'WGS84（CGCS2000）',
    renderer,
    attribution: toText(raw.MAP_ATTRIBUTION),
  }
}

export const mapTileConfig: MapTileConfig = parse()
