<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import { api, downloadUrl } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import FormFeedback from '../../common/FormFeedback/FormFeedback.vue'
import FilePreview from '../../common/FilePreview/FilePreview.vue'
const props = defineProps<{ course: string; canUpload: boolean }>()
const session = useSession(),
  op = useOperation()
type Material = {
  id: string
  title: string
  filename: string
  size: number
  author: number
  author_name: string
  teaching_resource: boolean
}
const rows = ref<Material[]>([]),
  title = ref(''),
  file = ref<File>(),
  picker = ref<HTMLInputElement>()
async function load() {
  await op.execute(async () => {
    rows.value = await api<Material[]>('course-materials/?course=' + props.course)
  }, '')
}
onMounted(load)
async function upload() {
  await op.execute(async () => {
    if (!file.value) throw Error('Выберите файл')
    const data = new FormData()
    data.set('course', props.course)
    data.set('title', title.value)
    data.set('file', file.value)
    await api('course-materials/', 'POST', data)
    title.value = ''
    file.value = undefined
    if (picker.value) picker.value.value = ''
    rows.value = await api<Material[]>('course-materials/?course=' + props.course)
  }, 'Материал загружен')
}
function select(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0]
}
</script>
<template>
  <section class="panel" data-layout="coursematerials-style-1">
    <h2>Материалы курса</h2>
    <p class="helper">
      Учебные материалы доступны участникам. Файлы студента видят он сам и преподаватели.
    </p>
    <FormFeedback :error="op.error.value" :success="op.success.value" :fields="op.fields.value" />
    <p v-if="!rows.length && !op.busy.value">Материалы пока не загружены.</p>
    <article v-for="row in rows" :key="row.id" data-layout="coursematerials-style-2">
      <h3>{{ row.title }}</h3>
      <p class="helper">
        {{ row.teaching_resource ? 'Учебный материал' : 'Работа участника' }} ·
        {{ row.author_name || (row.author === session.user?.id ? 'Вы' : 'Автор') }} ·
        {{ Math.ceil(row.size / 1024) }} КБ
      </p>
      <FilePreview :path="'course-materials/' + row.id + '/download/'" :filename="row.filename" />
      <a :href="downloadUrl('course-materials/' + row.id + '/download/')"
        >Скачать {{ row.filename }}</a
      >
    </article>
    <form v-if="canUpload" class="form" @submit.prevent="upload">
      <h3>Загрузить материал</h3>
      <label>Название<input v-model="title" required maxlength="200" /></label>
      <label
        >Файл<input
          ref="picker"
          type="file"
          accept=".txt,.md,.csv,.docx,.pptx,.pdf,.png,.jpg,.jpeg"
          required
          @change="select"
      /></label>
      <p class="helper">TXT, Markdown, CSV, DOCX, PPTX, PDF, PNG, JPG — до 20 МБ.</p>
      <Button type="submit" label="Загрузить" :loading="op.busy.value" />
    </form>
  </section>
</template>
<style src="./CourseMaterials.css" scoped></style>
