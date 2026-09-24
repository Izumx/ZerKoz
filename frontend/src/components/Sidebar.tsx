import { useMemo } from 'react'
import type { Color, ParcelFeature, RoutePlan, SignalItem, SignalStatus, Stats } from '../api'
import type { Notify, Selection } from '../App'
import ApplicationsPanel from './ApplicationsPanel'
import RoutePanel from './RoutePanel'
import { deadlineLabel, formatArea, timeAgo } from '../format'
import { useI18n } from '../i18n'

export type ColorFilter = 'all' | Color | 'overdue'
export type Tab = 'parcels' | 'signals' | 'applications' | 'route'
type SignalFilter = 'open' | SignalStatus | 'all'

interface Props {
  stats: Stats | null
  parcels: ParcelFeature[]
  signals: SignalItem[]
  tab: Tab
  onTab: (tab: Tab) => void
  colorFilter: ColorFilter
  onColorFilter: (filter: ColorFilter) => void
  query: string
  onQuery: (query: string) => void
  signalFilter: SignalFilter
  onSignalFilter: (filter: SignalFilter) => void
  selection: Selection | null
  freshSignals: Set<number>
  onPick: (selection: Selection) => void
  notify: Notify
  version: number
  route: RoutePlan | null
}

const RANK: Record<Color, number> = { red: 0, yellow: 1, green: 2 }

