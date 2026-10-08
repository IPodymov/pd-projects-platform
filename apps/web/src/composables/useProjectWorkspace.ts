import { errorMessage } from '@/utils/errors'
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useComparison } from '@/composables/useComparison'
import { useOperation } from '@/composables/useOperation'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { api } from '@/api'
import { useSession } from '@/stores/session'
import type { components } from '@future/api-client'
import type { InjectionKey } from 'vue'

export const projectWorkspaceKey: InjectionKey<ReturnType<typeof useProjectWorkspace>> =
  Symbol('projectWorkspace')
export function useProjectWorkspace() {
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
  return {
    route,
    session,
    p,
    docs,
    versions,
    tasks,
    submissions,
    members,
    chosenMember,
    error,
    loading,
    busy,
    docTitle,
    selectedDoc,
    file,
    old,
    next,
    draft,
    previous,
    dirty,
    milestones,
    stageForm,
    taskTitle,
    taskDue,
    taskMilestone,
    criteria,
    selectedTask,
    work,
    feedback,
    reviewFeedback,
    team,
    memberRole,
    editingWork,
    comparison,
    operation,
    lines,
    id,
    visibleVersions,
    load,
    run,
    pick,
    upload,
    diff,
    sendWork,
    restoreVersion,
    editDraft,
    revise,
    projectActions,
    projectTransition,
    stageTransition,
    createStage,
  }
}
