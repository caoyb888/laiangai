import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import '@/assets/variables.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 恢复 sessionStorage 中的登录态
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
auth.restoreFromSession()

app.mount('#app')
