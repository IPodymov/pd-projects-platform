<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/dateTime'
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import Button from 'primevue/button'
import PageState from '@/components/PageState.vue'
import FormFeedback from '@/components/FormFeedback.vue'
import ProjectGit from '@/components/ProjectGit.vue'
import DiffLine from '@/components/DiffLine.vue'
import { useComparison } from '@/composables/useComparison'
import { useOperation } from '@/composables/useOperation'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { api, downloadUrl } from '@/api'
import { useSession } from '@/stores/session'
import type { components } from '@future/api-client'
type Project = components['schemas']['Project']
type Doc = components['schemas']['Document']
type Version = components['schemas']['Version']
type Task = components['schemas']['Task']
type Submission = components['schemas']['Submission']
type Member = components['schemas']['Membership']
type Milestone = components['schemas']['Milestone']
const route = useRoute(),
  session = useSession(),
  p = ref<Project>(),
  docs = ref<Doc[]>([]),
  versions = ref<Version[]>([]),
  tasks = ref<Task[]>([]),
  submissions = ref<Submission[]>([]),
  members = ref<Member[]>([]),
  chosenMember = ref<number>(),
  error = ref(''),
  loading = ref(true),
  busy = ref(false),
  docTitle = ref(''),
  selectedDoc = ref(''),
  file = ref<File>(),
  old = ref(''),
  next = ref(''),
  draft = ref(false),
  previous = ref(''),
  dirty = ref(false),
  milestones = ref<Milestone[]>([]),
  stageForm = ref({ title: '', criteria: '', due_at: '' }),
  taskTitle = ref(''),
  taskDue = ref(''),
  taskMilestone = ref(''),
  criteria = ref(''),
  selectedTask = ref(''),
  work = ref(''),
  feedback = ref(''),
  reviewFeedback = ref<Record<string, string>>({}),
  team = ref<components['schemas']['Member'][]>([]),
  memberRole = ref('member'),
  editingWork = ref('')
const comparison = useComparison(),
  operation = useOperation()
const lines = comparison.lines
useUnsavedChanges(dirty)
watch(work, () => (dirty.value = true), { flush: 'sync' })
const id = String(route.params.id),
  visibleVersions = computed(() => versions.value.filter((v) => v.document === selectedDoc.value))
