/**
 * 前端配置文件：部署后可能随现场变化的配置项统一放在这里。
 * 修改后刷新浏览器即可生效，无需重新构建；后端配置见 backend/.env，两者互不引用。
 */
window._config = {
  // 后端接口地址：前后端同源（后端托管 dist）或 nginx 反代 /api 时留空；
  // 前端单独部署且未反代时填写后端地址，如 'http://192.168.1.10:8100'
  BASE_API: '',

  /* ================= 底图（内网服务，已按现场默认值配置） =================
   * 模板变量：{z} 层级、{x} 列号、{y} 行号，可选 {s} 子域（配合 MAP_TILE_SUBDOMAINS 使用）。
   * 例：http://{s}.tile.internal.local/vec/{z}/{x}/{y}.png
   */
  MAP_TILE_URL:
    'http://192.168.110.93:31003/gws/tiles/service/tile/1.0.0/raster/{z}/{x}/{y}.png?authorizeCode=xxx',

  // 子域列表，模板中不含 {s} 时留空数组即可
  MAP_TILE_SUBDOMAINS: [],

  // 瓦片坐标系：gcj02（高德/腾讯等国内切片）/ wgs84（原始 CGCS2000 切片）
  // 仅影响界面上的坐标系说明文字；系统内坐标一律按原值入库、绘制，不做偏移转换。
  MAP_TILE_CRS: 'gcj02',

  // 底图可用的最小 / 最大层级
  MAP_TILE_MIN_ZOOM: 3,
  MAP_TILE_MAX_ZOOM: 18,

  // 瓦片渲染器：gl（默认，WebGL 贴图，支持地图倾斜/旋转视角）
  // 若现场瓦片服务没有返回 Access-Control-Allow-Origin，GL 无法贴图，
  // 可改成 'canvas'（仅 2D，倾斜视角下瓦片不会显示）
  MAP_TILE_RENDERER: 'gl',

  // 底图版权信息，留空则不显示
  MAP_ATTRIBUTION: '',
}
