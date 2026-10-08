<script setup lang="ts">
import Button from 'primevue/button'
import PageState from '@/components/common/PageState/PageState.vue'
import FormFeedback from '@/components/common/FormFeedback/FormFeedback.vue'
import ArticleBody from '@/components/common/ArticleBody/ArticleBody.vue'
import ArticleTextEditor from '@/components/blog/ArticleTextEditor/ArticleTextEditor.vue'
import ArticleSettings from '@/components/blog/ArticleSettings/ArticleSettings.vue'
import ArticleAttachments from '@/components/blog/ArticleAttachments/ArticleAttachments.vue'
import { useBlogEditor } from '@/composables/useBlogEditor'
const {
  id,
  loading,
  error,
  preview,
  topics,
  attachments,
  form,
  op,
  load,
  save,
  publish,
  uploadImage,
  uploadAttachment,
  removeAttachment,
  importText,
} = useBlogEditor()
</script>
<template>
  <div class="page-heading">
    <div>
      <p class="eyebrow">
        <RouterLink to="/manage/publications">Блог</RouterLink> /
        {{ id ? 'Черновик' : 'Новая статья' }}
      </p>
      <h1>Редактор статьи</h1>
    </div>
    <div class="actions">
      <Button
        label="Предпросмотр"
        severity="secondary"
        :disabled="loading || !!error"
        @click="preview = !preview"
      /><Button
        label="Сохранить черновик"
        severity="secondary"
        :loading="op.busy.value"
        :disabled="loading || !!error"
        @click="save"
      /><Button
        label="Опубликовать"
        :loading="op.busy.value"
        :disabled="loading || !!error"
        @click="publish"
      />
    </div>
  </div>
  <FormFeedback
    :error="op.error.value"
    :fields="op.fields.value"
    :success="op.success.value"
  /><PageState :loading="loading" :error="error" @retry="load"
    ><div class="blog-editor-columns">
      <div>
        <article v-if="preview" class="panel">
          <h1>{{ form.title }}</h1>
          <p>{{ form.lead }}</p>
          <ArticleBody :body="form.body" />
        </article>
        <ArticleTextEditor
          v-else
          v-model="form.body"
          v-model:title="form.title"
          :saved="!!id"
          :busy="op.busy.value"
          @image="uploadImage"
          @attachment="uploadAttachment"
          @import="importText"
        />
      </div>
      <aside class="blog-editor-settings">
        <ArticleSettings v-model="form" :topics="topics" /><ArticleAttachments
          :article-id="id"
          :attachments="attachments"
          editable
          :busy="op.busy.value"
          @remove="removeAttachment"
        />
      </aside></div
  ></PageState>
</template>
<style src="./BlogEditorView.css" scoped></style>
