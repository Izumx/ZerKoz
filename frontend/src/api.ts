export type Color = 'green' | 'yellow' | 'red'
export type Lifecycle = 'none' | 'detected' | 'in_progress' | 'resolved' | 'returned'
export type ViolationType = 'unused' | 'seizure' | 'dump'
export type SignalStatus = 'new' | 'checking' | 'confirmed' | 'rejected' | 'resolved'
export type Purpose = 'izhs' | 'agri' | 'commercial' | 'industrial' | 'lph'
export type Stage = 'review' | 'inspection' | 'approved' | 'rejected'

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
  action: 'created' | 'status' | 'lifecycle' | 'updated' | 'photos' | 'duplicate' | 'ndvi_low'
  payload: Record<string, string | number | boolean | null>
  created_at: string
}

export interface ParcelDetail extends ParcelProps {
  geometry: GeoJSON.Polygon
  ndvi_series: (number | null)[]
  ndvi_months: string[]
  ndvi_source: 'simulation' | 'sentinel-2'
  photos: Photo[]
  signals: {
    id: number
    code: string
    status: SignalStatus
    description: string
    duplicate: boolean
    created_at: string
  }[]
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
  duplicate_of: { id: number; code: string } | null
  reports: number
  suggested_violation: ViolationType | null
  photos: Photo[]
  created_at: string
  updated_at: string
  duplicates?: { id: number; code: string; description: string; created_at: string }[]
  history?: HistoryItem[]
}

export interface Application {
  track_no: string
  applicant: string
  type: 'change_purpose' | 'lease_extension' | 'izhs'
  stage: Stage
  note_ru: string
  note_kz: string
  subscribers: number
  updated_at: string
}

export interface RouteStop {
  kind: 'parcel' | 'signal'
  id: number
  label: string
  address: string
  reason: 'overdue' | 'check' | 'signal'
  lat: number
  lon: number
}

export interface RoutePlan {
  start: { lat: number; lon: number }
  stops: RouteStop[]
  distance_km: number
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

export interface SessionInfo {
  auth_required: boolean
  authenticated: boolean
  demo_mode: boolean
  sentinel_enabled: boolean
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

/** Вызывается при ответе 401 — приложение показывает экран входа. */
let onUnauthorized: () => void = () => undefined
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { credentials: 'same-origin', ...init })
  } catch {
    throw new ApiError('Сервер недоступен', 0)
  }
  if (!response.ok) {
    if (response.status === 401 && !path.endsWith('/login')) onUnauthorized()
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
  session: () => request<SessionInfo>('/api/session'),
  login: (password: string) => request<{ ok: boolean }>('/api/login', json('POST', { password })),
  logout: () => request<{ ok: boolean }>('/api/logout', { method: 'POST' }),
  parcels: () => request<ParcelCollection>('/api/parcels'),
  parcel: (id: number) => request<ParcelDetail>(`/api/parcels/${id}`),
  patchParcel: (id: number, patch: ParcelPatch) => request<ParcelDetail>(`/api/parcels/${id}`, json('PATCH', patch)),
  refreshNdvi: (id: number) => request<ParcelDetail>(`/api/parcels/${id}/ndvi`, { method: 'POST' }),
  uploadPhotos: (id: number, files: File[]) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request<ParcelDetail>(`/api/parcels/${id}/photos`, { method: 'POST', body: form })
  },
  signals: () => request<SignalItem[]>('/api/signals'),
  signal: (id: number) => request<SignalItem>(`/api/signals/${id}`),
  patchSignal: (id: number, status: SignalStatus, violation_type?: ViolationType) =>
    request<SignalItem>(`/api/signals/${id}`, json('PATCH', { status, violation_type })),
  applications: () => request<Application[]>('/api/applications'),
  patchApplication: (track: string, patch: Partial<Pick<Application, 'stage' | 'note_ru' | 'note_kz'>>) =>
    request<Application>(`/api/applications/${track}`, json('PATCH', patch)),
  route: () => request<RoutePlan>('/api/route'),
  stats: () => request<Stats>('/api/stats'),
  demoSignal: () => request<SignalItem>('/api/demo/signal', { method: 'POST' }),
}
