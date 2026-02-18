/**
 * useNetworkStatus
 * v1.0.0 - 네트워크 온/오프라인 상태 추적 훅
 */
import { useState, useEffect, useCallback } from 'react'

export function useNetworkStatus() {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [wasOffline, setWasOffline] = useState(false)

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true)
      if (!navigator.onLine) return
      setWasOffline(true)
      // Auto-dismiss "back online" after 3s
      setTimeout(() => setWasOffline(false), 3000)
    }
    const handleOffline = () => {
      setIsOnline(false)
    }
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  const dismiss = useCallback(() => setWasOffline(false), [])

  return { isOnline, wasOffline, dismiss }
}
