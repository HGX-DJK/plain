/** naive-ui 全局注册与轻量提示。 */
import type { App } from 'vue'
import naive from 'naive-ui'

export function setupNaive(app: App): void {
  app.use(naive)
}

import { createDiscreteApi } from 'naive-ui'

const { message, dialog, notification } = createDiscreteApi(['message', 'dialog', 'notification'])

export const toastError = (text: string) => message.error(text)
export const toastSuccess = (text: string) => message.success(text)
export const dialogError = (text: string) => dialog.error({ title: '操作失败', content: text, positiveText: '知道了' })
/** 确认对话框；点击确定后执行 onConfirm。 */
export const dialogConfirm = (
  content: string,
  onConfirm?: () => void | Promise<void>,
  title = '确认操作',
) => {
  dialog.warning({
    title,
    content,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: () => {
      void onConfirm?.()
    },
  })
}
export const notifySuccess = (title: string, content?: string) =>
  notification.success({ title, content })
