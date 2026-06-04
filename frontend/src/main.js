import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { configureAxiosAuth } from './utils/authSession'
import { checkFrontendVersion } from './utils/frontendVersion'

const pinia = createPinia()
const app = createApp(App)

configureAxiosAuth(router)

app.use(pinia)

const bootstrap = async () => {
    const versionOk = await checkFrontendVersion()
    if (!versionOk) return
    app.use(router)
    await router.isReady()
    app.mount('#app')
}

bootstrap()
