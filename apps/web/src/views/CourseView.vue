<script setup lang="ts">
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/dateTime'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import Button from 'primevue/button'
import PageState from '@/components/PageState.vue'
import FormFeedback from '@/components/FormFeedback.vue'
import { api, client, apiError } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import type { components } from '@future/api-client'
type Course = components['schemas']['Course']
type Assignment = components['schemas']['Assignment']
type Work = components['schemas']['CourseWork']
type Enrollment = components['schemas']['Enrollment']
type Member = components['schemas']['Membership']
const id = String(useRoute().params.id),
  session = useSession(),
  course = ref<Course>(),
  assignments = ref<Assignment[]>([]),
  works = ref<Work[]>([]),
  enrollments = ref<Enrollment[]>([]),
  members = ref<Member[]>([]),
  loading = ref(true),
  error = ref(''),
  selected = ref(''),
  text = ref(''),
  dirty = ref(false),
  feedback = ref<Record<string, string>>({}),
  participant = ref(''),
  ownClass = ref(''),
  myMemberships = ref<Member[]>([]),
  availableClasses = ref<components['schemas']['Classroom'][]>([])
const op = useOperation(),
  form = ref({ title: '', instructions: '', criteria: '', due_at: '' })
useUnsavedChanges(dirty)
watch(text, () => (dirty.value = true), { flush: 'sync' })
watch(form, () => (dirty.value = true), { deep: true, flush: 'sync' })
const own = computed(() => enrollments.value.find((e) => e.user === session.user?.id)),
  latest = computed(() =>
    works.value
      .filter((w) => w.assignment === selected.value && w.enrollment === own.value?.id)
      .at(-1),
  )