async function load() {
  loading.value = true
  error.value = ''
  try {
    team.value = await api<components['schemas']['Member'][]>('project-members/?project=' + id)
    p.value = await api<Project>('projects/' + id + '/')
    milestones.value = await api<Milestone[]>('milestones/?project=' + id)
    ;[docs.value, versions.value, tasks.value, submissions.value] = await Promise.all([
      api<Doc[]>('documents/'),
      api<Version[]>('document-versions/'),
      api<Task[]>('tasks/'),
      api<Submission[]>('submissions/'),
    ])
    docs.value = docs.value.filter((d) => d.project === id)
    tasks.value = tasks.value.filter((t) => t.project === id)
    submissions.value = submissions.value.filter((s) => tasks.value.some((t) => t.id === s.task))
    if (!selectedDoc.value) selectedDoc.value = docs.value[0]?.id || ''
    if (session.staff)
      members.value = await api<Member[]>('memberships/?classroom=' + p.value.classroom)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
async function run(action: () => Promise<unknown>) {
  if (busy.value) return
  busy.value = true
  const result = await operation.execute(action)
  if (result !== undefined) {
    dirty.value = false
    await load()
  }
  busy.value = false
}
function pick(e: Event) {
  file.value = (e.target as HTMLInputElement).files?.[0]
}
async function upload() {
  if (!file.value || !selectedDoc.value) return
  const data = new FormData()
  data.append('file', file.value)
  await run(() => api('documents/' + selectedDoc.value + '/upload/', 'POST', data))
}
async function diff() {
  await comparison.compare(old.value, next.value)
}
async function sendWork() {
  if (editingWork.value) {
    const selected = submissions.value.find((x) => x.id === editingWork.value)
    await run(() =>
      api(
        'submissions/' + editingWork.value + '/',
        'PATCH',
        { text: work.value },
        selected?.updated_at,
      ),
    )
    editingWork.value = ''
    return
  }

  await run(() =>
    api('submissions/', 'POST', {
      task: selectedTask.value,
      text: work.value,
      draft: draft.value,
      ...(previous.value ? { previous: previous.value } : {}),
    }),
  )
}
async function restoreVersion(version: string) {
  if (window.confirm('Восстановить файл как новую версию? Текущая история сохранится.'))
    await run(() => api('document-versions/' + version + '/restore/', 'POST'))
}
function editDraft(s: Submission) {
  selectedTask.value = s.task
  work.value = s.text
  editingWork.value = s.id
  draft.value = true
}
function revise(s: Submission) {
  selectedTask.value = s.task
  work.value = s.text
  previous.value = s.id
  draft.value = true
  dirty.value = false
}
function projectActions() {
  const actions: Record<string, string[]> = {
    draft: ['active'],
    active: ['submitted', 'archived'],
    submitted: ['revision', 'accepted'],
    revision: ['submitted', 'archived'],
    accepted: ['archived'],
    archived: [],
  }
  return (actions[p.value?.status || 'archived'] || []).filter(
    (x) => session.staff || x === 'submitted',
  )
}
async function projectTransition(status: string) {
  if (!p.value) return
  if (status === 'archived' && !window.confirm('Архивировать проект?')) return
  await run(() =>
    api(
      'projects/' + id + '/transition/',
      'POST',
      { status, feedback: feedback.value },
      p.value!.updated_at,
    ),
  )
}
async function stageTransition(m: Milestone, status: string) {
  await run(() => api('milestones/' + m.id + '/transition/', 'POST', { status }, m.updated_at))
}
async function createStage() {
  await run(() =>
    api('milestones/', 'POST', {
      project: id,
      ...stageForm.value,
      due_at: new Date(stageForm.value.due_at).toISOString(),
      position: milestones.value.length,
    }),
  )
}
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">УЧЕБНЫЙ ПРОЕКТ</p>
      <h1>{{ p?.title || 'Проект' }}</h1>
      <p class="subtitle">{{ p?.description }}</p>
    </div>
    <span class="badge">Принято {{ p?.progress || 0 }}%</span>
  </div>
  <FormFeedback
    :error="operation.error.value"
    :fields="operation.fields.value"
    :success="operation.success.value"
  />
  <PageState :loading="loading" :error="error" @retry="load"
    ><div class="grid two">
      <section class="panel">
        <h2>Команда</h2>
        <p v-for="m in team" :key="m.id">
          {{ m.name }} · {{ m.role === 'leader' ? 'Лидер' : 'Участник' }}
          <Button
            v-if="session.staff"
            :label="m.role === 'leader' ? 'Сделать участником' : 'Назначить лидером'"
            text
            :disabled="busy"
            @click="
              run(() =>
                api(
                  'project-members/' + m.id + '/',
                  'PATCH',
                  { role: m.role === 'leader' ? 'member' : 'leader' },
                  m.updated_at,
                ),
              )
            "
          />
        </p>
        <p class="helper">
          {{ p?.members.length }} участников. Назначение доступно преподавателю класса.
        </p>
        <form
          v-if="session.staff"
          class="form"
          @submit.prevent="
            run(() =>
              api('project-members/', 'POST', {
                project: id,
                user: chosenMember,
                role: memberRole,
              }),
            )
          "
        >
          <label
            >Участник<select v-model="chosenMember" required>
              <option v-for="m in members" :key="m.id" :value="m.user">
                {{ m.name }} · {{ m.email }}
              </option>
            </select></label
          ><label
            >Роль в команде<select v-model="memberRole">
              <option value="member">Участник</option>
              <option value="leader">Лидер</option>
            </select></label
          ><Button type="submit" label="Добавить в команду" :loading="busy" />
        </form>
      </section>
      <section class="panel">
        <h2>Этапы и задания</h2>
        <form
          v-if="session.staff"
          class="form"
          @submit.prevent="
            run(() =>
              api('tasks/', 'POST', {
                project: id,
                title: taskTitle,
                stage: 'Основной',
                criteria,
                ...(taskMilestone ? { milestone: taskMilestone } : {}),
                due_at: new Date(taskDue).toISOString(),
              }),
            )
          "
        >
          <label>Новое задание<input v-model="taskTitle" required /></label
          ><label>Критерии<input v-model="criteria" required /></label
          ><label
            >Этап<select v-model="taskMilestone">
              <option value="">Без этапа</option>
              <option v-for="m in milestones" :key="m.id" :value="m.id">{{ m.title }}</option>
            </select></label
          ><label>Срок<input v-model="taskDue" type="datetime-local" required /></label
          ><Button type="submit" label="Назначить задание" :loading="busy" />
        </form>
        <p v-if="!tasks.length" class="helper">Задания ещё не назначены.</p>
        <p v-for="t in tasks" :key="t.id">
          <strong>{{ t.title }}</strong
          ><br /><span class="helper">{{ t.stage }} · до {{ formatDateTime(t.due_at) }}</span>
        </p>
      </section>
    </div>
    <section class="panel" style="margin-top: 24px">
      <h2>Жизненный цикл · {{ p?.status }}</h2>
      <div class="actions">
        <Button
          v-for="status in projectActions()"
          :key="status"
          :label="status"
          :loading="busy"
          @click="projectTransition(status)"
        />
      </div>
      <label v-if="session.staff">Замечание к проекту<input v-model="feedback" /></label>
      <h2 style="margin-top: 24px">Этапы проекта</h2>
      <form v-if="session.staff" class="form" @submit.prevent="createStage">
        <label>Название этапа<input v-model="stageForm.title" required /></label
        ><label>Критерии<textarea v-model="stageForm.criteria" required /></label
        ><label>Срок<input v-model="stageForm.due_at" type="datetime-local" required /></label
        ><Button label="Добавить этап" type="submit" :loading="busy" />
      </form>
      <article v-for="m in milestones" :key="m.id" style="margin-top: 20px">
        <h3>{{ m.title }} · {{ m.status }}</h3>
        <p>{{ m.criteria }}</p>
        <div class="actions">
          <Button
            v-if="session.staff && m.status === 'planned'"
            label="Начать этап"
            :loading="busy"
            @click="stageTransition(m, 'active')"
          /><Button
            v-if="m.status === 'active' || m.status === 'revision'"
            label="Отправить этап"
            :loading="busy"
            @click="stageTransition(m, 'submitted')"
          /><Button
            v-if="session.staff && m.status === 'submitted'"
            label="Принять этап"
            :loading="busy"
            @click="stageTransition(m, 'accepted')"
          /><Button
            v-if="session.staff && m.status === 'submitted'"
            label="На доработку"
            :loading="busy"
            @click="stageTransition(m, 'revision')"
          />
        </div>
      </article>
    </section>
    <section class="panel" style="margin-top: 24px">
      <h2>Отправить результат</h2>
      <form class="form" @submit.prevent="sendWork">
        <label
          >Задание<select v-model="selectedTask" required>
            <option v-for="t in tasks" :key="t.id" :value="t.id">{{ t.title }}</option>
          </select></label
        ><label>Результат<textarea v-model="work" required /></label
        ><label><input v-model="draft" type="checkbox" />Сохранить как черновик</label>
        <p v-if="previous" class="helper">Повторная работа после {{ previous.slice(0, 8) }}.</p>
        <Button
          type="submit"
          :label="draft ? 'Сохранить черновик' : 'Отправить на проверку'"
          :loading="busy"
        />
      </form>
      <div v-for="s in submissions" :key="s.id" class="panel" style="margin-top: 20px">
        <span class="badge">{{ s.result }}</span>
        <p>{{ s.text }}</p>
        <Button
          v-if="s.result === 'draft' && s.author === session.user?.id"
          label="Редактировать черновик"
          text
          @click="editDraft(s)"
        />
        <p v-if="s.feedback" class="helper">Замечания: {{ s.feedback }}</p>
        <Button
          v-if="s.author === session.user?.id && s.result === 'revision'"
          label="Подготовить повторную отправку"
          text
          @click="revise(s)"
        />
        <Button
          v-if="s.author === session.user?.id && s.result === 'draft'"
          label="Отправить черновик"
          :loading="busy"
          @click="run(() => api('submissions/' + s.id + '/send/', 'POST'))"
        />
        <form
          v-if="session.staff && s.result === 'submitted'"
          class="form"
          @submit.prevent="
            run(() =>
              api('submissions/' + s.id + '/review/', 'POST', {
                result: 'accepted',
                feedback: reviewFeedback[s.id] || '',
              }),
            )
          "
        >
          <label>Замечание<input v-model="reviewFeedback[s.id]" /></label>
          <div class="actions">
            <Button type="submit" label="Принять" :loading="busy" /><Button
              label="На доработку"
              severity="secondary"
              :loading="busy"
              @click="
                run(() =>
                  api('submissions/' + s.id + '/review/', 'POST', {
                    result: 'revision',
                    feedback: reviewFeedback[s.id] || '',
                  }),
                )
              "
            />
          </div>
        </form>
      </div>
    </section>
    <section class="panel" style="margin-top: 24px">
      <h2>Документы и история версий</h2>
      <form
        class="form"
        @submit.prevent="run(() => api('documents/', 'POST', { project: id, title: docTitle }))"
      >
        <label>Название нового документа<input v-model="docTitle" required /></label
        ><Button type="submit" label="Создать документ" :loading="busy" />
      </form>
      <div class="filters" style="margin-top: 24px">
        <select v-model="selectedDoc" aria-label="Документ">
          <option v-for="d in docs" :key="d.id" :value="d.id">{{ d.title }}</option></select
        ><input
          type="file"
          accept=".txt,.md,.csv,.docx,.pptx"
          aria-label="Новая версия файла"
          @change="pick"
        /><Button
          label="Загрузить версию"
          :disabled="!file || !selectedDoc"
          :loading="busy"
          @click="upload"
        />
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Файл</th>
              <th>Создан</th>
              <th>Размер</th>
              <th>Текст</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in visibleVersions" :key="v.id">
              <td>{{ v.filename }}</td>
              <td>{{ formatDateTime(v.created_at) }}</td>
              <td>{{ v.size }} Б</td>
              <td>{{ v.extraction_status }}</td>
              <td>
                <a :href="downloadUrl('document-versions/' + v.id + '/download/')">Скачать ↓</a
                ><Button label="Восстановить" text @click="restoreVersion(v.id)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="helper">
        Восстановление создаёт новую версию. Для DOCX/PPTX сравнивается извлечённый текст, без
        визуального сравнения оформления.
      </p>
      <div class="filters">
        <select v-model="old" aria-label="Старая версия">
          <option value="">Старая версия</option>
          <option v-for="v in visibleVersions" :key="v.id" :value="v.id">
            {{ v.filename }} · {{ new Date(v.created_at).toLocaleTimeString() }}
          </option></select
        ><select v-model="next" aria-label="Новая версия">
          <option value="">Новая версия</option>
          <option v-for="v in visibleVersions" :key="v.id" :value="v.id">
            {{ v.filename }} · {{ new Date(v.created_at).toLocaleTimeString() }}
          </option></select
        ><Button
          label="Сравнить"
          :disabled="!old || !next"
          :loading="comparison.busy.value"
          @click="diff"
        />
      </div>
      <p v-if="comparison.busy.value" role="status">Сравнение: {{ comparison.status.value }}…</p>
      <FormFeedback :error="comparison.error.value" />
      <div v-if="lines.length" class="diff">
        <div v-for="(line, i) in lines" :key="i" :class="['diff-line', line.kind]">
          <DiffLine :text="line.text" :ranges="line.ranges" />
        </div>
      </div></section
  ></PageState>
  <ProjectGit :project="id" />
</template>
