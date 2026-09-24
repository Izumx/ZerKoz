import type { HistoryItem } from './api'
import type { useI18n } from './i18n'

type I18n = ReturnType<typeof useI18n>

const DAY = 86_400_000

export function todayISO(): string {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
}

export function addDaysISO(days: number): string {
  const d = new Date(`${todayISO()}T00:00:00`)
  d.setDate(d.getDate() + days)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
}

/** Дней до срока: >0 — осталось, <0 — просрочено. */
export function daysUntil(deadline: string): number {
  return Math.round((Date.parse(`${deadline}T00:00:00`) - Date.parse(`${todayISO()}T00:00:00`)) / DAY)
}

export function deadlineLabel(i: I18n, deadline: string): string {
  const n = daysUntil(deadline)
  if (n === 0) return i.t('dueToday')
  return n > 0 ? i.t('daysLeft', { n }) : i.t('daysOverdue', { n: -n })
}

export function formatDate(iso: string, lang: string): string {
  return new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).toLocaleDateString(lang === 'kz' ? 'kk-KZ' : 'ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function formatDateTime(iso: string, lang: string): string {
  return new Date(iso).toLocaleString(lang === 'kz' ? 'kk-KZ' : 'ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function timeAgo(i: I18n, iso: string): string {
  const minutes = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 60_000))
  if (minutes < 1) return i.t('justNow')
  if (minutes < 60) return i.t('minAgo', { n: minutes })
  if (minutes < 60 * 24) return i.t('hAgo', { n: Math.round(minutes / 60) })
  return i.t('dAgo', { n: Math.round(minutes / 1440) })
}

export function formatArea(ha: number): string {
  return ha < 1 ? ha.toFixed(2) : ha.toFixed(1)
}

export function historyText(i: I18n, item: HistoryItem): string {
  const p = item.payload
  switch (item.action) {
    case 'created':
      return i.t('hCreated')
    case 'status':
      return i.t('hStatus', {
        from: i.d.signalStatus[p.from as keyof typeof i.d.signalStatus] ?? String(p.from),
        to: i.d.signalStatus[p.to as keyof typeof i.d.signalStatus] ?? String(p.to),
      })
    case 'lifecycle':
      return i.t('hLifecycle', {
        from: i.d.lifecycle[p.from as keyof typeof i.d.lifecycle] ?? String(p.from),
        to: i.d.lifecycle[p.to as keyof typeof i.d.lifecycle] ?? String(p.to),
      })
    case 'photos':
      return i.t('hPhotos', { count: Number(p.count) })
    case 'duplicate':
      return i.t('hDuplicate', { code: String(p.code) })
    case 'ndvi_low':
      return i.t('hNdviLow', { peak: Number(p.peak).toFixed(2) })
    default:
      return i.t('hUpdated')
  }
}
