import L from 'leaflet'
import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import type { SignalStatus, ViolationType } from '../api'
import { timeAgo } from '../format'
import { useI18n } from '../i18n'

/** Telegram Mini App для жителей: сигналы района на карте и «мои сигналы». */

interface PublicSignal {
  code: string
  lat: number
  lon: number
  status: SignalStatus
  violation: ViolationType | null
  reports: number
  created_at: string
  description?: string
  cadastral_no?: string | null
}

interface TelegramWebApp {
  initData: string
  ready: () => void
  expand: () => void
  colorScheme: 'light' | 'dark'
  themeParams: Record<string, string | undefined>
  HapticFeedback?: { selectionChanged: () => void }
}

declare global {
  interface Window {
    Telegram?: { WebApp: TelegramWebApp }
  }
}

const TARAZ: [number, number] = [42.9, 71.37]

function loadTelegram(): Promise<TelegramWebApp | null> {
  if (window.Telegram?.WebApp) return Promise.resolve(window.Telegram.WebApp)
  return new Promise((resolve) => {
    const script = document.createElement('script')
    script.src = 'https://telegram.org/js/telegram-web-app.js'
    script.onload = () => resolve(window.Telegram?.WebApp ?? null)
    script.onerror = () => resolve(null)
    document.head.appendChild(script)
  })
}

function distanceM(a: [number, number], b: [number, number]): number {
  const rad = Math.PI / 180
  const dLat = (b[0] - a[0]) * rad
  const dLon = (b[1] - a[1]) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) ** 2
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h))
}

const fmtDistance = (m: number) => (m < 1000 ? `${Math.round(m / 10) * 10} м` : `${(m / 1000).toFixed(1)} км`)

