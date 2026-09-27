import { useRef, useState } from 'react'
import type { HistoryItem, Photo } from '../api'
import { formatDateTime, historyText } from '../format'
import { useI18n } from '../i18n'

export function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="section">
      <header className="section__head">
        <h3>{title}</h3>
        {aside}
      </header>
      {children}
    </section>
  )
}

export function Photos({ photos, onUpload }: { photos: Photo[]; onUpload?: (files: File[]) => Promise<void> }) {
  const i = useI18n()
  const [open, setOpen] = useState<Photo | null>(null)
  const [busy, setBusy] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  const upload = onUpload && (
    <>
      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        hidden
        onChange={async (e) => {
          const files = Array.from(e.target.files ?? [])
          e.target.value = ''
          if (!files.length) return
          setBusy(true)
          try {
            await onUpload(files)
          } finally {
            setBusy(false)
          }
        }}
      />
      <button className="btn btn--ghost btn--sm" disabled={busy} onClick={() => input.current?.click()}>
        {busy ? i.t('uploading') : `＋ ${i.t('uploadPhotos')}`}
      </button>
    </>
  )

  return (
    <Section title={i.t('photos')} aside={upload}>
      {photos.length ? (
        <div className="photos">
          {photos.map((p) => (
            <figure key={p.id} className="photo-cell">
              <button className="photo" onClick={() => setOpen(p)}>
                <img src={p.url} alt="" loading="lazy" />
                <span className={`photo__tag photo__tag--${p.source}`}>
                  {p.source === 'citizen' ? i.t('byCitizen') : i.t('byInspector')}
                </span>
              </button>
            </figure>
          ))}
        </div>
      ) : (
        <p className="muted">{i.t('noPhotos')}</p>
      )}
      {open && (
        <div className="lightbox" role="dialog" aria-modal onClick={() => setOpen(null)}>
          <img src={open.url} alt="" />
          <button className="lightbox__close" aria-label={i.t('close')}>
            ✕
          </button>
        </div>
      )}
    </Section>
  )
}

export function History({ items }: { items: HistoryItem[] }) {
  const i = useI18n()
  if (!items.length) return null
  return (
    <Section title={i.t('history')}>
      <ol className="timeline">
        {items.map((h, idx) => (
          <li key={idx}>
            <time>{formatDateTime(h.created_at, i.lang)}</time>
            <span>{historyText(i, h)}</span>
          </li>
        ))}
      </ol>
    </Section>
  )
}

function monthLabel(month: string | undefined, lang: string): string {
  if (!month) return ''
  return new Date(`${month}-01T00:00:00`).toLocaleDateString(lang === 'kz' ? 'kk-KZ' : 'ru-RU', { month: 'short' })
}

/** Спарклайн NDVI за 12 месяцев. null — месяц без безоблачных снимков (разрыв линии). */
export function Ndvi({
  series,
  months,
  source,
  onRefresh,
}: {
  series: (number | null)[]
  months: string[]
  source: 'simulation' | 'sentinel-2'
  onRefresh?: () => Promise<void>
}) {
  const i = useI18n()
  const [busy, setBusy] = useState(false)
  if (series.length < 2) return null
  const w = 320
  const h = 64
  const max = 0.9
  const x = (k: number) => (k / (series.length - 1)) * w
  const y = (v: number) => h - (Math.max(0, v) / max) * h
  let line = ''
  let pen = false
  series.forEach((v, k) => {
    if (v === null) {
      pen = false
      return
    }
    line += `${pen ? 'L' : 'M'}${x(k).toFixed(1)},${y(v).toFixed(1)} `
    pen = true
  })
  const values = series.filter((v): v is number => v !== null)
  const peak = values.length ? Math.max(...values) : 0
  const low = peak < 0.25
  const refresh = onRefresh && (
    <button
      className="btn btn--ghost btn--sm"
      disabled={busy}
      onClick={async () => {
        setBusy(true)
        try {
          await onRefresh()
        } finally {
          setBusy(false)
        }
      }}
    >
      {busy ? i.t('ndviLoading') : `🛰 ${i.t('ndviRefresh')}`}
    </button>
  )
  return (
    <Section title={i.t('ndviTitle')} aside={refresh}>
      <svg className={`ndvi ${low ? 'ndvi--low' : ''}`} viewBox={`0 0 ${w} ${h + 16}`} role="img" aria-label={i.t('ndviTitle')}>
        <line x1="0" x2={w} y1={y(0.25)} y2={y(0.25)} className="ndvi__threshold" />
        <path d={line} className="ndvi__line" />
        {series.map((v, k) => (v === null ? null : <circle key={k} cx={x(k)} cy={y(v)} r="2.2" className="ndvi__dot" />))}
        <text x="0" y={h + 14}>
          {monthLabel(months[0], i.lang)}
        </text>
        <text x={w} y={h + 14} textAnchor="end">
          {monthLabel(months[months.length - 1], i.lang)}
        </text>
        <text x={w / 2} y={h + 14} textAnchor="middle">
          max {peak.toFixed(2)}
        </text>
      </svg>
      <p className={`small ${low ? 'text-bad' : 'muted'}`}>{low ? i.t('ndviLow') : i.t('ndviOk')}</p>
      <p className={`small ndvi-source ndvi-source--${source}`}>{source === 'sentinel-2' ? `🛰 ${i.t('ndviReal')}` : i.t('ndviNote')}</p>
    </Section>
  )
}
