import L from 'leaflet'
import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Marker, TileLayer, Tooltip, ZoomControl, useMap, useMapEvent } from 'react-leaflet'
import type { ParcelCollection, ParcelFeature, RoutePlan, SignalItem } from '../api'
import { HeatLayer, RouteLayer } from './MapLayers'
import { escapeHtml } from '../format'
import { useI18n } from '../i18n'
import type { Selection } from '../App'

export type Focus = { key: number; kind: 'parcel'; feature: ParcelFeature } | { key: number; kind: 'point'; lat: number; lon: number }

const BASES = {
  scheme: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics',
  },
} as const
type Base = keyof typeof BASES

const VISIBLE_SIGNALS = new Set(['new', 'checking', 'confirmed'])

function parcelStyle(feature: ParcelFeature, selected: boolean, base: Base): L.PathOptions {
  const { color } = feature.properties
  const common: L.PathOptions = { weight: selected ? 4 : 2, opacity: 1 }
  const outline = selected ? '#13233A' : undefined
  if (color === 'red') return { ...common, color: outline ?? '#C23A26', className: 'parcel parcel--red' }
  if (color === 'yellow')
    return {
      ...common,
      color: outline ?? '#B98500',
      dashArray: selected ? undefined : '7 5',
      fillColor: '#F2C230',
      fillOpacity: base === 'satellite' ? 0.45 : 0.38,
      className: 'parcel',
    }
  return {
    ...common,
    weight: selected ? 4 : 1.5,
    color: outline ?? '#23864A',
    fillColor: '#2E9D58',
    fillOpacity: base === 'satellite' ? 0.35 : 0.24,
    className: 'parcel',
  }
}

