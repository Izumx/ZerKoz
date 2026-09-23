export type Color = 'green' | 'yellow' | 'red'
export type Lifecycle = 'none' | 'detected' | 'in_progress' | 'resolved' | 'returned'
export type ViolationType = 'unused' | 'seizure' | 'dump'
export type SignalStatus = 'new' | 'checking' | 'confirmed' | 'rejected' | 'resolved'
export type Purpose = 'izhs' | 'agri' | 'commercial' | 'industrial' | 'lph'

export interface ParcelProps {
  id: number
  cadastral_no: string
  purpose: Purpose
  area_ha: number
  address: string
  owner: string
  lifecycle: Lifecycle
  violation_type: ViolationType | null
  deadline: string | null
  under_check: boolean
  open_signals: number
  color: Color
  overdue: boolean
  updated_at: string
}

export interface ParcelFeature {
  type: 'Feature'
  id: number
  geometry: GeoJSON.Polygon
  properties: ParcelProps
}

export interface ParcelCollection {
  type: 'FeatureCollection'
  features: ParcelFeature[]
}

export interface Photo {
  id: number
  url: string
  source: 'inspector' | 'citizen'
  signal_id: number | null
  created_at: string
}

export interface HistoryItem {
  entity: 'parcel' | 'signal'
  entity_id: number
  action: 'created' | 'status' | 'lifecycle' | 'updated' | 'photos'
  payload: Record<string, string | number | boolean | null>
  created_at: string
}

export interface ParcelDetail extends ParcelProps {
  geometry: GeoJSON.Polygon
  ndvi_series: number[]
  photos: Photo[]
  signals: { id: number; code: string; status: SignalStatus; description: string; created_at: string }[]
  history: HistoryItem[]
}

export interface SignalItem {
  id: number
  code: string
  lat: number
  lon: number
  description: string
  source: 'telegram' | 'demo' | 'seed'
  lang: string
  status: SignalStatus
  parcel: { id: number; cadastral_no: string; lifecycle: Lifecycle } | null
  has_citizen: boolean
  photos: Photo[]
  created_at: string
  updated_at: string
  history?: HistoryItem[]
}

export interface Stats {
  total: number
  green: number
  yellow: number
  red: number
  overdue: number
  signals_new: number
  signals_open: number
  signals_24h: number
}

export interface Health {
  ok: boolean
  bot_username: string | null
}

export interface ParcelPatch {
  lifecycle?: Lifecycle
  violation_type?: ViolationType | null
  deadline?: string | null
  under_check?: boolean
}

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch {
    throw new ApiError('Сервер недоступен', 0)
  }
  if (!response.ok) {
    let message = response.statusText
    try {
      message = (await response.json()).detail ?? message
    } catch {
      /* тело не JSON */
    }
    throw new ApiError(String(message), response.status)
  }
  return response.json() as Promise<T>
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  parcels: () => request<ParcelCollection>('/api/parcels'),
  parcel: (id: number) => request<ParcelDetail>(`/api/parcels/${id}`),
  patchParcel: (id: number, patch: ParcelPatch) => request<ParcelDetail>(`/api/parcels/${id}`, json('PATCH', patch)),
  uploadPhotos: (id: number, files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request<ParcelDetail>(`/api/parcels/${id}/photos`, { method: 'POST', body: form })
  },
  signals: () => request<SignalItem[]>('/api/signals'),
  signal: (id: number) => request<SignalItem>(`/api/signals/${id}`),
  patchSignal: (id: number, status: SignalStatus, violation_type?: ViolationType) =>
    request<SignalItem>(`/api/signals/${id}`, json('PATCH', { status, violation_type })),
  stats: () => request<Stats>('/api/stats'),
  health: () => request<Health>('/api/health'),
  demoSignal: () => request<SignalItem>('/api/demo/signal', { method: 'POST' }),
}
