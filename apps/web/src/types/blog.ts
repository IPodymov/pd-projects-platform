export interface ArticleForm {
  title: string
  slug: string
  body: string
  lead: string
  topic: string
  visibility: string
}
export interface ArticleAttachment {
  id: string
  filename: string
  size: number
}
export function articleCover(body: string): string {
  const url = body.match(/!\[[^\]]*\]\(([^)\s]+)\)/)?.[1] || ''
  return /^(https?:\/\/|\/(?!\/))/.test(url) ? url : ''
}
