import L from 'leaflet'
import { useEffect } from 'react'
import { Marker, Polyline, useMap } from 'react-leaflet'
import type { RoutePlan, SignalItem } from '../api'

/** Тепловая карта всех сигналов жителей (вес = число сообщений о месте). */
export function HeatLayer({ signals }: { signals: SignalItem[] }) {
  const map = useMap()
  useEffect(() => {
    let layer: L.Layer | null = null
    let cancelled = false
    ;(async () => {
      // leaflet.heat — UMD-плагин, ему нужен глобальный L
      ;(window as unknown as { L: typeof L }).L = L
      await import('leaflet.heat')
      if (cancelled) return
      const points = signals.map((s) => [s.lat, s.lon, Math.min(1, 0.4 + 0.2 * s.reports)] as [number, number, number])
      layer = (L as unknown as { heatLayer: (p: typeof points, o: object) => L.Layer }).heatLayer(points, {
        radius: 34,
        blur: 26,
        maxZoom: 15,
        gradient: { 0.3: '#5b3fd6', 0.6: '#e3a600', 1: '#d1402b' },
      })
      layer.addTo(map)
    })()
    return () => {
      cancelled = true
      if (layer) map.removeLayer(layer)
    }
  }, [map, signals])
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
  useEffect(() => {
    if (line.length > 1) map.flyToBounds(L.latLngBounds(line), { padding: [60, 60], duration: 0.8, maxZoom: 15 })
  }, [plan]) // eslint-disable-line react-hooks/exhaustive-deps
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
