<script setup lang="ts">
import { formatDateTime } from '@/utils/dateTime'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Button from 'primevue/button'
import PageState from '@/components/PageState.vue'
import FormFeedback from '@/components/FormFeedback.vue'
import { api } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import type { components } from '@future/api-client'
type Material = components['schemas']['Publication'] | components['schemas']['Competition']
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
    error.value = String(e)
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
      : { body: form.value.body }),
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
    <Button v-if="session.user?.platform_admin" label="Новый черновик" @click="edit()" />
  </div>
  <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
  <form v-if="session.user?.platform_admin" class="panel form" @submit.prevent="save">
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
    ><label
      >{{ competitions ? 'Требования' : 'Текст'
      }}<textarea v-if="competitions" v-model="form.requirements" required /><textarea
        v-else
        v-model="form.body"
        required
      /></label
    ><label v-if="competitions"
      >Приём заявок до<input v-model="form.deadline" type="datetime-local" required /></label
    ><Button type="submit" label="Сохранить черновик" :loading="op.busy.value" />
  </form>
  <PageState :loading="loading" :error="error" :empty="!rows.length" @retry="load"
    ><div class="grid">
      <article v-for="row in rows" :key="row.id" class="panel">
        <span class="badge">{{ row.status }}</span>
        <h2>{{ row.title }}</h2>
        <p style="white-space: pre-wrap">{{ 'body' in row ? row.body : row.requirements }}</p>
        <p v-if="'deadline' in row">До {{ formatDateTime(row.deadline) }}</p>
        <div v-if="session.user?.platform_admin" class="actions">
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