export default function Sidebar(props: Props) {
  const i = useI18n()
  const { stats, tab, colorFilter, query, signalFilter } = props

  const parcels = useMemo(() => {
    const q = query.trim().toLowerCase()
    return props.parcels
      .filter((f) => {
        const p = f.properties
        if (colorFilter === 'overdue' ? !p.overdue : colorFilter !== 'all' && p.color !== colorFilter) return false
        return !q || p.cadastral_no.includes(q) || p.address.toLowerCase().includes(q) || p.owner.toLowerCase().includes(q)
      })
      .sort(
        (a, b) =>
          Number(b.properties.overdue) - Number(a.properties.overdue) ||
          RANK[a.properties.color] - RANK[b.properties.color] ||
          a.properties.cadastral_no.localeCompare(b.properties.cadastral_no),
      )
  }, [props.parcels, colorFilter, query])

  const signals = useMemo(
    () =>
      props.signals.filter((s) =>
        signalFilter === 'all' ? true : signalFilter === 'open' ? s.status === 'new' || s.status === 'checking' : s.status === signalFilter,
      ),
    [props.signals, signalFilter],
  )

  const statButton = (filter: ColorFilter, value: number | undefined, label: string) => (
    <button
      className={`stat stat--${filter} ${colorFilter === filter ? 'is-active' : ''}`}
      onClick={() => {
        props.onTab('parcels')
        props.onColorFilter(colorFilter === filter ? 'all' : filter)
      }}
      aria-pressed={colorFilter === filter}
    >
      <span className="stat__value">{value ?? '–'}</span>
      <span className="stat__label">{label}</span>
    </button>
  )

  return (
    <aside className="sidebar">
      <div className="stats">
        {statButton('red', stats?.red, i.t('statRed'))}
        {statButton('yellow', stats?.yellow, i.t('statYellow'))}
        {statButton('green', stats?.green, i.t('statGreen'))}
        {statButton('overdue', stats?.overdue, i.t('statOverdue'))}
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'parcels'} className={tab === 'parcels' ? 'is-active' : ''} onClick={() => props.onTab('parcels')}>
          {i.t('tabParcels')} <span className="count">{props.parcels.length}</span>
        </button>
        <button role="tab" aria-selected={tab === 'signals'} className={tab === 'signals' ? 'is-active' : ''} onClick={() => props.onTab('signals')}>
          {i.t('tabSignals')}
          {stats && stats.signals_new > 0 && <span className="count count--hot">{stats.signals_new}</span>}
        </button>
        <button role="tab" aria-selected={tab === 'applications'} className={tab === 'applications' ? 'is-active' : ''} onClick={() => props.onTab('applications')}>
          {i.t('tabApplications')}
        </button>
        <button role="tab" aria-selected={tab === 'route'} className={tab === 'route' ? 'is-active' : ''} onClick={() => props.onTab('route')}>
          {i.t('tabRoute')}
        </button>
      </div>

      {tab === 'applications' ? (
        <ApplicationsPanel notify={props.notify} version={props.version} />
      ) : tab === 'route' ? (
        <RoutePanel plan={props.route} onPick={props.onPick} />
      ) : tab === 'parcels' ? (
        <>
          <div className="filters">
            <input
              type="search"
              className="search"
              placeholder={i.t('search')}
              value={query}
              onChange={(e) => props.onQuery(e.target.value)}
            />
            <a className="btn btn--ghost btn--sm" href="/api/export/parcels.csv" download>
              {i.t('exportCsv')}
            </a>
          </div>
          <ul className="list">
            {parcels.map((f) => {
              const p = f.properties
              const active = props.selection?.kind === 'parcel' && props.selection.id === p.id
              return (
                <li key={p.id}>
                  <button className={`row ${active ? 'is-active' : ''}`} onClick={() => props.onPick({ kind: 'parcel', id: p.id })}>
                    <span className={`dot dot--${p.color}`} aria-label={i.d.color[p.color]} />
                    <span className="row__main">
                      <span className="row__title mono">{p.cadastral_no}</span>
                      <span className="row__sub">
                        {p.address} · {i.d.purposeName[p.purpose]} · {formatArea(p.area_ha)} {i.t('ha')}
                      </span>
                      {p.lifecycle !== 'none' && p.lifecycle !== 'resolved' && p.lifecycle !== 'returned' && (
                        <span className="row__meta">
                          {p.violation_type && i.d.violation[p.violation_type]}
                          {p.deadline && (
                            <span className={p.overdue ? 'overdue' : ''}> · {deadlineLabel(i, p.deadline)}</span>
                          )}
                        </span>
                      )}
                      {p.color === 'yellow' && (
                        <span className="row__meta">
                          {p.open_signals > 0 ? `${i.t('openSignals')}: ${p.open_signals}` : i.t('underCheckNote')}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              )
            })}
            {parcels.length === 0 && <EmptyState onReset={() => { props.onColorFilter('all'); props.onQuery('') }} />}
          </ul>
        </>
      ) : (
        <>
          <div className="chips">
            {(['open', 'confirmed', 'rejected', 'resolved', 'all'] as SignalFilter[]).map((f) => (
              <button key={f} className={`chip ${signalFilter === f ? 'is-active' : ''}`} onClick={() => props.onSignalFilter(f)}>
                {f === 'all' ? i.t('all') : f === 'open' ? `${i.d.signalStatus.new} + ${i.d.signalStatus.checking}` : i.d.signalStatus[f]}
              </button>
            ))}
          </div>
          <ul className="list">
            {signals.map((s) => {
              const active = props.selection?.kind === 'signal' && props.selection.id === s.id
              return (
                <li key={s.id}>
                  <button
                    className={`row row--signal ${active ? 'is-active' : ''} ${props.freshSignals.has(s.id) ? 'is-fresh' : ''}`}
                    onClick={() => props.onPick({ kind: 'signal', id: s.id })}
                  >
                    {s.photos[0] ? <img className="thumb" src={s.photos[0].url} alt="" loading="lazy" /> : <span className="thumb" />}
                    <span className="row__main">
                      <span className="row__title">
                        <span className="mono">{s.code}</span>
                        <span className={`badge badge--${s.status}`}>{i.d.signalStatus[s.status]}</span>
                        {s.reports > 1 && <span className="badge badge--reports">👥 {s.reports}</span>}
                        {s.ai && s.ai.violation_type !== 'none' && <span className="badge badge--ai">✦</span>}
                      </span>
                      <span className="row__sub clamp">{s.description || '—'}</span>
                      <span className="row__meta">
                        {timeAgo(i, s.created_at)} · {s.parcel ? <span className="mono">{s.parcel.cadastral_no}</span> : i.t('outsideParcels')}
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
            {signals.length === 0 && <EmptyState onReset={() => props.onSignalFilter('all')} />}
          </ul>
        </>
      )}
    </aside>
  )
}

function EmptyState({ onReset }: { onReset: () => void }) {
  const i = useI18n()
  return (
    <li className="empty">
      {i.t('empty')}{' '}
      <button className="link" onClick={onReset}>
        {i.t('resetFilters')}
      </button>
    </li>
  )
}
