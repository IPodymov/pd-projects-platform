<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/dateTime'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Button from 'primevue/button'
import PageState from '@/components/common/PageState/PageState.vue'
import ArticleBody from '@/components/common/ArticleBody/ArticleBody.vue'
import FormFeedback from '@/components/common/FormFeedback/FormFeedback.vue'
import { api, downloadUrl } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import type { components } from '@future/api-client'
type Material = components['schemas']['Publication'] | components['schemas']['Competition']
const preview = ref(false)
const route = useRoute(),
  session = useSession(),
  op = useOperation(),
  resource = computed(() => String(route.params.resource)),
  competitions = computed(() => resource.value === 'competitions'),
  rows = ref<Material[]>([]),
  apps = ref<components['schemas']['Application'][]>([]),
  projects = ref<components['schemas']['Project'][]>([]),
  topics = ref<components['schemas']['Topic'][]>([]),
  loading = ref(true),
  error = ref(''),
  editId = ref(''),
  form = ref({
    slug: '',
    title: '',
    body: '',
    lead: '',
    requirements: '',
    deadline: '',
    topic: '',
    visibility: 'public',
  }),
  dirty = ref(false),
  selectedCompetition = ref(''),
  project = ref(''),
  text = ref(''),
  feedback = ref<Record<string, string>>({})