watch(selected, () => {
  text.value = latest.value?.text || ''
  dirty.value = false
})
function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (!result.data) throw apiError(result.error, result.response.status)
  return result.data
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    course.value = unwrap(await client.GET('/api/v1/courses/{id}/', { params: { path: { id } } }))
    ;[assignments.value, works.value, enrollments.value] = await Promise.all([
      api<Assignment[]>('assignments/?course=' + id),
      api<Work[]>('course-submissions/'),
      api<Enrollment[]>('enrollments/?course=' + id),
    ])
    works.value = works.value.filter((w) => assignments.value.some((a) => a.id === w.assignment))
    availableClasses.value = await api<components['schemas']['Classroom'][]>('classrooms/')
    myMemberships.value = (await api<Member[]>('memberships/')).filter(
      (m) =>
        m.user === session.user?.id &&
        !m.ended_at &&
        availableClasses.value.some(
          (c) => c.id === m.classroom && c.institution === course.value?.institution,
        ),
    )
    if (!ownClass.value) ownClass.value = myMemberships.value[0]?.classroom || ''
    if (session.staff)
      members.value = (await api<Member[]>('memberships/')).filter((m) =>
        enrollments.value.every((e) => e.user !== m.user),
      )
    if (!selected.value) selected.value = assignments.value[0]?.id || ''
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
async function createAssignment() {
  await op.execute(async () => {
    unwrap(
      await client.POST('/api/v1/assignments/', {
        body: {
          ...form.value,
          due_at: new Date(form.value.due_at).toISOString(),
          course: id,
          required: true,
          position: assignments.value.length,
        },
      }),
    )
    dirty.value = false
    form.value = { title: '', instructions: '', criteria: '', due_at: '' }
    dirty.value = false
    await load()
  }, 'Задание добавлено')
}
async function lifecycle(status: 'published' | 'archived') {
  if (
    !window.confirm(
      status === 'published'
        ? 'После публикации задания курса нельзя редактировать. Опубликовать?'
        : 'Архивировать курс и закрыть новые отправки?',
    )
  )
    return
  await op.execute(async () => {
    unwrap(
      await client.POST('/api/v1/courses/{id}/transition/', {
        params: { path: { id } },
        headers: { 'If-Match': course.value!.updated_at },
        body: { status },
      }),
    )
    await load()
  })
}
async function joinCourse() {
  await op.execute(async () => {
    if (!session.user?.id) throw Error('Войдите в аккаунт')
    unwrap(
      await client.POST('/api/v1/enrollments/', {
        body: {
          course: id,
          classroom: own.value?.classroom || ownClass.value,
          user: session.user.id,
        },
      }),
    )
    await load()
  }, 'Вы записаны на курс')
}
async function enroll() {
  await op.execute(async () => {
    const m = members.value.find((m) => m.id === participant.value)
    if (!m) throw Error('Выберите участника класса')
    unwrap(
      await client.POST('/api/v1/enrollments/', {
        body: { course: id, classroom: m.classroom, user: m.user },
      }),
    )
    await load()
  }, 'Участник записан на курс')
}
async function save(send = false) {
  await op.execute(
    async () => {
      if (!own.value) throw Error('Для отправки нужна запись на курс')
      let work: Work
      if (latest.value?.status === 'draft') {
        work = unwrap(
          await client.PATCH('/api/v1/course-submissions/{id}/', {
            params: { path: { id: latest.value.id } },
            headers: { 'If-Match': latest.value.updated_at },
            body: { text: text.value },
          }),
        )
      } else {
        work = unwrap(
          await client.POST('/api/v1/course-submissions/', {
            body: {
              assignment: selected.value,
              enrollment: own.value.id,
              text: text.value,
              ...(latest.value?.status === 'revision' ? { previous: latest.value.id } : {}),
            },
          }),
        )
      }
      if (send)
        unwrap(
          await client.POST('/api/v1/course-submissions/{id}/send/', {
            params: { path: { id: work.id } },
            headers: { 'If-Match': work.updated_at },
          }),
        )
      dirty.value = false
      await load()
    },
    send ? 'Работа отправлена преподавателю' : 'Черновик сохранён',
  )
}
async function review(work: Work, result: 'accepted' | 'revision') {
  await op.execute(async () => {
    unwrap(
      await client.POST('/api/v1/course-submissions/{id}/review/', {
        params: { path: { id: work.id } },
        headers: { 'If-Match': work.updated_at },
        body: { result, feedback: feedback.value[work.id] || '' },
      }),
    )
    await load()
  }, 'Результат проверки сохранён')
}
async function cancel(e: Enrollment) {
  if (!window.confirm('Отменить запись? История работ сохранится.')) return
  await op.execute(async () => {
    unwrap(
      await client.POST('/api/v1/enrollments/{id}/cancel/', {
        params: { path: { id: e.id } },
        headers: { 'If-Match': e.updated_at },
      }),
    )
    await load()
  }, 'Запись отменена')
}
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">ПОДГОТОВКА</p>
      <h1>{{ course?.title || 'Курс' }}</h1>
      <p class="subtitle">{{ course?.description }}</p>
    </div>
    <span class="badge">{{ course?.status }}</span>
  </div>
  <FormFeedback
    :error="op.error.value"
    :fields="op.fields.value"
    :success="op.success.value"
  /><PageState :loading="loading" :error="error" @retry="load"
    ><div class="actions" v-if="session.managesSchedule">
      <Button
        v-if="course?.status === 'draft'"
        label="Опубликовать курс"
        :loading="op.busy.value"
        @click="lifecycle('published')"
      /><Button
        v-if="course?.status === 'published'"
        label="В архив"
        severity="secondary"
        :loading="op.busy.value"
        @click="lifecycle('archived')"
      />
    </div>
    <section
      class="panel"
      style="margin-top: 20px"
      v-if="session.managesSchedule && course?.status === 'draft'"
    >
      <h2>Добавить задание</h2>
      <form class="form" @submit.prevent="createAssignment">
        <label>Название<input v-model="form.title" required /></label
        ><label>Инструкция<textarea v-model="form.instructions" required /></label
        ><label>Критерии принятия<textarea v-model="form.criteria" required /></label
        ><label>Срок<input v-model="form.due_at" type="datetime-local" required /></label
        ><Button type="submit" label="Добавить" :loading="op.busy.value" />
      </form>
    </section>
    <section class="panel" style="margin-top: 20px" v-if="session.staff">
      <h2>Участники курса</h2>
      <form v-if="course?.status === 'published'" class="form" @submit.prevent="enroll">
        <label
          >Участник<select v-model="participant" required>
            <option value="">Выберите…</option>
            <option v-for="m in members" :key="m.id" :value="m.id">
              {{ m.name }} · {{ m.email }}
            </option>
          </select></label
        ><Button type="submit" label="Записать" :loading="op.busy.value" />
      </form>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Участник</th>
              <th>Статус</th>
              <th>Принято</th>
              <th>Действие</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in enrollments" :key="e.id">
              <td>{{ e.user_name }}</td>
              <td>{{ e.status }}</td>
              <td>{{ e.progress }}%</td>
              <td>
                <Button
                  v-if="e.status === 'active'"
                  text
                  label="Отменить запись"
                  :disabled="op.busy.value"
                  @click="cancel(e)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <section class="panel" style="margin-top: 20px">
      <h2>Задания</h2>
      <p v-if="!assignments.length" class="helper">Задания ещё не добавлены.</p>
      <article v-for="a in assignments" :key="a.id" style="margin-top: 20px">
        <h3>{{ a.title }}</h3>
        <p>{{ a.instructions }}</p>
        <p class="helper">Критерии: {{ a.criteria }}</p>
        <p class="helper">До {{ formatDateTime(a.due_at) }}</p>
      </article>
    </section>
    <section
      v-if="
        course?.status === 'published' &&
        (!own || own.status === 'cancelled') &&
        myMemberships.length
      "
      class="panel"
    >
      <h2>Запись на курс</h2>
      <form class="form" @submit.prevent="joinCourse">
        <label
          >Мой класс<select v-model="ownClass" required>
            <option v-for="m in myMemberships" :key="m.id" :value="m.classroom">
              {{ availableClasses.find((c) => c.id === m.classroom)?.name }}
            </option>
          </select></label
        ><Button type="submit" label="Записаться" :loading="op.busy.value" />
      </form>
    </section>
    <section v-if="own" class="panel" style="margin-top: 20px">
      <h2>Моя работа · принято {{ own.progress }}%</h2>
      <p class="helper">
        Статус записи: {{ own.status }}. Прогресс учитывает только принятые обязательные задания.
      </p>
      <form
        v-if="own.status === 'active' && course?.status === 'published'"
        class="form"
        @submit.prevent="save(true)"
      >
        <label
          >Задание<select v-model="selected" required>
            <option v-for="a in assignments" :key="a.id" :value="a.id">{{ a.title }}</option>
          </select></label
        ><label
          >Результат<textarea
            v-model="text"
            required
            :disabled="latest?.status === 'submitted' || latest?.status === 'accepted'"
          />
        </label>
        <p v-if="latest?.status === 'revision'" class="helper">
          Замечания к предыдущей отправке: {{ latest.feedback }}
        </p>
        <div class="actions">
          <Button
            label="Сохранить черновик"
            severity="secondary"
            :disabled="latest?.status === 'submitted' || latest?.status === 'accepted'"
            :loading="op.busy.value"
            @click="save()"
          /><Button
            type="submit"
            label="Отправить на проверку"
            :disabled="latest?.status === 'submitted' || latest?.status === 'accepted'"
            :loading="op.busy.value"
          />
        </div>
      </form>
    </section>
    <section class="panel" style="margin-top: 20px">
      <h2>История отправок</h2>
      <p v-if="!works.length" class="helper">Работы ещё не отправлены.</p>
      <article v-for="w in works" :key="w.id" style="margin-top: 24px">
        <span class="badge">{{ w.status }}</span>
        <p>{{ w.text }}</p>
        <p v-if="w.feedback" class="helper">Замечание: {{ w.feedback }}</p>
        <p class="helper">{{ formatDateTime(w.created_at) }} · отправка {{ w.id.slice(0, 8) }}</p>
        <form
          v-if="session.staff && w.status === 'submitted'"
          class="form"
          @submit.prevent="review(w, 'accepted')"
        >
          <label>Замечание<input v-model="feedback[w.id]" /></label>
          <div class="actions">
            <Button type="submit" label="Принять" :loading="op.busy.value" /><Button
              label="На доработку"
              severity="secondary"
              :loading="op.busy.value"
              @click="review(w, 'revision')"
            />
          </div>
        </form>
      </article></section
  ></PageState>
</template>
