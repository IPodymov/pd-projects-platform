<script setup lang="ts">
import { inject } from 'vue'
import { projectWorkspaceKey } from '@/composables/useProjectWorkspace'
import Button from 'primevue/button'
import FileDropzone from '@/components/common/FileDropzone/FileDropzone.vue'
import FilePreview from '@/components/common/FilePreview/FilePreview.vue'
import FormFeedback from '@/components/common/FormFeedback/FormFeedback.vue'
import DiffLine from '@/components/common/DiffLine/DiffLine.vue'
import { api } from '@/api'
import { downloadUrl } from '@/api'
import { formatDateTime } from '@/utils/dateTime'
const workspace = inject(projectWorkspaceKey)
if (!workspace) throw new Error('Project workspace is unavailable')
const {
  docs,
  busy,
  docTitle,
  selectedDoc,
  file,
  old,
  next,
  comparison,
  lines,
  id,
  visibleVersions,
  run,
  upload,
  diff,
  restoreVersion,
} = workspace
</script>
<template>
  <section id="project-files" class="panel" data-layout="projectview-style-6">
    <h2>Файлы проекта</h2>
    <form
      class="form"
      @submit.prevent="run(() => api('documents/', 'POST', { project: id, title: docTitle }))"
    >
      <label>Название нового документа<input v-model="docTitle" required /></label
      ><Button type="submit" label="Создать документ" :loading="busy" />
    </form>
    <div class="filters" data-layout="projectview-style-7">
      <select v-model="selectedDoc" aria-label="Документ">
        <option v-for="d in docs" :key="d.id" :value="d.id">{{ d.title }}</option></select
      ><Button
        label="Загрузить версию"
        :disabled="!file || !selectedDoc"
        :loading="busy"
        @click="upload"
      />
    </div>
    <FileDropzone :filename="file?.name" :disabled="busy" @select="file = $event" />
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
              <FilePreview
                :path="'document-versions/' + v.id + '/download/'"
                :filename="v.filename"
              />
              <a :href="downloadUrl('document-versions/' + v.id + '/download/')">Скачать ↓</a
              ><Button label="Восстановить" text @click="restoreVersion(v.id)" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="helper">
      PDF и изображения доступны для скачивания. Восстановление создаёт новую версию. Для DOCX/PPTX
      сравнивается извлечённый текст, без визуального сравнения оформления.
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
    </div>
  </section>
</template>
<style src="./ProjectFiles.css" scoped></style>
