import { useEffect, useState } from 'react'
import { api, type Lifecycle, type ParcelDetail, type ParcelPatch, type ViolationType } from '../api'
import { addDaysISO, deadlineLabel, formatArea, formatDate, timeAgo } from '../format'
import { useI18n } from '../i18n'
import type { Notify, Selection } from '../App'
import { History, Ndvi, Photos, Section } from './Parts'

interface Props {
  id: number
  version: number
  onClose: () => void
  onChanged: () => void
  onPick: (selection: Selection) => void
  notify: Notify
  sentinelEnabled: boolean
}

const VIOLATIONS: ViolationType[] = ['unused', 'seizure', 'dump']

export default function ParcelCard({ id, version, onClose, onChanged, onPick, notify, sentinelEnabled }: Props) {
  const i = useI18n()
  const [parcel, setParcel] = useState<ParcelDetail | null>(null)

  useEffect(() => {
    let alive = true
    api.parcel(id).then((p) => alive && setParcel(p)).catch((e) => notify('error', e.message))
    return () => {
      alive = false
    }
  }, [id, version, notify])

  if (!parcel || parcel.id !== id) return <div className="drawer__loading" />

  const save = async (patch: ParcelPatch) => {
    try {
      setParcel(await api.patchParcel(id, patch))
      notify('ok', i.t('saved'))
      onChanged()
    } catch (e) {
      notify('error', (e as Error).message)
    }
  }

  return (
    <>
      <header className={`drawer__head drawer__head--${parcel.color}`}>
        <div>
          <div className="eyebrow">{i.t('cadastralNo')}</div>
          <h2 className="mono">{parcel.cadastral_no}</h2>
          <div className="drawer__sub">{parcel.address}</div>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label={i.t('close')}>
          ✕
        </button>
      </header>

      <div className="drawer__body">
        <div className={`status-line status-line--${parcel.color}`}>
          <span className={`dot dot--${parcel.color}`} />
          <strong>{i.d.lifecycle[parcel.lifecycle]}</strong>
          {parcel.violation_type && parcel.lifecycle !== 'none' && <span>· {i.d.violation[parcel.violation_type]}</span>}
          {parcel.under_check && <span>· {i.t('underCheckNote')}</span>}
          <a className="btn btn--ghost btn--sm status-line__act" href={`/?act=${parcel.id}&lang=${i.lang}`} target="_blank" rel="noreferrer">
            🖨 {i.t('act')}
          </a>
        </div>

        <dl className="facts">
          <div>
            <dt>{i.t('purpose')}</dt>
            <dd>{i.d.purposeName[parcel.purpose]}</dd>
          </div>
          <div>
            <dt>{i.t('area')}</dt>
            <dd>
              {formatArea(parcel.area_ha)} {i.t('ha')}
            </dd>
          </div>
          <div>
            <dt>{i.t('owner')}</dt>
            <dd>{parcel.owner || '—'}</dd>
          </div>
          <div>
            <dt>{i.t('openSignals')}</dt>
            <dd>{parcel.open_signals}</dd>
          </div>
        </dl>

        <LifecyclePanel parcel={parcel} onSave={save} />

        {parcel.signals.length > 0 && (
          <Section title={i.t('citizenSignals')}>
            <ul className="mini-list">
              {parcel.signals.map((s) => (
                <li key={s.id}>
                  <button className="mini-row" onClick={() => onPick({ kind: 'signal', id: s.id })}>
                    <span className="mono">{s.code}</span>
                    <span className={`badge badge--${s.status}`}>{i.d.signalStatus[s.status]}</span>
                    <span className="clamp muted">{s.duplicate ? '↳ ' : ''}{s.description}</span>
                    <span className="muted small">{timeAgo(i, s.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </Section>
        )}

        <Photos
          photos={parcel.photos}
          onUpload={async (files) => {
            try {
              setParcel(await api.uploadPhotos(id, files))
              notify('ok', i.t('photosUploaded'))
              onChanged()
            } catch (e) {
              notify('error', (e as Error).message)
            }
          }}
        />
        <Ndvi
          series={parcel.ndvi_series}
          months={parcel.ndvi_months}
          source={parcel.ndvi_source}
          onRefresh={
            sentinelEnabled
              ? async () => {
                  try {
                    setParcel(await api.refreshNdvi(id))
                    notify('ok', i.t('ndviUpdated'))
                    onChanged()
                  } catch (e) {
                    notify('error', (e as Error).message)
                  }
                }
              : undefined
          }
        />
        <History items={parcel.history} />
      </div>
    </>
  )
}

function LifecyclePanel({ parcel, onSave }: { parcel: ParcelDetail; onSave: (patch: ParcelPatch) => Promise<void> }) {
  const i = useI18n()
  const [violation, setViolation] = useState<ViolationType | ''>(parcel.violation_type ?? '')
  const [deadline, setDeadline] = useState(parcel.deadline ?? '')

  useEffect(() => {
    setViolation(parcel.violation_type ?? '')
    setDeadline(parcel.deadline ?? '')
  }, [parcel.id, parcel.violation_type, parcel.deadline])

  const lc = parcel.lifecycle
  const closed = lc === 'resolved' || lc === 'returned'
  const stepState = (step: 0 | 1 | 2): 'done' | 'current' | 'todo' => {
    const index: Record<Lifecycle, number> = { none: -1, detected: 0, in_progress: 1, resolved: 2, returned: 2 }
    const at = index[lc]
    if (at > step || (closed && step === 2)) return 'done'
    return at === step ? 'current' : 'todo'
  }
  const steps = [i.t('stepDetected'), i.t('stepInProgress'), closed ? i.d.lifecycle[lc] : i.t('stepClosed')]

  const deadlineEditor = (
    <div className="field">
      <label htmlFor="deadline">{i.t('deadline')}</label>
      <div className="deadline">
        <input id="deadline" type="date" value={deadline} min={lc === 'in_progress' ? undefined : addDaysISO(0)} onChange={(e) => setDeadline(e.target.value)} />
        {[7, 14, 30].map((n) => (
          <button key={n} className="chip" onClick={() => setDeadline(addDaysISO(n))}>
            +{n}
          </button>
        ))}
      </div>
      {parcel.deadline && (
        <div className={`deadline__state ${parcel.overdue ? 'text-bad' : 'muted'}`}>
          {formatDate(parcel.deadline, i.lang)} · {deadlineLabel(i, parcel.deadline)}
        </div>
      )}
    </div>
  )

  return (
    <Section title={i.t('lifecycleTitle')}>
      <ol className={`stepper ${lc === 'none' ? 'stepper--idle' : ''}`}>
        {steps.map((label, k) => (
          <li key={k} className={`step step--${stepState(k as 0 | 1 | 2)}`}>
            <span className="step__mark" />
            <span className="step__label">{label}</span>
          </li>
        ))}
      </ol>

      {(lc === 'none' || closed) && (
        <div className="action-box">
          {lc === 'none' ? <p className="muted small">{i.t('noViolation')}</p> : <p className="muted small">{i.t('closedNote')}</p>}
          <div className="field">
            <label htmlFor="violation">{i.t('violationType')}</label>
            <select id="violation" value={violation} onChange={(e) => setViolation(e.target.value as ViolationType)}>
              <option value="" disabled>
                {i.t('chooseViolation')}
              </option>
              {VIOLATIONS.map((v) => (
                <option key={v} value={v}>
                  {i.d.violation[v]}
                </option>
              ))}
            </select>
          </div>
          <div className="actions">
            <button className="btn btn--danger" disabled={!violation} onClick={() => onSave({ lifecycle: 'detected', violation_type: violation || null })}>
              {closed ? i.t('repeatViolation') : i.t('recordViolation')}
            </button>
            {lc === 'none' && (
              <button className="btn btn--ghost" onClick={() => onSave({ under_check: !parcel.under_check })}>
                {parcel.under_check ? i.t('underCheckOff') : i.t('underCheckOn')}
              </button>
            )}
          </div>
        </div>
      )}

      {lc === 'detected' && (
        <div className="action-box">
          {deadlineEditor}
          {!deadline && <p className="muted small">{i.t('needDeadline')}</p>}
          <div className="actions">
            <button className="btn btn--primary" disabled={!deadline} onClick={() => onSave({ lifecycle: 'in_progress', deadline })}>
              {i.t('startFix')} →
            </button>
            <button className="btn btn--ghost" onClick={() => onSave({ lifecycle: 'resolved' })}>
              {i.t('markResolved')}
            </button>
            <button className="btn btn--ghost" onClick={() => onSave({ lifecycle: 'returned' })}>
              {i.t('returnToState')}
            </button>
          </div>
        </div>
      )}

      {lc === 'in_progress' && (
        <div className="action-box">
          {deadlineEditor}
          <div className="actions">
            {deadline !== (parcel.deadline ?? '') && deadline && (
              <button className="btn btn--ghost" onClick={() => onSave({ deadline })}>
                {i.t('saveDeadline')}
              </button>
            )}
            <button className="btn btn--ok" onClick={() => onSave({ lifecycle: 'resolved' })}>
              ✓ {i.t('markResolved')}
            </button>
            <button className="btn btn--ghost" onClick={() => onSave({ lifecycle: 'returned' })}>
              {i.t('returnToState')}
            </button>
          </div>
        </div>
      )}
    </Section>
  )
}
