import './assets/main.css'
import 'primeicons/primeicons.css'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { definePreset } from '@primeuix/themes'
import App from './App.vue'
import router from './router'
const theme = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#f1f5ff',
      100: '#e1e9ff',
      200: '#c7d5ff',
      300: '#a5bcff',
      400: '#7292ff',
      500: '#2f59ef',
      600: '#274bd0',
      700: '#2244bc',
      800: '#203b95',
      900: '#1c3177',
      950: '#14214b',
    },
  },
})
createApp(App)
  .use(createPinia())
  .use(router)
  .use(PrimeVue, { theme: { preset: theme, options: { darkModeSelector: false } }, ripple: true })
  .mount('#app')
