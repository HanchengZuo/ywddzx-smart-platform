import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { configureAxiosAuth } from './utils/authSession'

const pinia = createPinia()
const app = createApp(App)

configureAxiosAuth(router)

app.use(pinia)
app.use(router)

router.isReady().then(() => {
    app.mount('#app')
})
