/**
 * API 에러 처리 유틸리티
 *
 * HTTP 상태 코드 및 네트워크 에러를 한국어 메시지로 변환
 */

export interface ApiError extends Error {
  code?: string
  status?: number
}

/**
 * 에러를 사용자 친화적인 한국어 메시지로 변환
 */
export function getErrorMessage(error: unknown): string {
  if (!error) return '알 수 없는 오류가 발생했습니다'

  // ApiError 타입 체크
  if (typeof error === 'object' && error !== null) {
    const apiError = error as ApiError

    // HTTP 상태 코드별 메시지
    if (apiError.status) {
      switch (apiError.status) {
        case 400:
          return '잘못된 요청입니다'
        case 401:
          return '인증이 필요합니다'
        case 403:
          return '접근 권한이 없습니다'
        case 404:
          return '요청한 데이터를 찾을 수 없습니다'
        case 408:
          return '요청 시간이 초과되었습니다'
        case 429:
          return '너무 많은 요청입니다. 잠시 후 다시 시도해주세요'
        case 500:
        case 502:
        case 503:
        case 504:
          return '서버에 문제가 발생했습니다. 잠시 후 다시 시도해주세요'
      }
    }

    // 에러 코드별 메시지
    if (apiError.code) {
      switch (apiError.code) {
        case 'ECONNABORTED':
        case 'ETIMEDOUT':
          return '요청 시간이 초과되었습니다'
        case 'ENOTFOUND':
        case 'ECONNREFUSED':
        case 'ENETUNREACH':
          return '네트워크 연결을 확인해주세요'
        case 'ERR_NETWORK':
          return '네트워크 연결을 확인해주세요'
        case 'ERR_CANCELED':
          return '요청이 취소되었습니다'
      }
    }

    // 기본 에러 메시지
    if ('message' in apiError && apiError.message) {
      return apiError.message
    }
  }

  // 문자열 에러
  if (typeof error === 'string') {
    return error
  }

  return '알 수 없는 오류가 발생했습니다'
}

/**
 * 에러가 재시도 가능한지 판단
 * 5xx 에러 또는 네트워크 에러만 재시도
 */
export function isRetryableError(error: unknown): boolean {
  if (typeof error === 'object' && error !== null) {
    const apiError = error as ApiError

    // 5xx 서버 에러는 재시도 가능
    if (apiError.status && apiError.status >= 500 && apiError.status < 600) {
      return true
    }

    // 네트워크 에러는 재시도 가능 (타임아웃 제외)
    if (apiError.code) {
      const retryableCodes = ['ENOTFOUND', 'ECONNREFUSED', 'ENETUNREACH', 'ERR_NETWORK']
      return retryableCodes.includes(apiError.code)
    }
  }

  return false
}

/**
 * 에러가 클라이언트 에러인지 판단 (4xx)
 */
export function isClientError(error: unknown): boolean {
  if (typeof error === 'object' && error !== null) {
    const apiError = error as ApiError
    return !!(apiError.status && apiError.status >= 400 && apiError.status < 500)
  }
  return false
}
