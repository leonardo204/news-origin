/**
 * NetworkStatus
 * v1.0.0 - 네트워크 상태 배너 컴포넌트 (오프라인/복귀 알림)
 */
import { WifiOff, Wifi } from 'lucide-react'
import { useNetworkStatus } from '@/hooks/useNetworkStatus'

export default function NetworkStatus() {
  const { isOnline, wasOffline, dismiss } = useNetworkStatus()

  if (isOnline && !wasOffline) return null

  return (
    <div
      className={`fixed left-0 right-0 top-0 z-50 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
        !isOnline
          ? 'bg-red-600 text-white'
          : 'bg-green-600 text-white'
      }`}
    >
      {!isOnline ? (
        <>
          <WifiOff className="h-4 w-4" />
          오프라인 상태입니다. 인터넷 연결을 확인하세요.
        </>
      ) : (
        <>
          <Wifi className="h-4 w-4" />
          다시 온라인 상태입니다.
          <button onClick={dismiss} className="ml-2 underline">닫기</button>
        </>
      )}
    </div>
  )
}
