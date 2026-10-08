<script setup lang="ts">
import { computed, ref, onBeforeUnmount } from 'vue'
import Button from 'primevue/button'
import { downloadUrl, apiError } from '@/api'
import { useOperation } from '@/composables/useOperation'
import FormFeedback from '../FormFeedback/FormFeedback.vue'
import ArticleBody from '../ArticleBody/ArticleBody.vue'
const props = defineProps<{ path: string; filename: string }>()
const extension = computed(() => props.filename.split('.').at(-1)?.toLowerCase())
const supported = computed(() =>
  ['txt', 'md', 'csv', 'pdf', 'png', 'jpg', 'jpeg'].includes(extension.value || ''),
)
const opened = ref(false),
  text = ref(''),
  source = ref(''),
  op = useOperation()
let controller: AbortController | undefined
function close() {
  controller?.abort()
  opened.value = false
  if (source.value) URL.revokeObjectURL(source.value)
  source.value = ''
  text.value = ''
}
onBeforeUnmount(close)
async function show() {
  opened.value = true
  await op.execute(async () => {
    controller = new AbortController()
    const response = await fetch(downloadUrl(props.path), {
      credentials: 'include',
      signal: controller.signal,
    })
    if (!response.ok) throw apiError(await response.json().catch(() => null), response.status)
    const content = await response.blob()
    if (!opened.value) return
    if (['txt', 'md', 'csv'].includes(extension.value || '')) text.value = await content.text()
    else {
      const type =
        extension.value === 'pdf'
          ? 'application/pdf'
          : extension.value === 'png'
            ? 'image/png'
            : 'image/jpeg'
      source.value = URL.createObjectURL(new Blob([content], { type }))
    }
  }, '')
}
</script>
<template>
  <Button
    v-if="supported && !opened"
    label="Просмотреть"
    text
    :loading="op.busy.value"
    @click="show"
  />
  <section
    v-if="opened"
    class="panel"
    data-layout="filepreview-style-1"
    aria-label="Просмотр материала"
  >
    <div class="actions">
      <strong>{{ filename }}</strong
      ><Button label="Закрыть просмотр" text @click="close" />
    </div>
    <FormFeedback :error="op.error.value" />
    <p v-if="op.busy.value" role="status">Загрузка материала…</p>
    <template v-else-if="!op.error.value">
      <iframe
        v-if="extension === 'pdf' && source"
        :src="source"
        :title="filename"
        sandbox="allow-scripts"
        data-layout="filepreview-style-2"
      />
      <img v-else-if="source" :src="source" :alt="filename" data-layout="filepreview-style-3" />
      <ArticleBody v-else-if="extension === 'md'" :body="text" />
      <pre v-else data-layout="filepreview-style-4">{{ text }}</pre>
    </template>
  </section>
</template>
<style src="./FilePreview.css" scoped></style>
