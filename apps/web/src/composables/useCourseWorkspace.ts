import { errorMessage } from '@/utils/errors'
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, client, apiError } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import type { components } from '@future/api-client'
import type { InjectionKey } from 'vue'
export const courseWorkspaceKey: InjectionKey<ReturnType<typeof useCourseWorkspace>> =
  Symbol('courseWorkspace')
export function useCourseWorkspace() {
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
  type Lesson = components['schemas']['CourseLesson']
  const lessons = ref<Lesson[]>([]),
    lessonForm = ref({ title: '', body: '' })
  const op = useOperation(),
    form = ref({ title: '', instructions: '', criteria: '', due_at: '' })
  useUnsavedChanges(dirty)
  watch(text, () => (dirty.value = true), { flush: 'sync' })
  watch(form, () => (dirty.value = true), { deep: true, flush: 'sync' })
  watch(lessonForm, () => (dirty.value = true), { deep: true, flush: 'sync' })
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
      lessons.value = await api<Lesson[]>('course-lessons/?course=' + id)
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
      if (!ownClass.value)
        ownClass.value =
          myMemberships.value[0]?.classroom ||
          availableClasses.value.find((c) => c.institution === course.value?.institution)?.id ||
          ''
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
  async function createLesson() {
    await op.execute(async () => {
      await api('course-lessons/', 'POST', {
        ...lessonForm.value,
        course: id,
        position: lessons.value.length,
      })
      lessonForm.value = { title: '', body: '' }
      dirty.value = false
      await load()
    }, 'Урок добавлен')
  }
  async function completeLesson(lesson: Lesson) {
    await op.execute(async () => {
      await api('course-lessons/' + lesson.id + '/complete/', 'POST')
      await load()
    }, 'Урок пройден')
  }
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
          ? 'После публикации уроки и задания курса нельзя редактировать. Опубликовать?'
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
  return {
    id,
    session,
    course,
    assignments,
    works,
    enrollments,
    members,
    loading,
    error,
    selected,
    text,
    dirty,
    feedback,
    participant,
    ownClass,
    myMemberships,
    availableClasses,
    lessons,
    lessonForm,
    op,
    form,
    own,
    latest,
    unwrap,
    load,
    createLesson,
    completeLesson,
    createAssignment,
    lifecycle,
    joinCourse,
    enroll,
    save,
    review,
    cancel,
  }
}
