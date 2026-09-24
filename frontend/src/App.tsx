import { useCallback, useEffect, useRef, useState } from 'react'
import {
  api,
  setUnauthorizedHandler,
  type ParcelCollection,
  type RoutePlan,
  type SessionInfo,
  type SignalItem,
  type Stats,
} from './api'
import ActView from './components/ActView'
import Login from './components/Login'
import MapView, { type Focus } from './components/MapView'
import ParcelCard from './components/ParcelCard'
import Sidebar, { type ColorFilter, type Tab } from './components/Sidebar'
import SignalCard from './components/SignalCard'
import { useI18n } from './i18n'
import { useLive, type LiveEvent } from './useLive'

export type Selection = { kind: 'parcel' | 'signal'; id: number }
export type Notify = (kind: 'ok' | 'error', text: string) => void

interface Toast {
  id: number
  kind: 'ok' | 'error' | 'signal'
  text: string
  signal?: SignalItem
}

const FRESH_MS = 60_000

/** Корень: проверка сессии → экран входа, печатный акт или рабочее место инспектора. */
export default function App() {
  const params = new URLSearchParams(window.location.search)
  const actId = Number(params.get('act')) || null
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const i = useI18n()

  const loadSession = useCallback(() => {
    api.session().then(setSession).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    const lang = params.get('lang')
    if (lang === 'kz' || lang === 'ru') i.setLang(lang)
    loadSession()
    setUnauthorizedHandler(() => setSession((s) => (s ? { ...s, authenticated: false } : s)))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!session) return <div className="stage__placeholder">{error ?? '…'}</div>
  if (!session.authenticated) return <Login onSuccess={loadSession} />
  if (actId) return <ActView id={actId} />
  return <Workspace session={session} onLogout={() => api.logout().finally(loadSession)} />
}

function Workspace({ session, onLogout }: { session: SessionInfo; onLogout: () => void }) {
  const i = useI18n()
  const [parcels, setParcels] = useState<ParcelCollection | null>(null)
  const [signals, setSignals] = useState<SignalItem[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [route, setRoute] = useState<RoutePlan | null>(null)
  const [version, setVersion] = useState(0)
  const [selection, setSelection] = useState<Selection | null>(null)
  const [focus, setFocus] = useState<Focus | null>(null)
  const [tab, setTab] = useState<Tab>('parcels')
  const [colorFilter, setColorFilter] = useState<ColorFilter>('all')
  const [query, setQuery] = useState('')
  const [signalFilter, setSignalFilter] = useState<'open' | 'all' | SignalItem['status']>('open')
  const [fresh, setFresh] = useState<Set<number>>(new Set())
  const [toasts, setToasts] = useState<Toast[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [demoBusy, setDemoBusy] = useState(false)
  const parcelsRef = useRef(parcels)
  parcelsRef.current = parcels
  const signalsRef = useRef(signals)
  signalsRef.current = signals
  const tabRef = useRef(tab)
  tabRef.current = tab

  const pushToast = useCallback((toast: Omit<Toast, 'id'>, ttl = 4500) => {
    const id = Date.now() + Math.random()
    setToasts((list) => [...list.slice(-3), { ...toast, id }])
    window.setTimeout(() => setToasts((list) => list.filter((x) => x.id !== id)), ttl)
  }, [])
  const notify = useCallback<Notify>((kind, text) => pushToast({ kind, text }), [pushToast])

  const refresh = useCallback(async () => {
    try {
      const [p, s, st] = await Promise.all([api.parcels(), api.signals(), api.stats()])
      setParcels(p)
      setSignals(s)
      setStats(st)
      setVersion((v) => v + 1)
      setLoadError(null)
      if (tabRef.current === 'route') setRoute(await api.route())
    } catch (e) {
      setLoadError((e as Error).message)
    }
  }, [])

  const refreshTimer = useRef<number>()
  const scheduleRefresh = useCallback(() => {
    window.clearTimeout(refreshTimer.current)
    refreshTimer.current = window.setTimeout(refresh, 150)
  }, [refresh])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    if (tab === 'route') api.route().then(setRoute).catch((e) => notify('error', e.message))
    else setRoute(null)
  }, [tab, notify])

  const pick = useCallback((sel: Selection) => {
    setSelection(sel)
    if (sel.kind === 'parcel') {
      const feature = parcelsRef.current?.features.find((f) => f.id === sel.id)
      if (feature) setFocus({ key: Date.now(), kind: 'parcel', feature })
    } else {
      const signal = signalsRef.current.find((s) => s.id === sel.id)
      if (signal) setFocus({ key: Date.now(), kind: 'point', lat: signal.lat, lon: signal.lon })
      else
        api
          .signal(sel.id)
          .then((s) => setFocus({ key: Date.now(), kind: 'point', lat: s.lat, lon: s.lon }))
          .catch(() => undefined)
    }
  }, [])

  const onLive = useCallback(
    async (event: LiveEvent) => {
      scheduleRefresh()
      if (event.type !== 'signal.created') return
      const { id, code } = event.data
      setFresh((set) => new Set(set).add(id))
      window.setTimeout(() => setFresh((set) => { const next = new Set(set); next.delete(id); return next }), FRESH_MS)
      const signal = await api.signal(id).catch(() => undefined)
      pushToast({ kind: 'signal', text: i.t('newSignal', { code }), signal }, 12_000)
    },
    [scheduleRefresh, pushToast, i],
  )
  const connected = useLive(onLive)

  const demo = async () => {
    setDemoBusy(true)
    try {
      await api.demoSignal()
    } catch (e) {
      notify('error', (e as Error).message)
    } finally {
      setDemoBusy(false)
    }
  }

  const drawerProps = {
    version,
    onClose: () => setSelection(null),
    onChanged: scheduleRefresh,
    onPick: pick,
    notify,
  }

  return (
    <div className="app">
      <svg width="0" height="0" className="defs" aria-hidden>
        <defs>
          <pattern id="hatch-red" patternUnits="userSpaceOnUse" width="9" height="9" patternTransform="rotate(45)">
            <rect width="9" height="9" fill="#D6452F" fillOpacity="0.16" />
            <rect width="3.2" height="9" fill="#D6452F" fillOpacity="0.85" />
          </pattern>
        </defs>
      </svg>

      <header className="topbar">
        <div className="brand">
          <span className="brand__mark" aria-hidden>
            <svg viewBox="0 0 32 32">
              <path d="M6 23 L13 8 L26 12 L21 25 Z" />
              <circle cx="16" cy="16" r="3" />
            </svg>
          </span>
          <span>
            <span className="brand__name">ЖерКөз</span>
            <span className="brand__sub">{i.t('appSubtitle')}</span>
          </span>
        </div>
        <div className="topbar__tools">
          <span className={`live ${connected ? 'is-on' : ''}`}>
            <span className="live__dot" /> {connected ? i.t('live') : i.t('offline')}
          </span>
          {session.bot_username && (
            <a className="bot-link" href={`https://t.me/${session.bot_username}`} target="_blank" rel="noreferrer" title={i.t('botLink')}>
              <span aria-hidden>✈</span> @{session.bot_username}
            </a>
          )}
          {session.demo_mode && (
            <button className="btn btn--demo" onClick={demo} disabled={demoBusy}>
              {demoBusy ? i.t('demoSending') : `⚡ ${i.t('demoSignal')}`}
            </button>
          )}
          <div className="lang-switch" role="group" aria-label="Язык / Тіл">
            {(['kz', 'ru'] as const).map((l) => (
              <button key={l} className={i.lang === l ? 'is-active' : ''} onClick={() => i.setLang(l)} aria-pressed={i.lang === l}>
                {l === 'kz' ? 'ҚАЗ' : 'РУС'}
              </button>
            ))}
          </div>
          {session.auth_required && (
            <button className="bot-link logout" onClick={onLogout}>
              {i.t('logout')}
            </button>
          )}
        </div>
      </header>

      <div className="workspace">
        <Sidebar
          stats={stats}
          parcels={parcels?.features ?? []}
          signals={signals}
          tab={tab}
          onTab={setTab}
          colorFilter={colorFilter}
          onColorFilter={setColorFilter}
          query={query}
          onQuery={setQuery}
          signalFilter={signalFilter}
          onSignalFilter={setSignalFilter}
          selection={selection}
          freshSignals={fresh}
          onPick={pick}
          notify={notify}
          version={version}
          route={route}
        />

        <main className="stage">
          {parcels ? (
            <MapView
              parcels={parcels}
              signals={signals}
              version={version}
              selection={selection}
              freshSignals={fresh}
              focus={focus}
              route={tab === 'route' ? route : null}
              onSelect={pick}
            />
          ) : (
            <div className="stage__placeholder">{loadError ?? '…'}</div>
          )}

          {selection && (
            <aside className="drawer" key={`${selection.kind}-${selection.id}`}>
              {selection.kind === 'parcel' ? (
                <ParcelCard id={selection.id} sentinelEnabled={session.sentinel_enabled} {...drawerProps} />
              ) : (
                <SignalCard id={selection.id} {...drawerProps} />
              )}
            </aside>
          )}
        </main>
      </div>

      <div className="toasts" aria-live="polite">
        {toasts.map((toast) =>
          toast.kind === 'signal' ? (
            <div key={toast.id} className="toast toast--signal">
              {toast.signal?.photos[0] && <img src={toast.signal.photos[0].url} alt="" />}
              <div className="toast__body">
                <strong>{toast.text}</strong>
                <span className="clamp">
                  {toast.signal?.duplicate_of ? `↳ ${toast.signal.duplicate_of.code} · ` : ''}
                  {toast.signal?.description || i.t('newSignalBody')}
                </span>
                {toast.signal && (
                  <button
                    className="btn btn--primary btn--sm"
                    onClick={() => {
                      pick({ kind: 'signal', id: toast.signal!.duplicate_of?.id ?? toast.signal!.id })
                      setToasts((list) => list.filter((x) => x.id !== toast.id))
                    }}
                  >
                    {i.t('showOnMap')} →
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div key={toast.id} className={`toast toast--${toast.kind}`}>
              {toast.text}
            </div>
          ),
        )}
      </div>
    </div>
  )
}
