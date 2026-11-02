/**
 * 地图视野：采集图层按视野取数时使用。
 *
 * 后端 /v1/features/map 的 bbox 与业务库同为「单位度」经纬度（SRID 4490），
 * 因此这里统一把地图引擎给出的范围换算成经纬度包围盒。
 */

/** 经纬度包围盒 [minLng, minLat, maxLng, maxLat] */
export type Bbox = [number, number, number, number]

export interface MapViewport {
  bbox: Bbox
  zoom: number
}

/** Web 墨卡托（米）→ 经纬度（度）；地图引擎以 3857 输出包围盒时用于兜底换算 */
export function mercatorToLonLat(x: number, y: number): [number, number] {
  const r = 6378137
  const lng = ((x / r) * 180) / Math.PI
  const lat = ((Math.atan(Math.sinh(y / r)) * 180) / Math.PI)
  return [lng, lat]
}

/**
 * 把任意单位的包围盒归一化为经纬度。
 *
 * iSpace 底图按经纬度建图时 getExtent() 直接给出度；若现场换成墨卡托投影
 * （数值可达千万级），这里按 3857 反算，避免把米当度发给 PostGIS 导致查不到数据。
 */
export function toLonLatBbox(minx: number, miny: number, maxx: number, maxy: number): Bbox {
  const isDegrees = Math.abs(minx) <= 180 && Math.abs(maxx) <= 180 && Math.abs(miny) <= 90 && Math.abs(maxy) <= 90
  let a = minx
  let b = miny
  let c = maxx
  let d = maxy
  if (!isDegrees) {
    ;[a, b] = mercatorToLonLat(minx, miny)
    ;[c, d] = mercatorToLonLat(maxx, maxy)
  }
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
  return [
    Number(clamp(Math.min(a, c), -180, 180).toFixed(7)),
    Number(clamp(Math.min(b, d), -90, 90).toFixed(7)),
    Number(clamp(Math.max(a, c), -180, 180).toFixed(7)),
    Number(clamp(Math.max(b, d), -90, 90).toFixed(7)),
  ]
}
