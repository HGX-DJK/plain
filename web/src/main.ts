import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { setupNaive } from './utils/naive'
// 地图引擎 iSpace 的脚本与样式在 index.html 中以本地文件引入（见 public/iSpace）
import './styles/index.scss'

const app = createApp(App)
app.use(createPinia())
app.use(router)
setupNaive(app)
app.mount('#app')
