import type { RoutePlan } from '../api'
import { useI18n } from '../i18n'
import type { Selection } from '../App'

const GOOGLE_MAX_WAYPOINTS = 9

function googleUrl(plan: RoutePlan): string {
  const stops = plan.stops.slice(0, GOOGLE_MAX_WAYPOINTS + 1)
  const pt = (s: { lat: number; lon: number }) => `${s.lat.toFixed(6)},${s.lon.toFixed(6)}`
  const params = new URLSearchParams({
    api: '1',
    origin: pt(plan.start),
    destination: pt(stops[stops.length - 1]),
    travelmode: 'driving',
  })
  if (stops.length > 1) params.set('waypoints', stops.slice(0, -1).map(pt).join('|'))
  return `https://www.google.com/maps/dir/?${params}`
}

function yandexUrl(plan: RoutePlan): string {
  const points = [plan.start, ...plan.stops].map((s) => `${s.lat.toFixed(6)},${s.lon.toFixed(6)}`).join('~')
  return `https://yandex.kz/maps/?rtext=${points}&rtt=auto`
}

export default function RoutePanel({ plan, onPick }: { plan: RoutePlan | null; onPick: (s: Selection) => void }) {
  const i = useI18n()
  if (!plan) return <div className="list" />
  const reason = { overdue: i.t('reasonOverdue'), check: i.t('reasonCheck'), signal: i.t('reasonSignal') }

  return (
    <div className="list route">
      <p className="muted small route__hint">{i.t('routeHint')}</p>
      {plan.stops.length === 0 ? (
        <p className="empty">{i.t('routeEmpty')}</p>
      ) : (
        <>
          <div className="route__summary">
            <strong>{i.t('routeDistance', { n: plan.stops.length, km: plan.distance_km })}</strong>
            <div className="actions">
              <a className="btn btn--primary btn--sm" href={googleUrl(plan)} target="_blank" rel="noreferrer">
                {i.t('openGoogle')} ↗
              </a>
              <a className="btn btn--ghost btn--sm" href={yandexUrl(plan)} target="_blank" rel="noreferrer">
                {i.t('openYandex')} ↗
              </a>
            </div>
          </div>
          <ol className="route__stops">
            <li className="route__stop route__stop--start">
              <span className="route__num">★</span>
              <span>{i.t('office')}</span>
            </li>
            {plan.stops.map((s, k) => (
              <li key={`${s.kind}-${s.id}`}>
                <button className="route__stop" onClick={() => onPick({ kind: s.kind, id: s.id })}>
                  <span className={`route__num route__num--${s.reason}`}>{k + 1}</span>
                  <span className="row__main">
                    <span className="mono">{s.label}</span>
                    <span className="row__sub">
                      {reason[s.reason]}
                      {s.address && ` · ${s.address}`}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  )
}
