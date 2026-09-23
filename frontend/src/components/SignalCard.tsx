import { useEffect, useState } from 'react'
import { api, type SignalItem, type SignalStatus, type ViolationType } from '../api'
import { formatDateTime, timeAgo } from '../format'
import { useI18n } from '../i18n'
import type { Notify, Selection } from '../App'
import { History, Photos, Section } from './Parts'

interface Props {
  id: number
  version: number
  onClose: () => void
  onChanged: () => void
  onPick: (selection: Selection) => void
  notify: Notify
}

export default function SignalCard({ id, version, onClose, onChanged, onPick, notify }: Props) {
  const i = useI18n()
  const [signal, setSignal] = useState<SignalItem | null>(null)
  const [violation, setViolation] = useState<ViolationType>('dump')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let alive = true
    api.signal(id).then((s) => alive && setSignal(s)).catch((e) => notify('error', e.message))
    return () => {
      alive = false
    }
  }, [id, version, notify])

  if (!signal || signal.id !== id) return <div className="drawer__loading" />

  const setStatus = async (status: SignalStatus) => {
    setBusy(true)
    try {
      const updated = await api.patchSignal(id, status, status === 'confirmed' ? violation : undefined)
      setSignal(updated)
      notify('ok', i.t('statusChanged', { code: updated.code, status: i.d.signalStatus[status] }))
      onChanged()
    } catch (e) {
      notify('error', (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const source = signal.source === 'telegram' ? i.t('sourceTelegram') : signal.source === 'demo' ? i.t('sourceDemo') : i.t('sourceSeed')
  const st = signal.status
  const canConfirm = st === 'new' || st === 'checking'

  return (
    <>
      <header className="drawer__head drawer__head--signal">
        <div>
          <div className="eyebrow">
            {i.t('signal')} · {source}
          </div>
          <h2 className="mono">{signal.code}</h2>
          <div className="drawer__sub">
            {i.t('received')} {formatDateTime(signal.created_at, i.lang)} · {timeAgo(i, signal.created_at)}
          </div>
        </div>
        <button className="icon-btn" onClick={onClose} aria-label={i.t('close')}>
          ✕
        </button>
      </header>

      <div className="drawer__body">
        <div className="status-line">
          <span className={`badge badge--${st}`}>{i.d.signalStatus[st]}</span>
        </div>

        {signal.description && <blockquote className="quote">{signal.description}</blockquote>}

        <dl className="facts facts--one">
          <div>
            <dt>{i.t('location')}</dt>
            <dd>
              <span className="mono">
                {signal.lat.toFixed(5)}, {signal.lon.toFixed(5)}
              </span>
              <br />
              {signal.parcel ? (
                <button className="link" onClick={() => onPick({ kind: 'parcel', id: signal.parcel!.id })}>
                  {i.t('openParcel')} <span className="mono">{signal.parcel.cadastral_no}</span> →
                </button>
              ) : (
                <span className="muted">{i.t('outsideParcels')}</span>
              )}
            </dd>
          </div>
        </dl>

        {st !== 'resolved' && (
          <Section title={i.t('lifecycleTitle')}>
            <div className="action-box">
              {canConfirm && signal.parcel && (
                <div className="field">
                  <label htmlFor="sig-violation">{i.t('violationType')}</label>
                  <select id="sig-violation" value={violation} onChange={(e) => setViolation(e.target.value as ViolationType)}>
                    {(['dump', 'unused', 'seizure'] as ViolationType[]).map((v) => (
                      <option key={v} value={v}>
                        {i.d.violation[v]}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="actions">
                {st === 'new' && (
                  <button className="btn btn--primary" disabled={busy} onClick={() => setStatus('checking')}>
                    {i.t('takeToCheck')}
                  </button>
                )}
                {canConfirm && (
                  <button className="btn btn--danger" disabled={busy} onClick={() => setStatus('confirmed')}>
                    {i.t('confirmViolation')}
                  </button>
                )}
                {canConfirm && (
                  <button className="btn btn--ghost" disabled={busy} onClick={() => setStatus('rejected')}>
                    {i.t('reject')}
                  </button>
                )}
                {st === 'confirmed' && (
                  <button className="btn btn--ok" disabled={busy} onClick={() => setStatus('resolved')}>
                    ✓ {i.t('markSignalResolved')}
                  </button>
                )}
                {st === 'rejected' && (
                  <button className="btn btn--ghost" disabled={busy} onClick={() => setStatus('checking')}>
                    {i.t('backToCheck')}
                  </button>
                )}
              </div>
              <p className={`small ${signal.has_citizen ? 'notice' : 'muted'}`}>
                {signal.has_citizen ? `🔔 ${i.t('citizenNotified')}` : i.t('noCitizen')}
              </p>
            </div>
          </Section>
        )}

        <Photos photos={signal.photos} />
        <History items={signal.history ?? []} />
      </div>
    </>
  )
}
