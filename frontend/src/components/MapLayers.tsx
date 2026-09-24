import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { Marker, Polyline, useMap } from 'react-leaflet'
import type { RoutePlan, SignalItem } from '../api'

type HeatLayerType = L.Layer & { setLatLngs: (points: [number, number, number][]) => void }

const heatPoints = (signals: SignalItem[]) =>
  signals.map((s) => [s.lat, s.lon, Math.min(1, 0.4 + 0.2 * s.reports)] as [number, number, number])

/** Тепловая карта всех сигналов жителей (вес = число сообщений о месте). Слой создаётся один раз. */
export function HeatLayer({ signals }: { signals: SignalItem[] }) {
  const map = useMap()
  const layer = useRef<HeatLayerType | null>(null)
  const latest = useRef(signals)
  latest.current = signals

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      // leaflet.heat — UMD-плагин, ему нужен глобальный L
      ;(window as unknown as { L: typeof L }).L = L
      await import('leaflet.heat')
      if (cancelled) return
      const heatLayer = (L as unknown as { heatLayer: (p: [number, number, number][], o: object) => HeatLayerType }).heatLayer
      layer.current = heatLayer(heatPoints(latest.current), {
        radius: 34,
        blur: 26,
        maxZoom: 15,
        gradient: { 0.3: '#5b3fd6', 0.6: '#e3a600', 1: '#d1402b' },
      })
      layer.current.addTo(map)
    })()
    return () => {
      cancelled = true
      if (layer.current) map.removeLayer(layer.current)
      layer.current = null
    }
  }, [map])

  // новые сигналы — обновляем точки существующего слоя, без пересоздания и мигания
  useEffect(() => {
    layer.current?.setLatLngs(heatPoints(signals))
  }, [signals])
  return null
}

const numberIcon = (label: string, kind: string) =>
  L.divIcon({
    className: 'route-pin-wrap',
    html: `<span class="route-pin route-pin--${kind}">${label}</span>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  })

/** Маршрут выезда: пунктир от управления через все точки по порядку. */
export function RouteLayer({ plan }: { plan: RoutePlan }) {
  const map = useMap()
  const line: [number, number][] = [[plan.start.lat, plan.start.lon], ...plan.stops.map((s) => [s.lat, s.lon] as [number, number])]
  // приближаем только когда меняется сам набор точек, а не при каждом обновлении данных
  const stopsKey = plan.stops.map((s) => `${s.kind}${s.id}`).join(',')
  useEffect(() => {
    if (line.length > 1) map.flyToBounds(L.latLngBounds(line), { padding: [60, 60], duration: 0.8, maxZoom: 15 })
  }, [stopsKey]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <>
      <Polyline positions={line} pathOptions={{ color: '#13233A', weight: 3, dashArray: '8 6', opacity: 0.85 }} />
      <Marker position={line[0]} icon={numberIcon('★', 'start')} zIndexOffset={2000} />
      {plan.stops.map((s, k) => (
        <Marker key={`${s.kind}-${s.id}`} position={[s.lat, s.lon]} icon={numberIcon(String(k + 1), s.reason)} zIndexOffset={2000} />
      ))}
    </>
  )
}
