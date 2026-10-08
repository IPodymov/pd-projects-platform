<script setup lang="ts">
import Button from 'primevue/button'
import { downloadUrl } from '@/api'
import type { ArticleAttachment } from '@/types/blog'
defineProps<{
  articleId: string
  attachments: ArticleAttachment[]
  editable?: boolean
  busy?: boolean
}>()
defineEmits<{ remove: [id: string] }>()
</script>
<template>
  <section class="panel article-attachments">
    <h2>Прикреплённые материалы</h2>
    <p v-if="!attachments.length" class="helper">Материалы ещё не добавлены.</p>
    <div v-for="file in attachments" :key="file.id" class="attachment-row">
      <div>
        <a :href="downloadUrl('publications/' + articleId + '/attachment/?attachment=' + file.id)"
          ><strong>{{ file.filename }}</strong></a
        ><small>{{ Math.ceil(file.size / 1024) }} КБ</small>
      </div>
      <Button
        v-if="editable"
        label="Убрать"
        severity="secondary"
        :disabled="busy"
        @click="$emit('remove', file.id)"
      /><a
        v-else
        :href="downloadUrl('publications/' + articleId + '/attachment/?attachment=' + file.id)"
        >Скачать</a
      >
    </div>
  </section>
</template>
<style src="./ArticleAttachments.css" scoped></style>
