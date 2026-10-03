import { ref, onBeforeUnmount } from 'vue'
import { client, apiError } from '@/api'
import type { components } from '@future/api-client'
export interface DiffLine {
  kind: string
  text: string
  ranges?: number[][]
}
export function useComparison() {
  const busy = ref(false),
    status = ref(''),
    error = ref(''),
    lines = ref<DiffLine[]>([]),
    structure = ref<unknown[]>([])
  let generation = 0
  onBeforeUnmount(() => generation++)
  async function compare(old: string, other: string) {
    const current = ++generation
    busy.value = true
    error.value = ''
    lines.value = []
    status.value = 'queued'
    try {
      const result = await client.POST('/api/v1/document-versions/{id}/compare/', {
        params: { path: { id: old } },
        body: { other },
      })
      if (!result.data) throw apiError(result.error, result.response.status)
      let job: components['schemas']['Comparison'] = result.data
      for (let attempt = 0; attempt < 90 && current === generation; attempt++) {
        status.value = job.status
        if (job.status === 'failed')
          throw Error(
            'Сравнение завершилось ошибкой: ' +
              job.error_code +
              '. Повторите запрос после проверки файлов.',
          )
        if (job.status === 'succeeded') {
          const data = job.result as { lines?: DiffLine[]; new_structure?: unknown[] }
          lines.value = data.lines || []
          structure.value = data.new_structure || []
          return
        }
        await new Promise((resolve) => setTimeout(resolve, 1000))
        if (current !== generation) return
        const next = await client.GET('/api/v1/comparisons/{id}/', {
          params: { path: { id: job.id } },
        })
        if (!next.data) throw apiError(next.error, next.response.status)
        job = next.data
      }
      if (current === generation)
        throw Error(
          'Обработка продолжается. Повторите запрос позже, чтобы получить сохранённый результат.',
        )
    } catch (e) {
      if (current === generation) error.value = String(e)
    } finally {
      if (current === generation) busy.value = false
    }
  }
  return { busy, status, error, lines, structure, compare }
}
