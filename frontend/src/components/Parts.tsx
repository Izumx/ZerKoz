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
            <button key={p.id} className="photo" onClick={() => setOpen(p)}>
              <img src={p.url} alt="" loading="lazy" />
              <span className={`photo__tag photo__tag--${p.source}`}>
                {p.source === 'citizen' ? i.t('byCitizen') : i.t('byInspector')}
              </span>
            </button>
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

/** Спарклайн NDVI за 12 месяцев (октябрь → сентябрь). */
export function Ndvi({ series }: { series: number[] }) {
  const i = useI18n()
  if (series.length < 2) return null
  const w = 320
  const h = 64
  const max = 0.9
  const pts = series.map((v, k) => [(k / (series.length - 1)) * w, h - (v / max) * h] as const)
  const line = pts.map(([x, y], k) => `${k ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const peak = Math.max(...series)
  const low = peak < 0.25
  return (
    <Section title={i.t('ndviTitle')} aside={<span className="muted small">{i.t('ndviNote')}</span>}>
      <svg className={`ndvi ${low ? 'ndvi--low' : ''}`} viewBox={`0 0 ${w} ${h + 16}`} role="img" aria-label={i.t('ndviTitle')}>
        <line x1="0" x2={w} y1={h - (0.25 / max) * h} y2={h - (0.25 / max) * h} className="ndvi__threshold" />
        <path d={`${line} L${w},${h} L0,${h} Z`} className="ndvi__area" />
        <path d={line} className="ndvi__line" />
        <text x="0" y={h + 14}>{i.lang === 'kz' ? 'қаз' : 'окт'}</text>
        <text x={w} y={h + 14} textAnchor="end">{i.lang === 'kz' ? 'қыр' : 'сен'}</text>
        <text x={w / 2} y={h + 14} textAnchor="middle">
          max {peak.toFixed(2)}
        </text>
      </svg>
      <p className={`small ${low ? 'text-bad' : 'muted'}`}>{low ? i.t('ndviLow') : i.t('ndviOk')}</p>
    </Section>
  )
}
