<script setup lang="ts">
import { ref, nextTick } from 'vue'
import Button from 'primevue/button'
const body = defineModel<string>({ required: true }),
  title = defineModel<string>('title', { required: true })
defineProps<{ saved: boolean; busy: boolean }>()
const emit = defineEmits<{ image: [file: File]; attachment: [file: File]; import: [file: File] }>()
const textarea = ref<HTMLTextAreaElement>(),
  imageInput = ref<HTMLInputElement>(),
  attachmentInput = ref<HTMLInputElement>(),
  importInput = ref<HTMLInputElement>()
async function format(prefix: string, suffix = '') {
  const start = textarea.value?.selectionStart || 0,
    end = textarea.value?.selectionEnd || start
  const selected = body.value.slice(start, end)
  body.value =
    body.value.slice(0, start) + prefix + (selected || 'Текст') + suffix + body.value.slice(end)
  await nextTick()
  textarea.value?.focus()
  textarea.value?.setSelectionRange(
    start + prefix.length,
    start + prefix.length + (selected || 'Текст').length,
  )
}
function pick(event: Event, kind: 'image' | 'attachment' | 'import') {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    if (kind === 'image') emit('image', file)
    else if (kind === 'attachment') emit('attachment', file)
    else emit('import', file)
  }
  input.value = ''
}
</script>
<template>
  <section class="panel article-text-editor">
    <label
      >Заголовок<input v-model="title" required maxlength="200" placeholder="Заголовок статьи"
    /></label>
    <div class="article-toolbar" role="group" aria-label="Форматирование текста">
      <Button
        type="button"
        label="Заголовок"
        severity="secondary"
        @click="format('\n## ')"
      /><Button
        type="button"
        label="Жирный"
        severity="secondary"
        @click="format('**', '**')"
      /><Button type="button" label="Список" severity="secondary" @click="format('\n- ')" /><Button
        type="button"
        label="Ссылка"
        severity="secondary"
        @click="format('[', '](https://example.org)')"
      /><Button
        type="button"
        label="Изображение"
        severity="secondary"
        :disabled="!saved || busy"
        @click="imageInput?.click()"
      /><Button
        type="button"
        label="Прикрепить файл"
        severity="secondary"
        :disabled="!saved || busy"
        @click="attachmentInput?.click()"
      /><Button type="button" label="Импорт текста" text @click="importInput?.click()" />
    </div>
    <input
      ref="imageInput"
      class="article-hidden-input"
      type="file"
      accept="image/png,image/jpeg"
      aria-label="Загрузить изображение"
      @change="pick($event, 'image')"
    /><input
      ref="attachmentInput"
      class="article-hidden-input"
      type="file"
      accept=".txt,.md,.csv,.docx,.pptx,.pdf,.png,.jpg,.jpeg"
      aria-label="Прикрепить материал"
      @change="pick($event, 'attachment')"
    /><input
      ref="importInput"
      class="article-hidden-input"
      type="file"
      accept=".md,.txt"
      aria-label="Импорт Markdown или TXT"
      @change="pick($event, 'import')"
    />
    <label
      >Текст<textarea
        ref="textarea"
        v-model="body"
        required
        placeholder="Начните с вопроса: что мне действительно интересно изучать?"
      />
    </label>
    <p v-if="!saved" class="helper">Сохраните черновик, чтобы добавлять изображения и материалы.</p>
    <p class="helper">Поддерживаются Markdown, заголовки, списки, цитаты и блоки кода.</p>
  </section>
</template>
<style src="./ArticleTextEditor.css" scoped></style>
