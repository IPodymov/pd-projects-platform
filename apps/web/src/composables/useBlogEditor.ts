import { onMounted, ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, downloadUrl } from '@/api'
import { useSession } from '@/stores/session'
import { useOperation } from '@/composables/useOperation'
import { useUnsavedChanges } from '@/composables/useUnsavedChanges'
import { errorMessage } from '@/utils/errors'
import type { ArticleForm, ArticleAttachment } from '@/types/blog'
import type { components } from '@future/api-client'
export function useBlogEditor() {
  const route = useRoute(),
    router = useRouter(),
    session = useSession(),
    op = useOperation()
  const id = ref(String(route.params.id || '')),
    revision = ref(''),
    loading = ref(true),
    error = ref(''),
    preview = ref(false),
    dirty = ref(false)
  const topics = ref<components['schemas']['Topic'][]>([]),
    attachments = ref<ArticleAttachment[]>([])
  const form = ref<ArticleForm>({
    title: '',
    slug: 'article-' + crypto.randomUUID(),
    body: '',
    lead: '',
    topic: '',
    visibility: 'public',
  })
  const allowed = computed(
    () => !!session.user?.platform_admin || !!session.user?.roles.includes('curator'),
  )
  watch(
    form,
    () => {
      dirty.value = true
    },
    { deep: true, flush: 'sync' },
  )
  useUnsavedChanges(dirty)
  async function load() {
    loading.value = true
    error.value = ''
    try {
      if (!allowed.value)
        throw Error('Создание статей доступно кураторам и администратору платформы')
      topics.value = await api<components['schemas']['Topic'][]>('topics/')
      if (id.value) {
        const article = await api<components['schemas']['Publication']>(
          'publications/' + id.value + '/',
        )
        if (
          article.status !== 'draft' ||
          (!session.user?.platform_admin && article.author !== session.user?.id)
        )
          throw Error('Редактировать можно только собственный черновик')
        form.value = {
          title: article.title,
          slug: article.slug,
          body: article.body,
          lead: article.lead || '',
          topic: article.topic,
          visibility: article.visibility || 'public' || 'public',
        }
        revision.value = article.updated_at || ''
        attachments.value = await api<ArticleAttachment[]>(
          'publications/' + id.value + '/attachments/',
        )
      } else form.value.topic = topics.value[0]?.code || ''
      dirty.value = false
    } catch (e) {
      error.value = errorMessage(e)
    } finally {
      loading.value = false
    }
  }
  async function persist() {
    if (!form.value.title.trim() || !form.value.body.trim() || !form.value.topic)
      throw Error('Заполните заголовок, текст и рубрику статьи')
    const article = await api<components['schemas']['Publication']>(
      'publications/' + (id.value ? id.value + '/' : ''),
      id.value ? 'PATCH' : 'POST',
      form.value,
      revision.value || undefined,
    )
    id.value = article.id
    revision.value = article.updated_at || ''
    dirty.value = false
    return article
  }
  async function save() {
    await op.execute(async () => {
      await persist()
      await router.replace('/blog/' + id.value + '/edit')
    }, 'Черновик сохранён')
  }
  async function publish() {
    await op.execute(async () => {
      await persist()
      await api(
        'publications/' + id.value + '/transition/',
        'POST',
        { status: 'published' },
        revision.value,
      )
      dirty.value = false
      await router.push('/articles/' + id.value)
    }, 'Статья опубликована')
  }
  async function uploadImage(file: File) {
    await op.execute(async () => {
      if (!id.value) throw Error('Сначала сохраните черновик')
      const data = new FormData()
      data.set('file', file)
      const result = await api<{ path: string }>(
        'publications/' + id.value + '/upload_image/',
        'POST',
        data,
      )
      form.value.body += '\n\n![Изображение](' + downloadUrl(result.path) + ')\n'
    }, 'Изображение добавлено. Сохраните текст статьи.')
  }
  async function uploadAttachment(file: File) {
    await op.execute(async () => {
      if (!id.value) throw Error('Сначала сохраните черновик')
      const data = new FormData()
      data.set('file', file)
      attachments.value.push(
        await api<ArticleAttachment>(
          'publications/' + id.value + '/upload_attachment/',
          'POST',
          data,
        ),
      )
    }, 'Материал прикреплён')
  }
  async function removeAttachment(attachment: string) {
    await op.execute(async () => {
      await api('publications/' + id.value + '/remove_attachment/', 'POST', { attachment })
      attachments.value = attachments.value.filter((a) => a.id !== attachment)
    }, 'Материал убран из статьи')
  }
  async function importText(file: File) {
    await op.execute(async () => {
      if (file.size > 1024 * 1024 || !/\.(md|txt)$/i.test(file.name))
        throw Error('Выберите Markdown или TXT до 1 МБ')
      form.value.body = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer())
    }, 'Текст импортирован. Сохраните черновик.')
  }
  onMounted(load)
  return {
    id,
    loading,
    error,
    preview,
    dirty,
    topics,
    attachments,
    form,
    allowed,
    op,
    load,
    save,
    publish,
    uploadImage,
    uploadAttachment,
    removeAttachment,
    importText,
  }
}
