<script setup lang="ts">
import { computed } from 'vue'
import { articleCover } from '@/types/blog'
import type { ArticleForm } from '@/types/blog'
import type { components } from '@future/api-client'
const form = defineModel<ArticleForm>({ required: true })
defineProps<{ topics: components['schemas']['Topic'][] }>()
const cover = computed(() => articleCover(form.value.body))
</script>
<template>
  <section class="panel article-settings">
    <h2>Настройки</h2>
    <label
      >Рубрика<select v-model="form.topic" required>
        <option value="" disabled>Выберите…</option>
        <option v-for="topic in topics" :key="topic.code" :value="topic.code">
          {{ topic.title }}
        </option>
      </select></label
    ><label
      >Кому видна<select v-model="form.visibility">
        <option value="public">Все пользователи</option>
        <option value="authenticated">Участники платформы</option>
      </select></label
    ><label>Постоянный адрес<input v-model="form.slug" required pattern="[a-zA-Z0-9_-]+" /></label
    ><label>Вступление для ленты<textarea v-model="form.lead" maxlength="500" /></label>
    <div class="article-cover">
      <img v-if="cover" :src="cover" alt="Обложка статьи" /><span v-else>Обложка статьи</span>
    </div>
    <p class="helper">Первое изображение текста отображается в ленте как обложка.</p>
  </section>
</template>
<style src="./ArticleSettings.css" scoped></style>
