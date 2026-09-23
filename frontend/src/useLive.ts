import { useEffect, useRef, useState } from 'react'

export type LiveEvent =
  | { type: 'signal.created'; data: { id: number; code: string; lat: number; lon: number; parcel_id: number | null } }
  | { type: 'signal.updated'; data: { id: number; code: string; status: string } }
  | { type: 'parcel.updated'; data: { id: number } }
  | { type: 'resync'; data: null }

/** Подписка на Server-Sent Events. EventSource сам переподключается; после переподключения шлём resync. */
export function useLive(onEvent: (event: LiveEvent) => void): boolean {
  const [connected, setConnected] = useState(false)
  const handler = useRef(onEvent)
  handler.current = onEvent

  useEffect(() => {
    const source = new EventSource('/api/events/stream')
    let wasOpen = false
    source.onopen = () => {
      setConnected(true)
      if (wasOpen) handler.current({ type: 'resync', data: null })
      wasOpen = true
    }
    source.onerror = () => setConnected(false)
    source.onmessage = (message) => {
      try {
        handler.current(JSON.parse(message.data) as LiveEvent)
      } catch {
        /* пропускаем повреждённое сообщение */
      }
    }
    return () => source.close()
  }, [])

  return connected
}
