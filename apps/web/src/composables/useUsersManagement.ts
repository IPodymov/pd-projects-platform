import type { InjectionKey } from 'vue'

import { computed, ref, onMounted } from 'vue'
import { api, apiPage } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { errorMessage } from '@/utils/errors'
import type { components } from '@future/api-client'
type Membership = components['schemas']['Membership']
type Classroom = components['schemas']['Classroom']
type Course = components['schemas']['Course']
type Project = components['schemas']['Project']
type Enrollment = components['schemas']['Enrollment']
type Staff = components['schemas']['Staff']
type ManagedUser = {
  id: number
  email: string
  name: string
  display_name: string
  date_of_birth: string | null
  is_active: boolean
  email_verified_at: string | null
  updated_at: string
  memberships: Membership[]
  enrollments: Enrollment[]
  projects: Project[]
  staff_assignments: Staff[]
}
export const usersManagementKey: InjectionKey<ReturnType<typeof useUsersManagement>> =
  Symbol('usersManagement')
export function useUsersManagement() {
  const session = useSession(),
    op = useOperation()
  const rows = ref<ManagedUser[]>([]),
    selected = ref<ManagedUser>(),
    classes = ref<Classroom[]>([]),
    courses = ref<Course[]>([]),
    projects = ref<Project[]>([])
  const loading = ref(false),
    error = ref(''),
    search = ref(''),
    page = ref(1),
    count = ref(0),
    dirty = ref(false)
  const profile = ref({ display_name: '', date_of_birth: '', is_active: true })
  const attach = ref({ email: '', classroom: '' }),
    classForm = ref({ membership: '', classroom: '' }),
    courseForm = ref({ course: '', classroom: '' }),
    projectForm = ref({ project: '', role: 'member' }),
    newProject = ref({ title: '', description: '', classroom: '' })
  useUnsavedChanges(dirty)
  const activeMemberships = computed(
    () => selected.value?.memberships.filter((m) => !m.ended_at) || [],
  )
  const studentClasses = computed(() =>
    classes.value.filter((c) => activeMemberships.value.some((m) => m.classroom === c.id)),
  )
  const availableProjects = computed(() =>
    projects.value.filter(
      (p) =>
        studentClasses.value.some((c) => c.id === p.classroom) &&
        !['accepted', 'archived'].includes(p.status) &&
        !selected.value?.projects.some((existing) => existing.id === p.id),
    ),
  )
  const availableCourses = computed(() =>
    courses.value.filter(
      (c) =>
        c.status === 'published' &&
        studentClasses.value.some((cl) => cl.institution === c.institution) &&
        !selected.value?.enrollments.some((e) => e.course === c.id && e.status !== 'cancelled'),
    ),
  )
  const courseClasses = computed(() =>
    studentClasses.value.filter(
      (c) =>
        c.institution ===
        courses.value.find((course) => course.id === courseForm.value.course)?.institution,
    ),
  )
  const transferClasses = computed(() => {
    const current = selected.value?.memberships.find((m) => m.id === classForm.value.membership)
    const institution = classes.value.find((c) => c.id === current?.classroom)?.institution
    return classes.value.filter((c) => !institution || c.institution === institution)
  })
  function classroomName(id: string) {
    const c = classes.value.find((c) => c.id === id)
    return c ? c.name + ' · ' + c.academic_year : id
  }
  function choose(user: ManagedUser) {
    if (dirty.value && !window.confirm('Отменить несохранённые изменения профиля?')) return
    selected.value = user
    profile.value = {
      display_name: user.display_name || user.name,
      date_of_birth: user.date_of_birth || '',
      is_active: user.is_active,
    }
    classForm.value = {
      membership: user.memberships.find((m) => !m.ended_at)?.id || '',
      classroom: '',
    }
    courseForm.value = { course: '', classroom: '' }
    projectForm.value = { project: '', role: 'member' }
    newProject.value = { title: '', description: '', classroom: '' }
    dirty.value = false
  }
  async function loadRows() {
    const result = await apiPage<ManagedUser>(
      'users/?page=' + page.value + '&search=' + encodeURIComponent(search.value),
    )
    rows.value = result.results
    count.value = result.count
  }
  async function load() {
    loading.value = true
    error.value = ''
    try {
      await Promise.all([
        loadRows(),
        (async () => {
          ;[classes.value, courses.value, projects.value] = await Promise.all([
            api<Classroom[]>('classrooms/'),
            api<Course[]>('courses/'),
            api<Project[]>('projects/'),
          ])
        })(),
      ])
    } catch (e) {
      error.value = errorMessage(e)
    } finally {
      loading.value = false
    }
  }
  onMounted(load)
  async function find() {
    page.value = 1
    await load()
  }
  async function changePage(delta: number) {
    page.value += delta
    await load()
  }
  async function assign(action: string, body: unknown, message: string) {
    await op.execute(async () => {
      if (dirty.value) throw Error('Сначала сохраните изменения профиля')
      if (!selected.value) return
      const result = await api<ManagedUser>(
        'users/' + selected.value.id + '/' + action + '/',
        'POST',
        body,
        selected.value.updated_at,
      )
      choose(result)
      await load()
    }, message)
  }
  async function saveProfile() {
    await op.execute(async () => {
      if (!selected.value) return
      const body = {
        display_name: profile.value.display_name,
        date_of_birth: profile.value.date_of_birth || null,
        ...(session.user?.platform_admin ? { is_active: profile.value.is_active } : {}),
      }
      const result = await api<ManagedUser>(
        'users/' + selected.value.id + '/',
        'PATCH',
        body,
        selected.value.updated_at,
      )
      dirty.value = false
      choose(result)
      await loadRows()
      if (result.id === session.user?.id) await session.refresh()
    }, 'Учётная запись обновлена')
  }
  async function addStudent() {
    await op.execute(async () => {
      if (dirty.value) throw Error('Сначала сохраните изменения профиля')
      const result = await api<ManagedUser>('users/add_student/', 'POST', attach.value)
      attach.value = { email: '', classroom: '' }
      dirty.value = false
      choose(result)
      await load()
    }, 'Пользователь добавлен в класс')
  }
  async function refreshUser() {
    await op.execute(async () => {
      if (!selected.value) return
      choose(await api<ManagedUser>('users/' + selected.value.id + '/'))
    }, 'Карточка обновлена')
  }

  return {
    session,
    op,
    rows,
    selected,
    classes,
    courses,
    projects,
    loading,
    error,
    search,
    page,
    count,
    dirty,
    profile,
    attach,
    classForm,
    courseForm,
    projectForm,
    newProject,
    activeMemberships,
    studentClasses,
    availableProjects,
    availableCourses,
    courseClasses,
    transferClasses,
    classroomName,
    choose,
    load,
    find,
    changePage,
    assign,
    saveProfile,
    addStudent,
    refreshUser,
  }
}
