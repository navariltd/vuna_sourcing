import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { frappeRequest, setConfig } from 'frappe-ui'
import { router } from './router'
import './style.css'
import App from './App.vue'

setConfig('resourceFetcher', frappeRequest)

createApp(App).use(createPinia()).use(router).mount('#app')
