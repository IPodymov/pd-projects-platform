import { onMounted, onBeforeUnmount, type Ref } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'

export function useUnsavedChanges(dirty: Ref<boolean>) {
  const beforeUnload = (event: BeforeUnloadEvent) => {
    if (dirty.value) {
      event.preventDefault()
      event.returnValue = ''
    }
  }
  onMounted(() => window.addEventListener('beforeunload', beforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', beforeUnload))
  onBeforeRouteUpdate(
    () => !dirty.value || window.confirm('Есть несохранённые изменения. Перейти к другой записи?'),
  )
  onBeforeRouteLeave(
    () => !dirty.value || window.confirm('Есть несохранённые изменения. Покинуть страницу?'),
  )
}
