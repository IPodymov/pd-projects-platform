<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import BlogCard from '@/components/blog/BlogCard/BlogCard.vue'
import PageState from '@/components/common/PageState/PageState.vue'
import FormFeedback from '@/components/common/FormFeedback/FormFeedback.vue'
import { api } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import { errorMessage } from '@/utils/errors'
import type { components } from '@future/api-client'
type Article = components['schemas']['Publication']
const session = useSession(),
  op = useOperation(),
  rows = ref<Article[]>([]),
  topics = ref<components['schemas']['Topic'][]>([]),
  loading = ref(true),
  error = ref(''),
  search = ref(''),
  topic = ref('')
const canWrite = computed(
  () => !!session.user?.platform_admin || !!session.user?.roles.includes('curator'),
)
const filtered = computed(() =>
  rows.value.filter(
    (row) =>
      (!topic.value || row.topic === topic.value) &&
      (row.title + ' ' + row.lead).toLowerCase().includes(search.value.toLowerCase()),
  ),
)
const featured = computed(
  () => filtered.value.find((row) => row.status === 'published') || filtered.value[0],
)
const otherArticles = computed(() => filtered.value.filter((row) => row.id !== featured.value?.id))
function canEdit(row: Article) {
  return !!session.user?.platform_admin || (canWrite.value && row.author === session.user?.id)
}
function topicTitle(code: string) {
  return topics.value.find((t) => t.code === code)?.title || code
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    ;[rows.value, topics.value] = await Promise.all([
      api<Article[]>('publications/'),
      api<components['schemas']['Topic'][]>('topics/'),
    ])
    rows.value.sort((a, b) => b.created_at.localeCompare(a.created_at))
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
async function archive(id: string) {
  if (!window.confirm('Архивировать статью?')) return
  await op.execute(async () => {
    await api('publications/' + id + '/transition/', 'POST', { status: 'archived' })
    await load()
  }, 'Статья архивирована')
}
onMounted(load)
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>Блог и полезные материалы</h1>
      <p class="subtitle">Методички, шаблоны и советы по проектной деятельности</p>
    </div>
    <div class="actions">
      <input
        v-model="search"
        class="blog-search"
        type="search"
        placeholder="Поиск по статьям"
        aria-label="Поиск по статьям"
      /><RouterLink v-if="canWrite" to="/blog/new"><Button label="Новая статья" /></RouterLink>
    </div>
  </div>
  <FormFeedback :error="op.error.value" :fields="op.fields.value" :success="op.success.value" />
  <div class="blog-filters" role="group" aria-label="Рубрики">
    <button :class="{ active: !topic }" @click="topic = ''">Все</button
    ><button
      v-for="t in topics"
      :key="t.code"
      :class="{ active: topic === t.code }"
      @click="topic = t.code"
    >
      {{ t.title }}
    </button>
  </div>
  <PageState :loading="loading" :error="error" :empty="!filtered.length" @retry="load"
    ><BlogCard
      v-if="featured"
      :article="featured"
      :topic="topicTitle(featured.topic)"
      featured
      :can-edit="canEdit(featured)"
      @archive="archive" />
    <div class="grid">
      <BlogCard
        v-for="article in otherArticles"
        :key="article.id"
        :article="article"
        :topic="topicTitle(article.topic)"
        :can-edit="canEdit(article)"
        @archive="archive"
      /></div
  ></PageState>
</template>
<style src="./BlogView.css" scoped></style>