const canWrite = computed(
  () =>
    !!session.user?.platform_admin ||
    (!competitions.value && !!session.user?.roles.includes('curator')),
)
function canEdit(row: Material) {
  return (
    !!session.user?.platform_admin ||
    (canWrite.value && 'author' in row && row.author === session.user?.id)
  )
}
async function importText(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  await op.execute(async () => {
    if (file.size > 1024 * 1024 || !/\.(md|txt)$/i.test(file.name))
      throw Error('Выберите Markdown или TXT до 1 МБ')
    form.value.body = await file.text()
  }, 'Текст импортирован. Сохраните черновик.')
  input.value = ''
}
async function uploadImage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !editId.value) return
  await op.execute(async () => {
    const data = new FormData()
    data.set('file', file)
    const result = await api<{ path: string }>(
      'publications/' + editId.value + '/upload_image/',
      'POST',
      data,
    )
    form.value.body += '\n\n![Изображение](' + downloadUrl(result.path) + ')\n'
  }, 'Изображение добавлено. Сохраните текст черновика.')
  input.value = ''
}
useUnsavedChanges(dirty)
watch(form, () => (dirty.value = true), { deep: true, flush: 'sync' })
async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api<Material[]>(resource.value + '/')
    topics.value = await api<components['schemas']['Topic'][]>('topics/')
    if (session.user?.id) {
      projects.value = await api<components['schemas']['Project'][]>('projects/')
      apps.value = await api<components['schemas']['Application'][]>('competition-applications/')
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(resource, () => {
  editId.value = ''
  void load()
})
function edit(row?: Material) {
  editId.value = row?.id || ''
  form.value = {
    slug: row?.slug || '',
    title: row?.title || '',
    body: row && 'body' in row ? row.body : '',
    lead: row && 'lead' in row ? row.lead || '' : '',
    requirements: row && 'requirements' in row ? row.requirements : '',
    deadline: row && 'deadline' in row ? row.deadline.slice(0, 16) : '',
    topic: row?.topic || topics.value[0]?.code || '',
    visibility: row?.visibility || 'public',
  }
  dirty.value = false
}
async function save() {
  const body = {
    slug: form.value.slug,
    title: form.value.title,
    topic: form.value.topic,
    visibility: form.value.visibility,
    ...(competitions.value
      ? {
          requirements: form.value.requirements,
          deadline: new Date(form.value.deadline).toISOString(),
        }
      : { body: form.value.body, lead: form.value.lead }),
  }
  const result = await op.execute(() =>
    api(
      resource.value + '/' + (editId.value ? editId.value + '/' : ''),
      editId.value ? 'PATCH' : 'POST',
      body,
    ),
  )
  if (result) {
    dirty.value = false
    edit()
    await load()
  }
}
async function transition(id: string, status: string, application = false) {
  if (
    (status === 'cancelled' || status === 'archived') &&
    !window.confirm(
      'Подтвердить ' + (status === 'cancelled' ? 'отмену заявки' : 'архивирование') + '?',
    )
  )
    return
  const result = await op.execute(() =>
    api(
      (application ? 'competition-applications' : resource.value) + '/' + id + '/transition/',
      'POST',
      { status, ...(application ? { feedback: feedback.value[id] || '' } : {}) },
    ),
  )
  if (result) await load()
}
async function apply() {
  const result = await op.execute(() =>
    api('competition-applications/', 'POST', {
      competition: selectedCompetition.value,
      project: project.value,
      text: text.value,
    }),
  )
  if (result) {
    text.value = ''
    await load()
  }
}
async function editApplication(row: components['schemas']['Application']) {
  const result = await op.execute(() =>
    api('competition-applications/' + row.id + '/', 'PATCH', { text: row.text }),
  )
  if (result) await load()
}
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">МАТЕРИАЛЫ ПЛАТФОРМЫ</p>
      <h1>{{ competitions ? 'Конкурсы и заявки' : 'Журнал платформы' }}</h1>
    </div>
    <Button v-if="canWrite" label="Новый черновик" @click="edit()" />
  </div>
  <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
  <form v-if="canWrite" class="panel form" @submit.prevent="save">
    <h2>{{ editId ? 'Редактировать черновик' : 'Подготовить материал' }}</h2>
    <label>Название<input v-model="form.title" required maxlength="200" /></label
    ><label>Постоянный адрес<input v-model="form.slug" required pattern="[a-zA-Z0-9_-]+" /></label
    ><label
      >Тема<select v-model="form.topic" required>
        <option value="" disabled>Выберите тему</option>
        <option v-for="topic in topics" :key="topic.code" :value="topic.code">
          {{ topic.title }}
        </option>
      </select></label
    ><label
      >Аудитория<select v-model="form.visibility">
        <option value="public">Публично</option>
        <option value="authenticated">Участники платформы</option>
      </select></label
    ><label v-if="!competitions"
      >Вступление для ленты<textarea v-model="form.lead" maxlength="500" /></label
    ><label v-if="!competitions && editId"
      >Добавить изображение (PNG, JPG до 5 МБ)<input
        type="file"
        accept="image/png,image/jpeg"
        @change="uploadImage" /></label
    ><label v-if="!competitions"
      >Импорт текста<input type="file" accept=".md,.txt" @change="importText" /></label
    ><label
      >{{ competitions ? 'Требования' : 'Текст'
      }}<textarea v-if="competitions" v-model="form.requirements" required /><textarea
        v-else
        v-model="form.body"
        required
      /></label
    ><label v-if="competitions"
      >Приём заявок до<input v-model="form.deadline" type="datetime-local" required /></label
    ><template v-if="!competitions"
      ><p class="helper">
        Markdown: заголовки ##, списки, ссылки, изображения, цитаты и блоки кода. HTML выводится как
        текст.
      </p>
      <Button type="button" label="Предпросмотр" severity="secondary" @click="preview = !preview" />
      <article v-if="preview" class="panel">
        <h2>{{ form.title }}</h2>
        <p>{{ form.lead }}</p>
        <ArticleBody :body="form.body" /></article></template
    ><Button type="submit" label="Сохранить черновик" :loading="op.busy.value" />
  </form>
  <PageState :loading="loading" :error="error" :empty="!rows.length" @retry="load"
    ><div class="grid">
      <article v-for="row in rows" :key="row.id" class="panel">
        <span class="badge">{{ row.status }}</span>
        <h2>{{ row.title }}</h2>
        <template v-if="'body' in row"
          ><p class="helper">
            {{ row.author_name || 'Редакция платформы' }} ·
            {{ topics.find((t) => t.code === row.topic)?.title }}
          </p>
          <p>{{ row.lead || row.body.slice(0, 240) }}</p>
          <RouterLink :to="'/articles/' + row.id">Читать статью</RouterLink></template
        >
        <p v-else data-layout="materialsview-style-1">{{ row.requirements }}</p>
        <p v-if="'deadline' in row">До {{ formatDateTime(row.deadline) }}</p>
        <div v-if="canEdit(row)" class="actions">
          <Button
            v-if="row.status === 'draft'"
            label="Редактировать"
            text
            @click="edit(row)"
          /><Button
            v-if="row.status === 'draft'"
            label="Опубликовать"
            :disabled="op.busy.value"
            @click="transition(row.id, 'published')"
          /><Button
            v-if="row.status === 'published'"
            label="Архивировать"
            text
            :disabled="op.busy.value"
            @click="transition(row.id, 'archived')"
          />
        </div>
        <Button
          v-if="competitions && session.user?.id && row.status === 'published'"
          label="Подготовить заявку проекта"
          @click="selectedCompetition = row.id"
        />
      </article></div
  ></PageState>
  <form v-if="selectedCompetition" class="panel form" @submit.prevent="apply">
    <h2>Новая заявка</h2>
    <label
      >Проект<select v-model="project" required>
        <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.title }}</option>
      </select></label
    ><label>Описание результата<textarea v-model="text" required /></label
    ><Button type="submit" label="Сохранить черновик заявки" :loading="op.busy.value" />
  </form>
  <section v-if="competitions && session.user?.id" class="panel">
    <h2>Заявки проектов</h2>
    <p v-if="!apps.length" class="helper">Пока нет заявок.</p>
    <article v-for="a in apps" :key="a.id">
      <h3>{{ projects.find((x) => x.id === a.project)?.title }} · {{ a.status }}</h3>
      <textarea
        v-if="a.author === session.user?.id && ['draft', 'revision'].includes(a.status)"
        v-model="a.text"
      />
      <p v-else>{{ a.text }}</p>
      <div class="actions">
        <Button
          v-if="a.author === session.user?.id && ['draft', 'revision'].includes(a.status)"
          label="Сохранить изменения"
          :disabled="op.busy.value"
          @click="editApplication(a)"
        /><Button
          v-if="a.author === session.user?.id && ['draft', 'revision'].includes(a.status)"
          label="Отправить"
          :disabled="op.busy.value"
          @click="transition(a.id, 'submitted', true)"
        /><Button
          v-if="
            a.author === session.user?.id && ['draft', 'submitted', 'revision'].includes(a.status)
          "
          label="Отменить"
          text
          :disabled="op.busy.value"
          @click="transition(a.id, 'cancelled', true)"
        />
      </div>
      <div v-if="session.user?.platform_admin && a.status === 'submitted'" class="form">
        <label>Замечание<textarea v-model="feedback[a.id]" /></label>
        <div class="actions">
          <Button
            v-for="state in [
              { id: 'accepted', label: 'Принять' },
              { id: 'revision', label: 'Доработка' },
              { id: 'rejected', label: 'Отклонить' },
            ]"
            :key="state.id"
            :label="state.label"
            :disabled="op.busy.value"
            @click="transition(a.id, state.id, true)"
          />
        </div>
      </div>
      <p v-for="h in a.history" :key="h.id" class="helper">
        {{ formatDateTime(h.created_at) }}: {{ h.previous }} → {{ h.status }} ·
        {{ h.feedback }}
      </p>
    </article>
  </section>
</template>
<style src="./MaterialsView.css" scoped></style>
