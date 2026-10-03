import { ref } from 'vue'
import { ApiError } from '@/api'
export function useOperation() {
  const busy = ref(false),
    error = ref(''),
    fields = ref<Record<string, string[]>>({}),
    success = ref('')
  async function execute<T>(
    action: () => Promise<T>,
    message = 'Изменения сохранены',
  ): Promise<T | undefined> {
    if (busy.value) return
    busy.value = true
    error.value = ''
    fields.value = {}
    success.value = ''
    try {
      const value = await action()
      success.value = message
      return value
    } catch (e) {
      error.value = String(e)
      if (e instanceof ApiError) fields.value = e.fields
      return undefined
    } finally {
      busy.value = false
    }
  }
  return { busy, error, fields, success, execute }
}
