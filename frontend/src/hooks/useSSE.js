import { useState, useEffect } from 'react'
import useAuthStore from '../store/authStore'

export function useSSE(runId) {
  const [data, setData] = useState(null)
  const [connected, setConnected] = useState(false)
  const [closed, setClosed] = useState(false)
  const token = useAuthStore(s => s.token)

  useEffect(() => {
    if (!runId) return

    const url = token
      ? `/api/v1/runs/${runId}/stream?token=${encodeURIComponent(token)}`
      : `/api/v1/runs/${runId}/stream`

    const es = new EventSource(url)

    es.onopen = () => setConnected(true)

    es.onmessage = (e) => {
      try {
        setData(JSON.parse(e.data))
      } catch {
        setData(e.data)
      }
    }

    es.addEventListener('done', () => {
      setClosed(true)
      es.close()
    })

    es.addEventListener('error_event', () => {
      setClosed(true)
      es.close()
    })

    es.onerror = () => {
      setConnected(false)
    }

    return () => {
      es.close()
    }
  }, [runId, token])

  return { data, connected, closed }
}
