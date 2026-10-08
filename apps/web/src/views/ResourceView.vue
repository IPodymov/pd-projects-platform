<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import Button from 'primevue/button'
import PageState from '@/components/common/PageState/PageState.vue'
import { api, apiPage } from '@/api'
import { useSession } from '@/stores/session'
type Row = { id?: string; title?: string; name?: string; [key: string]: unknown }
type Field = {
  key: string
  label: string
  type?: string
  source?: string
  options?: { value: string; label: string }[]
}
const configs: Record<string, { title: string; description: string; fields: Field[] }> = {
  institutions: {
    title: 'Учреждения',
    description: 'Школы, колледжи и университеты.',
    fields: [
      { key: 'name', label: 'Название' },
      {
        key: 'kind',
        label: 'Тип',
        options: [
          { value: 'school', label: 'Школа' },
          { value: 'college', label: 'Колледж' },
          { value: 'university', label: 'Вуз' },
        ],
      },
    ],
  },
  classrooms: {
    title: 'Учебные группы',
    description: 'Состав каждого учебного года хранится отдельно.',
    fields: [
      { key: 'name', label: 'Название класса' },
      { key: 'academic_year', label: 'Учебный год (2026/2027)' },
      { key: 'institution', label: 'Учреждение', source: 'institutions' },
    ],
  },
  courses: {
    title: 'Курсы',
    description: 'Подготовка, материалы и участие в обучении.',
    fields: [
      { key: 'title', label: 'Название' },
      { key: 'description', label: 'Описание', type: 'textarea' },
      { key: 'institution', label: 'Учреждение', source: 'institutions' },
    ],
  },
  projects: {
    title: 'Проекты',
    description: 'Команды, задания и история вашей работы.',
    fields: [
      { key: 'title', label: 'Название' },
      { key: 'description', label: 'Описание', type: 'textarea' },
      { key: 'classroom', label: 'Класс', source: 'classrooms' },
    ],
  },
  invitations: {
    title: 'Пригласить сотрудника',
    description: 'Назначение роли закреплено в приглашении.',
    fields: [
      { key: 'email', label: 'Email', type: 'email' },
      { key: 'institution', label: 'Учреждение', source: 'institutions' },
      { key: 'classroom', label: 'Класс преподавателя (необязательно)', source: 'classrooms' },
      {
        key: 'role',
        label: 'Роль',
        options: [
          { value: 'teacher', label: 'Преподаватель' },
          { value: 'curator', label: 'Куратор' },
          { value: 'admin', label: 'Администратор учреждения (назначает платформа)' },
          { value: 'organizer', label: 'Организатор мастер-классов' },
          { value: 'workshop_teacher', label: 'Преподаватель мастер-классов' },
        ],
      },
    ],
  },
  publications: {
    title: 'Журнал платформы',
    description: 'Заметки, методические материалы и новости.',
    fields: [],
  },
  competitions: { title: 'Конкурсы', description: 'Требования и сроки участия.', fields: [] },
}
const route = useRoute(),
  session = useSession(),
  resource = computed(() => String(route.params.resource)),
  config = computed(() => configs[resource.value]),
  rows = ref<Row[]>([]),
  choices = ref<Record<string, Row[]>>({}),
  form = ref<Record<string, string>>({}),
  error = ref(''),
  loading = ref(false),
  saving = ref(false),
  showForm = ref(false),
  page = ref(1),
  count = ref(0),
  search = ref('')
const canCreate = computed(() => {
  if (resource.value === 'institutions') return !!session.user?.platform_admin
  if (['classrooms', 'invitations'].includes(resource.value)) return session.institutionAdmin
  if (resource.value === 'courses') return session.managesCourses
  return session.staff
})
async function load() {
  loading.value = true
  error.value = ''
  form.value = {}
  try {
    if (!config.value) throw Error('Раздел не найден')
    const data = await apiPage<Row>(
      resource.value + '/?page=' + page.value + '&search=' + encodeURIComponent(search.value),
    )
    rows.value = data.results
    count.value = data.count
    for (const f of config.value.fields) {
      if (f.source) choices.value[f.source] = await api<Row[]>(f.source + '/')
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
async function searchRows() {
  page.value = 1
  await load()
}
async function changePage(delta: number) {
  page.value += delta
  await load()
}
watch(
  resource,
  () => {
    page.value = 1
    search.value = ''
    showForm.value = false
    void load()
  },
  { immediate: true },
)
async function save() {
  saving.value = true
  error.value = ''
  try {
    const data = { ...form.value }
    if (!data.classroom) delete data.classroom
    await api(resource.value + '/', 'POST', data)
    showForm.value = false
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">ПЛАТФОРМА</p>
      <h1>{{ config?.title }}</h1>
      <p class="subtitle">{{ config?.description }}</p>
    </div>
    <Button
      v-if="canCreate && config?.fields.length"
      label="Создать"
      icon="pi pi-plus"
      @click="showForm = !showForm"
    />
  </div>
  <section v-if="showForm" class="panel" data-layout="resourceview-style-1">
    <form class="form" @submit.prevent="save">
      <label v-for="f in config?.fields" :key="f.key"
        >{{ f.label
        }}<select
          v-if="f.source || f.options"
          v-model="form[f.key]"
          :required="f.key !== 'classroom' || resource !== 'invitations'"
        >
          <option value="">Выберите…</option>
          <option v-for="o in f.options" :key="o.value" :value="o.value">{{ o.label }}</option>
          <option v-for="o in choices[f.source || '']" :key="o.id" :value="o.id">
            {{ o.name || o.title }}
          </option></select
        ><textarea v-else-if="f.type === 'textarea'" v-model="form[f.key]" /><input
          v-else
          v-model="form[f.key]"
          :type="f.type || 'text'"
          required /></label
      ><Button type="submit" label="Сохранить" :loading="saving" />
    </form>
  </section>
  <form class="filters" @submit.prevent="searchRows">
    <input v-model="search" aria-label="Поиск" placeholder="Поиск по названию" /><Button
      type="submit"
      label="Найти"
    />
  </form>
  <PageState :loading="loading" :error="error" :empty="!rows.length" @retry="load"
    ><div class="grid">
      <article v-for="r in rows" :key="r.id" class="panel">
        <div class="card-icon"><i class="pi pi-folder" /></div>
        <h3>{{ r.title || r.name || r.email }}</h3>
        <p class="helper">{{ r.description || r.body || r.requirements || r.role || r.kind }}</p>
        <div class="card-meta">
          <span v-if="r.deadline"
            >До {{ new Date(String(r.deadline)).toLocaleDateString('ru') }}</span
          ><span v-if="r.academic_year">{{ r.academic_year }}</span
          ><span v-if="r.status" class="badge">{{ r.status }}</span>
        </div>
        <RouterLink v-if="resource === 'courses'" :to="'/courses/' + r.id"
          ><Button label="Открыть курс" text
        /></RouterLink>
        <RouterLink v-if="resource === 'projects'" :to="'/projects/' + r.id"
          ><Button label="Открыть проект" text icon="pi pi-arrow-right"
        /></RouterLink>
      </article></div
  ></PageState>
  <div class="actions">
    <Button label="Назад" :disabled="page === 1 || loading" @click="changePage(-1)" /><span
      >Страница {{ page }} · всего {{ count }}</span
    ><Button label="Далее" :disabled="page * 50 >= count || loading" @click="changePage(1)" />
  </div>
</template>
<style src="./ResourceView.css" scoped></style>
