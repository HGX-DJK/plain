/// <reference types="vite/client" />

interface Window {
  /** 运行时配置，见 public/js/config.js */
  _config?: {
    BASE_API?: string
    // ---- 底图（内网/离线部署时在前端配置文件里指定） ----
    MAP_TILE_URL?: string
    MAP_TILE_SUBDOMAINS?: string[] | string
    MAP_TILE_CRS?: string
    MAP_TILE_MIN_ZOOM?: number | string
    MAP_TILE_MAX_ZOOM?: number | string
    MAP_TILE_RENDERER?: string
    MAP_ATTRIBUTION?: string
    [key: string]: string | string[] | number | undefined
  }
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}
