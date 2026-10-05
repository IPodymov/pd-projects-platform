import { fieldLabel, readableMessage, statusMessage } from '@/utils/errors'
import { createApiClient } from '@future/api-client'
export const baseUrl = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export const client = createApiClient(baseUrl)
const revisions = new Map<string, string>()
let csrf = ''
export function setCsrf(value: string) {
  csrf = value
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
    public code = 'request_error',
    public fields: Record<string, string[]> = {},
  ) {
    super(message)
  }
  override toString() {
    return (
      this.message +
      (Object.keys(this.fields).length
        ? ' · ' +
          Object.entries(this.fields)
            .map(([key, values]) => fieldLabel(key) + ': ' + values.join(' · '))
            .join('; ')
        : '')
    )
  }
}
function rootKey(path: string) {
  return path.match(/\/api\/v1\/[^/]+\/[^/]+\//)?.[0] || path.split('?')[0] || ''
}
function remember(path: string, data: unknown) {
  if (!data || typeof data !== 'object') return
  const row = data as Record<string, unknown>
  if (Array.isArray(data)) {
    for (const item of data) remember(path, item)
    return
  }
  if (Array.isArray(row.results)) {
    remember(path, row.results)
    return
  }
  if (typeof row.id === 'string' && typeof row.updated_at === 'string') {
    const resource = path.match(/\/api\/v1\/[^/]+\//)?.[0]
    if (resource) revisions.set(resource + row.id + '/', row.updated_at)
  }
}
function mutationHeaders(method: string, path: string, expected?: string) {
  const headers = new Headers()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    headers.set('X-CSRFToken', csrf)
    const stamp = expected || revisions.get(rootKey(path))
    if (stamp) headers.set('If-Match', stamp)
  }
  return headers
}
function handleResponse(path: string, response: Response, data: unknown) {
  if (response.ok) remember(path, data)
  else if (
    response.status === 401 &&
    data &&
    typeof data === 'object' &&
    'code' in data &&
    data.code === 'not_authenticated'
  )
    window.dispatchEvent(new Event('auth-expired'))
}
export function apiError(value: unknown, status = 400): ApiError {
  const body = value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
  const fields: Record<string, string[]> = {}
  if (body.fields && typeof body.fields === 'object')
    for (const [key, item] of Object.entries(body.fields))
      fields[key] = Array.isArray(item)
        ? item.map((value) => readableMessage(String(value)))
        : [readableMessage(String(item))]
  const code = typeof body.code === 'string' ? body.code : 'request_error'
  const specificMessages: Record<string, string> = {
    authentication_failed: 'Не удалось войти. Проверьте почту и пароль и повторите попытку.',
    duplicate_or_invalid_relation:
      'Такая запись уже существует или связанная запись недоступна. Проверьте данные и выбранные записи.',
  }
  const detail =
    specificMessages[code] ||
    (status >= 500 || [401, 403, 404, 413, 429].includes(status)
      ? statusMessage(status)
      : typeof body.detail === 'string' && /[а-яё]/i.test(body.detail)
        ? body.detail
        : statusMessage(status))
  return new ApiError(
    detail,
    status,
    typeof body.code === 'string' ? body.code : 'request_error',
    fields,
  )
}
client.use({
  onRequest({ request }) {
    const headers = mutationHeaders(request.method, new URL(request.url, location.origin).pathname)
    headers.forEach((value, key) => {
      if (key !== 'if-match' || !request.headers.has(key)) request.headers.set(key, value)
    })
    return request
  },
  async onResponse({ request, response }) {
    const data = await response
      .clone()
      .json()
      .catch(() => null)
    handleResponse(new URL(request.url, location.origin).pathname, response, data)
    return response
  },
})
export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
async function request<T>(
  path: string,
  method = 'GET',
  data?: unknown,
  expected?: string,
): Promise<T> {
  const url = '/api/v1/' + path
  const multipart = data instanceof FormData
  const headers = mutationHeaders(method, url, expected)
  if (!multipart) headers.set('Content-Type', 'application/json')
  const options: RequestInit = {
    method,
    credentials: 'include',
    headers,
  }
  if (method !== 'GET' && method !== 'HEAD' && data !== undefined)
    options.body = multipart ? data : JSON.stringify(data)
  const response = await fetch(baseUrl + url, options)
  const value = response.status === 204 ? undefined : await response.json().catch(() => null)
  handleResponse(url, response, value)
  if (!response.ok) {
    throw apiError(value, response.status)
  }
  return value as T
}
export function apiPage<T>(path: string) {
  return request<Page<T>>(path)
}
// Legacy resource screens collect bounded lookup lists; dedicated lists use apiPage.
export async function api<T>(
  path: string,
  method = 'GET',
  data?: unknown,
  expected?: string,
): Promise<T> {
  const first = await request<T>(path, method, data, expected)
  if (first && typeof first === 'object' && 'results' in first && Array.isArray(first.results)) {
    const page = first as unknown as Page<unknown>
    const rows = [...page.results]
    let next = page.next
    while (next) {
      if (rows.length >= 5000) throw new ApiError('Слишком большой список. Уточните фильтр.')
      const nextUrl = new URL(next, location.origin)
      if (!nextUrl.pathname.startsWith('/api/v1/')) throw new ApiError('Некорректная страница API')
      const more = await request<Page<unknown>>(
        nextUrl.pathname.slice('/api/v1/'.length) + nextUrl.search,
      )
      rows.push(...more.results)
      next = more.next
    }
    return rows as T
  }
  return first
}
export function downloadUrl(path: string) {
  return baseUrl + '/api/v1/' + path
}
