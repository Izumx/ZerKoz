import { useEffect, useState } from 'react'
import { api, type Application, type Stage } from '../api'
import { formatDateTime } from '../format'
import { useI18n } from '../i18n'
import type { Notify } from '../App'

const STAGES: Stage[] = ['review', 'inspection', 'approved', 'rejected']

/** Заявления граждан: смена этапа уведомляет подписчиков в Telegram. */
export default function ApplicationsPanel({ notify, version }: { notify: Notify; version: number }) {
  const i = useI18n()
  const [items, setItems] = useState<Application[]>([])
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    api.applications().then(setItems).catch((e) => notify('error', e.message))
  }, [notify, version])

  return (
    <ul className="list">
      {items.map((a) =>
        open === a.track_no ? (
          <li key={a.track_no}>
            <ApplicationEditor
              app={a}
              onClose={() => setOpen(null)}
              onSaved={(updated) => {
                setItems((list) => list.map((x) => (x.track_no === updated.track_no ? updated : x)))
                setOpen(null)
                notify('ok', i.t('applicationSaved', { code: updated.track_no }))
              }}
              notify={notify}
            />
          </li>
        ) : (
          <li key={a.track_no}>
            <button className="row" onClick={() => setOpen(a.track_no)}>
              <span className={`stage-dot stage-dot--${a.stage}`} />
              <span className="row__main">
                <span className="row__title">
                  <span className="mono">{a.track_no}</span>
                  <span className={`badge badge--stage-${a.stage}`}>{i.d.stage[a.stage]}</span>
                </span>
                <span className="row__sub">
                  {i.d.appType[a.type]} · {a.applicant}
                </span>
                <span className="row__meta">
                  {formatDateTime(a.updated_at, i.lang)}
                  {a.subscribers > 0 && <> · 🔔 {a.subscribers}</>}
                </span>
              </span>
            </button>
          </li>
        ),
      )}
    </ul>
  )
}

function ApplicationEditor({
  app,
  onClose,
  onSaved,
  notify,
}: {
  app: Application
  onClose: () => void
  onSaved: (app: Application) => void
  notify: Notify
}) {
  const i = useI18n()
  const [stage, setStage] = useState<Stage>(app.stage)
  const [noteRu, setNoteRu] = useState(app.note_ru)
  const [noteKz, setNoteKz] = useState(app.note_kz)
  const [busy, setBusy] = useState(false)

  return (
    <form
      className="app-editor"
      onSubmit={async (e) => {
        e.preventDefault()
        setBusy(true)
        try {
          onSaved(await api.patchApplication(app.track_no, { stage, note_ru: noteRu, note_kz: noteKz }))
        } catch (err) {
          notify('error', (err as Error).message)
        } finally {
          setBusy(false)
        }
      }}
    >
      <div className="app-editor__head">
        <span className="mono">{app.track_no}</span>
        <button type="button" className="icon-btn" onClick={onClose} aria-label={i.t('close')}>
          ✕
        </button>
      </div>
      <div className="muted small">
        {i.d.appType[app.type]} · {app.applicant}
      </div>
      <div className="chips">
        {STAGES.map((s) => (
          <button type="button" key={s} className={`chip ${stage === s ? 'is-active' : ''}`} onClick={() => setStage(s)}>
            {i.d.stage[s]}
          </button>
        ))}
      </div>
      <label className="field">
        <span>{i.t('noteRu')}</span>
        <textarea rows={3} value={noteRu} onChange={(e) => setNoteRu(e.target.value)} />
      </label>
      <label className="field">
        <span>{i.t('noteKz')}</span>
        <textarea rows={3} value={noteKz} onChange={(e) => setNoteKz(e.target.value)} />
      </label>
      <p className="muted small">
        🔔 {i.t('subscribers', { n: app.subscribers })}. {i.t('applicationHint')}
      </p>
      <button className="btn btn--primary" disabled={busy}>
        {i.t('saveApplication')}
      </button>
    </form>
  )
}