const icon = (status: SignalStatus, mine: boolean) =>
  L.divIcon({
    className: 'sig-wrap',
    html: `<span class="sig sig--${status}${mine ? ' sig--selected' : ''}"><i></i></span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  })

function FlyTo({ target }: { target: { at: [number, number]; key: number } | null }) {
  const map = useMap()
  useEffect(() => {
    if (target) map.flyTo(target.at, Math.max(map.getZoom(), 15), { duration: 0.6 })
  }, [target, map])
  return null
}

export default function TgApp() {
  const i = useI18n()
  const [tg, setTg] = useState<TelegramWebApp | null>(null)
  const [signals, setSignals] = useState<PublicSignal[]>([])
  const [mine, setMine] = useState<PublicSignal[] | null>(null)
  const [name, setName] = useState('')
  const [tab, setTab] = useState<'nearby' | 'mine'>('nearby')
  const [me, setMe] = useState<[number, number] | null>(null)
  const [target, setTarget] = useState<{ at: [number, number]; key: number } | null>(null)

  useEffect(() => {
    document.title = `ЖерКөз · ${i.t('tgTitle')}`
    fetch('/api/public/signals').then((r) => r.json()).then(setSignals).catch(() => undefined)
    loadTelegram().then((app) => {
      if (!app) return
      app.ready()
      app.expand()
      setTg(app)
      if (app.colorScheme === 'dark') document.documentElement.dataset.tgDark = '1'
      if (!app.initData) return
      fetch('/api/public/my-signals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ init_data: app.initData }),
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((body) => {
          if (!body) return
          setMine(body.signals)
          setName(body.first_name)
          if (body.lang === 'kz' || body.lang === 'ru') i.setLang(body.lang)
        })
        .catch(() => undefined)
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const locate = () =>
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        const at: [number, number] = [pos.coords.latitude, pos.coords.longitude]
        setMe(at)
        setTarget({ at, key: Date.now() })
      },
      () => undefined,
      { enableHighAccuracy: true, timeout: 8000 },
    )

  const origin = me ?? TARAZ
  const nearby = useMemo(
    () =>
      signals
        .map((s) => ({ ...s, distance: distanceM(origin, [s.lat, s.lon]) }))
        .sort((a, b) => a.distance - b.distance)
        .slice(0, 30),
    [signals, origin],
  )
  const mineCodes = new Set((mine ?? []).map((s) => s.code))
  const counts = {
    open: signals.filter((s) => s.status === 'new' || s.status === 'checking').length,
    confirmed: signals.filter((s) => s.status === 'confirmed').length,
    resolved: signals.filter((s) => s.status === 'resolved').length,
  }
  const show = (s: PublicSignal) => {
    tg?.HapticFeedback?.selectionChanged()
    setTarget({ at: [s.lat, s.lon], key: Date.now() })
  }
  const list: (PublicSignal & { distance?: number })[] = tab === 'nearby' ? nearby : mine ?? []

  return (
    <div className="tga">
      <header className="tga__head">
        <div>
          <div className="tga__title">{name ? i.t('tgHello', { name }) : `ЖерКөз · ${i.t('tgTitle')}`}</div>
          <div className="tga__sub">{i.t('tgSubtitle')}</div>
        </div>
        <div className="tga__counts" aria-label={i.t('tgSubtitle')}>
          <span className="tga__count tga__count--open">{counts.open}</span>
          <span className="tga__count tga__count--confirmed">{counts.confirmed}</span>
          <span className="tga__count tga__count--resolved">{counts.resolved}</span>
        </div>
      </header>

      <div className="tga__map">
        <MapContainer center={TARAZ} zoom={12} zoomControl={false} className="map" attributionControl={false}>
          <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19} />
          {signals.map((s) => (
            <Marker key={s.code} position={[s.lat, s.lon]} icon={icon(s.status, mineCodes.has(s.code))}>
              <Popup>
                <b>{i.d.signalStatus[s.status]}</b>
                {s.violation && <> · {i.d.violation[s.violation]}</>}
                <br />
                {timeAgo(i, s.created_at)}
                {s.reports > 1 && <> · {i.t('reports', { n: s.reports })}</>}
              </Popup>
            </Marker>
          ))}
          {me && <CircleMarker center={me} radius={8} pathOptions={{ color: '#fff', weight: 3, fillColor: '#0B6E7A', fillOpacity: 1 }} />}
          <FlyTo target={target} />
        </MapContainer>
        <button className="tga__locate" onClick={locate}>
          ◎ {i.t('tgLocate')}
        </button>
      </div>

      <div className="tga__tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'nearby'} className={tab === 'nearby' ? 'is-active' : ''} onClick={() => setTab('nearby')}>
          {i.t('tgNearby')}
        </button>
        <button role="tab" aria-selected={tab === 'mine'} className={tab === 'mine' ? 'is-active' : ''} onClick={() => setTab('mine')}>
          {i.t('tgMine')} {mine && mine.length > 0 && <span className="count">{mine.length}</span>}
        </button>
      </div>

      <ul className="tga__list">
        {list.map((s) => (
          <li key={s.code}>
            <button className="tga__row" onClick={() => show(s)}>
              <span className={`badge badge--${s.status}`}>{i.d.signalStatus[s.status]}</span>
              <span className="tga__row-main">
                <span className="tga__row-title">
                  {tab === 'mine' ? <span className="mono">{s.code}</span> : s.violation ? i.d.violation[s.violation] : '—'}
                  {s.reports > 1 && <span className="muted"> · 👥 {s.reports}</span>}
                </span>
                {tab === 'mine' && s.description && <span className="tga__row-sub clamp">{s.description}</span>}
                <span className="tga__row-sub">
                  {timeAgo(i, s.created_at)}
                  {s.distance !== undefined && ` · ${i.t(me ? 'tgAway' : 'tgFromCenter', { d: fmtDistance(s.distance) })}`}
                </span>
              </span>
            </button>
          </li>
        ))}
        {list.length === 0 && (
          <li className="empty">
            {tab === 'nearby' ? i.t('tgEmptyNearby') : tg?.initData ? i.t('tgEmptyMine') : i.t('tgOpenInTelegram')}
          </li>
        )}
      </ul>
      <p className="tga__privacy">{i.t('tgPrivacy')}</p>
    </div>
  )
}
