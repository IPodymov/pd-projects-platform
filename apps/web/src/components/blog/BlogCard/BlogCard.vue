<script setup lang="ts">
import Button from 'primevue/button'
import StatusBadge from '@/components/common/StatusBadge/StatusBadge.vue'
import { articleCover } from '@/types/blog'
import type { components } from '@future/api-client'
defineProps<{
  article: components['schemas']['Publication']
  topic: string
  featured?: boolean
  canEdit: boolean
}>()
defineEmits<{ archive: [id: string] }>()
</script>
<template>
  <article class="panel blog-card" :class="{ 'blog-card--featured': featured }">
    <RouterLink :to="'/articles/' + article.id" class="blog-cover" tabindex="-1" aria-hidden="true"
      ><img
        v-if="articleCover(article.body)"
        :src="articleCover(article.body)"
        alt=""
        loading="lazy"
    /></RouterLink>
    <div class="blog-card-content">
      <span v-if="featured" class="blog-recommendation">Рекомендуем</span
      ><span v-else class="blog-topic">{{ topic }}</span>
      <h2>
        <RouterLink :to="'/articles/' + article.id">{{ article.title }}</RouterLink>
      </h2>
      <p>{{ article.lead || article.body.slice(0, 160) }}</p>
      <span class="helper">{{ article.author_name || 'Редакция' }}</span>
      <div class="actions">
        <RouterLink :to="'/articles/' + article.id"
          ><Button label="Читать" severity="secondary" /></RouterLink
        ><StatusBadge v-if="article.status !== 'published'" :status="article.status" /><RouterLink
          v-if="canEdit && article.status === 'draft'"
          :to="'/blog/' + article.id + '/edit'"
          ><Button label="Редактировать" text /></RouterLink
        ><Button
          v-if="canEdit && article.status === 'published'"
          label="В архив"
          text
          @click="$emit('archive', article.id)"
        />
      </div>
    </div>
  </article>
</template>
<style src="./BlogCard.css" scoped></style>
