/** 后端返回的时间带真实时区偏移，统一按浏览器本地时区展示。 */
export function formatDateTime(t?: string | null, withSeconds = true): string {
  if (!t) return '-'
  const date = new Date(t)
  // 解析失败时退回原始字符串截断，避免出现 Invalid Date
  if (Number.isNaN(date.getTime())) return t.replace('T', ' ').slice(0, withSeconds ? 19 : 16)
  const pad = (n: number) => String(n).padStart(2, '0')
  const base = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
  return withSeconds ? `${base}:${pad(date.getSeconds())}` : base
}