function signalIcon(signal: SignalItem, fresh: boolean, selected: boolean) {
  const cls = ['sig', `sig--${signal.status}`, fresh && 'sig--fresh', selected && 'sig--selected'].filter(Boolean)
  return L.divIcon({
    className: 'sig-wrap',
    html: `<span class="${cls.join(' ')}"><i></i></span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  })
}

const OVERVIEW_ZOOM = 15
const DOT_STYLE: Record<ParcelFeature['properties']['color'], L.CircleMarkerOptions> = {
  green: { color: '#fff', weight: 2, fillColor: '#2E9D58', fillOpacity: 1 },
  yellow: { color: '#B98500', weight: 2, dashArray: '3 2', fillColor: '#F2C230', fillOpacity: 1 },
  red: { color: '#fff', weight: 2, fillColor: '#D1402B', fillOpacity: 1 },
}

/** На обзорном масштабе мелкие участки (ИЖС ~30 м) не видны — дублируем их точками в цвете статуса. */
function ParcelDots({ parcels, onSelect }: { parcels: ParcelCollection; onSelect: (s: Selection) => void }) {
  const map = useMap()
  const [zoom, setZoom] = useState(map.getZoom())
  useMapEvent('zoomend', () => setZoom(map.getZoom()))
  const centroids = useMemo(
    () => parcels.features.map((f) => ({ f, center: L.geoJSON(f).getBounds().getCenter() })),
    [parcels],
  )
  if (zoom >= OVERVIEW_ZOOM) return null
  return (
    <>
      {centroids.map(({ f, center }) => (
        <CircleMarker
          key={`${f.id}-${f.properties.color}`}
          center={center}
          radius={f.properties.color === 'green' ? 5 : 7}
          pathOptions={DOT_STYLE[f.properties.color]}
          eventHandlers={{ click: () => onSelect({ kind: 'parcel', id: f.id }) }}
        >
          <Tooltip direction="top" offset={[0, -6]} className="map-tip">
            <b className="mono">{f.properties.cadastral_no}</b>
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  )
}

function FocusController({ focus }: { focus: Focus | null }) {
  const map = useMap()
  useEffect(() => {
    if (!focus) return
    // справа открыта карточка — центрируем объект в видимой части карты
    const drawerWidth = document.querySelector('.drawer')?.clientWidth ?? 0
    const drawer = drawerWidth < map.getSize().x - 200 ? drawerWidth : 0
    const bounds =
      focus.kind === 'parcel'
        ? L.geoJSON(focus.feature).getBounds()
        : L.latLng(focus.lat, focus.lon).toBounds(250)
    map.flyToBounds(bounds, {
      maxZoom: 17,
      paddingTopLeft: [60, 60],
      paddingBottomRight: [drawer + 60, 60],
      duration: 0.8,
    })
  }, [focus, map])
  return null
}

interface Props {
  parcels: ParcelCollection
  signals: SignalItem[]
  version: number
  selection: Selection | null
  freshSignals: Set<number>
  focus: Focus | null
  route: RoutePlan | null
  onSelect: (selection: Selection) => void
}

export default function MapView({ parcels, signals, version, selection, freshSignals, focus, route, onSelect }: Props) {
  const i = useI18n()
  const [base, setBase] = useState<Base>('scheme')
  const [heat, setHeat] = useState(false)
  // начальный вид вычисляется один раз, дальше карту двигает пользователь
  const [bounds] = useState(() => L.geoJSON(parcels as GeoJSON.FeatureCollection).getBounds().pad(0.05))
  const selectedParcel = selection?.kind === 'parcel' ? selection.id : null
  const selectedSignal = selection?.kind === 'signal' ? selection.id : null

  return (
    <div className={`map-wrap map-wrap--${base}`}>
      <MapContainer bounds={bounds} zoomControl={false} className="map" preferCanvas={false}>
        <TileLayer key={base} url={BASES[base].url} attribution={BASES[base].attribution} maxZoom={19} />
        <ZoomControl position="topleft" />
        <GeoJSON
          key={`${version}-${selectedParcel}-${base}`}
          data={parcels as GeoJSON.FeatureCollection}
          style={(f) => parcelStyle(f as ParcelFeature, (f as ParcelFeature).id === selectedParcel, base)}
          onEachFeature={(f, layer) => {
            const feature = f as ParcelFeature
            layer.on('click', () => onSelect({ kind: 'parcel', id: feature.id }))
            layer.bindTooltip(
              `<b class="mono">${escapeHtml(feature.properties.cadastral_no)}</b><br>${i.d.lifecycle[feature.properties.lifecycle]}`,
              { sticky: true, className: 'map-tip', direction: 'top', offset: [0, -8] },
            )
          }}
        />
        <ParcelDots parcels={parcels} onSelect={onSelect} />
        {signals
          .filter((s) => VISIBLE_SIGNALS.has(s.status) || s.id === selectedSignal)
          .map((s) => (
            <Marker
              key={`${s.id}-${s.status}-${freshSignals.has(s.id)}-${s.id === selectedSignal}`}
              position={[s.lat, s.lon]}
              icon={signalIcon(s, freshSignals.has(s.id), s.id === selectedSignal)}
              zIndexOffset={freshSignals.has(s.id) ? 1000 : 0}
              eventHandlers={{ click: () => onSelect({ kind: 'signal', id: s.id }) }}
            >
              <Tooltip direction="top" offset={[0, -12]} className="map-tip">
                <b className="mono">{s.code}</b> · {i.d.signalStatus[s.status]}
              </Tooltip>
            </Marker>
          ))}
        {heat && <HeatLayer signals={signals} />}
        {route && <RouteLayer plan={route} />}
        <FocusController focus={focus} />
      </MapContainer>

      <div className="base-switch" role="group" aria-label="Подложка">
        {(['scheme', 'satellite'] as Base[]).map((b) => (
          <button key={b} className={b === base ? 'is-active' : ''} onClick={() => setBase(b)} aria-pressed={b === base}>
            {b === 'scheme' ? i.t('baseScheme') : i.t('baseSatellite')}
          </button>
        ))}
        <button className={heat ? 'is-active' : ''} onClick={() => setHeat((h) => !h)} aria-pressed={heat}>
          🔥 {i.t('heatmap')}
        </button>
      </div>

      <div className="legend">
        <div className="legend__row">
          <span className="swatch swatch--green" /> {i.t('legendGreen')}
        </div>
        <div className="legend__row">
          <span className="swatch swatch--yellow" /> {i.t('legendYellow')}
        </div>
        <div className="legend__row">
          <span className="swatch swatch--red" /> {i.t('legendRed')}
        </div>
        <div className="legend__row">
          <span className="swatch swatch--signal" /> {i.t('legendSignal')}
        </div>
      </div>
    </div>
  )
}
