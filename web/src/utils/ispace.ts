/**
 * 地图引擎 iSpace 运行时入口。
 *
 * 项目使用 public/iSpace/ispace-gl-new.js（UMD 构建，挂载全局变量 window.ispace），
 * 它与 npm 上的 maptalks 是同一套 API，仅命名不同，因此类型声明继续复用 maptalks 的 d.ts。
 * 该脚本已在 index.html 中按同步脚本引入，模块执行时全局变量必然就绪。
 */
import type * as MaptalksTypes from 'maptalks'

type IspaceNamespace = typeof MaptalksTypes

const runtime = (globalThis as unknown as { ispace?: IspaceNamespace }).ispace

if (!runtime) {
  throw new Error(
    '未找到 ispace：请确认 index.html 已引入 /iSpace/ispace-gl-new.js（public/iSpace 下的本地文件）',
  )
}

const ispace: IspaceNamespace = runtime

export { ispace }
export default ispace
