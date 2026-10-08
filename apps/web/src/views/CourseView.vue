<script setup lang="ts">
import { provide, ref } from 'vue'
import { useCourseWorkspace, courseWorkspaceKey } from '@/composables/useCourseWorkspace'
import Button from 'primevue/button'
import PageState from '@/components/common/PageState/PageState.vue'
import StatusBadge from '@/components/common/StatusBadge/StatusBadge.vue'
import FormFeedback from '@/components/common/FormFeedback/FormFeedback.vue'
import CourseMaterials from '@/components/course/CourseMaterials/CourseMaterials.vue'
import CourseOutline from '@/components/course/CourseOutline/CourseOutline.vue'
import CourseBuilder from '@/components/course/CourseBuilder/CourseBuilder.vue'
import CourseParticipants from '@/components/course/CourseParticipants/CourseParticipants.vue'
import CourseLessons from '@/components/course/CourseLessons/CourseLessons.vue'
import CourseAssignments from '@/components/course/CourseAssignments/CourseAssignments.vue'
import CourseJoin from '@/components/course/CourseJoin/CourseJoin.vue'
import CourseWork from '@/components/course/CourseWork/CourseWork.vue'
import CourseWorkHistory from '@/components/course/CourseWorkHistory/CourseWorkHistory.vue'
const workspace = useCourseWorkspace()
provide(courseWorkspaceKey, workspace)
const { course, session, op, loading, error, load, lifecycle, id, own } = workspace
const preview = ref(false)
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">Курсы / {{ course?.status === 'draft' ? 'Конструктор' : 'Обучение' }}</p>
      <h1>{{ course?.title || 'Курс' }}</h1>
      <StatusBadge v-if="course" :status="course.status" />
      <p class="subtitle course-description">{{ course?.description }}</p>
    </div>
    <div v-if="session.managesCourses" class="actions">
      <Button label="Предпросмотр" severity="secondary" @click="preview = !preview" /><Button
        v-if="course?.status === 'draft'"
        label="Опубликовать"
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
  </div>
  <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
  <PageState :loading="loading" :error="error" @retry="load"
    ><div class="course-columns">
      <aside class="course-structure"><CourseOutline /><CourseJoin /></aside>
      <div class="course-content">
        <CourseBuilder v-if="!preview" /><CourseLessons /><CourseAssignments /><CourseMaterials
          v-if="course"
          :course="id"
          :can-upload="
            course.status !== 'archived' && (session.managesCourses || own?.status === 'active')
          "
        /><CourseWork /><CourseWorkHistory /><CourseParticipants />
      </div></div
  ></PageState>
</template>
<style src="./CourseView.css" scoped></style>
