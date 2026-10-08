<script setup lang="ts">
import { provide } from 'vue'
import { useProjectWorkspace, projectWorkspaceKey } from '@/composables/useProjectWorkspace'
import Button from 'primevue/button'
import PageState from '@/components/common/PageState/PageState.vue'
import FormFeedback from '@/components/common/FormFeedback/FormFeedback.vue'
import StatusBadge from '@/components/common/StatusBadge/StatusBadge.vue'
import ProjectGit from '@/components/project/ProjectGit/ProjectGit.vue'
import ProjectHistory from '@/components/project/ProjectHistory/ProjectHistory.vue'
import ProjectTeam from '@/components/project/ProjectTeam/ProjectTeam.vue'
import ProjectTasks from '@/components/project/ProjectTasks/ProjectTasks.vue'
import ProjectReview from '@/components/project/ProjectReview/ProjectReview.vue'
import ProjectSubmissions from '@/components/project/ProjectSubmissions/ProjectSubmissions.vue'
import ProjectFiles from '@/components/project/ProjectFiles/ProjectFiles.vue'
const workspace = useProjectWorkspace()
provide(projectWorkspaceKey, workspace)
const { p, operation, loading, error, load, id, milestones } = workspace
function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">Мои проекты / {{ p?.classroom_name }}</p>
      <h1>{{ p?.title || 'Проект' }}</h1>
      <p class="subtitle">{{ p?.description }}</p>
    </div>
    <div class="actions">
      <Button
        label="Ссылка на GitHub"
        severity="secondary"
        @click="scrollTo('project-git')"
      /><Button label="Загрузить файл" @click="scrollTo('project-files')" />
    </div>
  </div>
  <FormFeedback
    :error="operation.error.value"
    :fields="operation.fields.value"
    :success="operation.success.value"
  />
  <PageState :loading="loading" :error="error" @retry="load">
    <div class="project-status">
      <StatusBadge v-if="p" :status="p.status" /><span class="helper"
        >Принято {{ p?.progress || 0 }}% заданий</span
      >
    </div>
    <div v-if="milestones.length" class="panel project-steps">
      <div v-for="(m, index) in milestones" :key="m.id">
        <span>{{ index + 1 }}. {{ m.title }}</span
        ><StatusBadge :status="m.status" />
      </div>
    </div>
    <div class="project-columns">
      <div class="project-primary">
        <ProjectFiles />
        <div id="project-git"><ProjectGit :project="id" /></div>
        <details class="panel">
          <summary>Команда и задания</summary>
          <ProjectTeam /><ProjectTasks />
        </details>
        <ProjectSubmissions />
      </div>
      <div class="project-secondary"><ProjectHistory /><ProjectReview /></div>
    </div>
  </PageState>
</template>
<style src="./ProjectView.css" scoped></style>
