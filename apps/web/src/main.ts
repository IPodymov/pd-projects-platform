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
      50: '#eef5ef',
      100: '#dcebdd',
      200: '#b9d7be',
      300: '#8ebb96',
      400: '#65a473',
      500: '#39794b',
      600: '#2e633e',
      700: '#254f33',
      800: '#1c3d28',
      900: '#173020',
      950: '#0c1d12',
    },
  },
})
createApp(App)
  .use(createPinia())
  .use(router)
  .use(PrimeVue, { theme: { preset: theme, options: { darkModeSelector: false } }, ripple: true })
  .mount('#app')
