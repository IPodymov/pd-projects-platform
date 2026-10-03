/** Convert an API timestamp to a datetime-local value in the browser timezone. */
export function toLocalDateTime(value: string): string {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString('ru')
}
