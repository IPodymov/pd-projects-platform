/// <reference types="vite/client" />

// Let the standard TypeScript language service resolve Vue single-file components.
// vue-tsc and Vue - Official provide the detailed component and template types.
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent
  export default component
}
