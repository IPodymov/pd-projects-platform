<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api'
import { errorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/dateTime'
import PageState from '@/components/common/PageState/PageState.vue'
import ArticleBody from '@/components/common/ArticleBody/ArticleBody.vue'
import ArticleAttachments from '@/components/blog/ArticleAttachments/ArticleAttachments.vue'
import type { ArticleAttachment } from '@/types/blog'
import type { components } from '@future/api-client'
const attachments = ref<ArticleAttachment[]>([])
const route = useRoute(),
  article = ref<components['schemas']['Publication']>(),
  loading = ref(false),
  error = ref('')
async function load() {
  loading.value = true
  error.value = ''
  article.value = undefined
  try {
    article.value = await api('publications/' + String(route.params.id) + '/')
    attachments.value = await api('publications/' + String(route.params.id) + '/attachments/')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
watch(() => route.params.id, load, { immediate: true })
</script>
<template>
  <RouterLink to="/manage/publications">← Журнал кураторов</RouterLink>
  <PageState :loading="loading" :error="error" @retry="load">
    <article v-if="article" class="panel" data-layout="articleview-style-1">
      <p class="eyebrow">{{ article.topic }} · {{ article.status }}</p>
      <h1>{{ article.title }}</h1>
      <p class="helper">
        {{ article.author_name || 'Редакция платформы' }} ·
        {{ formatDateTime(article.created_at) }} ·
        {{ Math.max(1, Math.ceil(article.body.split(/\s+/).length / 200)) }} мин чтения
      </p>
      <p class="subtitle">{{ article.lead }}</p>
      <ArticleBody :body="article.body" />
      <ArticleAttachments
        v-if="attachments.length"
        :article-id="article.id"
        :attachments="attachments"
      />
    </article>
  </PageState>
</template>
<style src="./ArticleView.css" scoped></style>
