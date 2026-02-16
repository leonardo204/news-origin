import { describe, it, expect } from 'vitest'
import { getErrorMessage, isRetryableError, isClientError, type ApiError } from './errors'

describe('getErrorMessage', () => {
  it('returns generic message for null/undefined', () => {
    expect(getErrorMessage(null)).toBe('알 수 없는 오류가 발생했습니다')
    expect(getErrorMessage(undefined)).toBe('알 수 없는 오류가 발생했습니다')
  })

  it('handles string errors', () => {
    expect(getErrorMessage('커스텀 에러 메시지')).toBe('커스텀 에러 메시지')
  })

  it('handles Error objects with message', () => {
    expect(getErrorMessage(new Error('네트워크 오류'))).toBe('네트워크 오류')
  })

  it('returns message for 400 status', () => {
    const error: ApiError = { name: 'ApiError', message: '', status: 400 }
    expect(getErrorMessage(error)).toBe('잘못된 요청입니다')
  })

  it('returns message for 401 status', () => {
    const error: ApiError = { name: 'ApiError', message: '', status: 401 }
    expect(getErrorMessage(error)).toBe('인증이 필요합니다')
  })

  it('returns message for 403 status', () => {
    const error: ApiError = { name: 'ApiError', message: '', status: 403 }
    expect(getErrorMessage(error)).toBe('접근 권한이 없습니다')
  })

  it('returns message for 404 status', () => {
    const error: ApiError = { name: 'ApiError', message: '', status: 404 }
    expect(getErrorMessage(error)).toBe('요청한 데이터를 찾을 수 없습니다')
  })

  it('returns message for 408 status', () => {
    const error: ApiError = { name: 'ApiError', message: '', status: 408 }
    expect(getErrorMessage(error)).toBe('요청 시간이 초과되었습니다')
  })

  it('returns message for 429 status', () => {
    const error: ApiError = { name: 'ApiError', message: '', status: 429 }
    expect(getErrorMessage(error)).toBe('너무 많은 요청입니다. 잠시 후 다시 시도해주세요')
  })

  it('returns server error message for 5xx status', () => {
    expect(getErrorMessage({ status: 500 } as ApiError)).toBe('서버에 문제가 발생했습니다. 잠시 후 다시 시도해주세요')
    expect(getErrorMessage({ status: 502 } as ApiError)).toBe('서버에 문제가 발생했습니다. 잠시 후 다시 시도해주세요')
    expect(getErrorMessage({ status: 503 } as ApiError)).toBe('서버에 문제가 발생했습니다. 잠시 후 다시 시도해주세요')
    expect(getErrorMessage({ status: 504 } as ApiError)).toBe('서버에 문제가 발생했습니다. 잠시 후 다시 시도해주세요')
  })

  it('handles ECONNABORTED code', () => {
    const error: ApiError = { name: 'ApiError', message: '', code: 'ECONNABORTED' }
    expect(getErrorMessage(error)).toBe('요청 시간이 초과되었습니다')
  })

  it('handles ETIMEDOUT code', () => {
    const error: ApiError = { name: 'ApiError', message: '', code: 'ETIMEDOUT' }
    expect(getErrorMessage(error)).toBe('요청 시간이 초과되었습니다')
  })

  it('handles network error codes', () => {
    expect(getErrorMessage({ code: 'ENOTFOUND' } as ApiError)).toBe('네트워크 연결을 확인해주세요')
    expect(getErrorMessage({ code: 'ECONNREFUSED' } as ApiError)).toBe('네트워크 연결을 확인해주세요')
    expect(getErrorMessage({ code: 'ENETUNREACH' } as ApiError)).toBe('네트워크 연결을 확인해주세요')
    expect(getErrorMessage({ code: 'ERR_NETWORK' } as ApiError)).toBe('네트워크 연결을 확인해주세요')
  })

  it('handles ERR_CANCELED code', () => {
    const error: ApiError = { name: 'ApiError', message: '', code: 'ERR_CANCELED' }
    expect(getErrorMessage(error)).toBe('요청이 취소되었습니다')
  })

  it('falls back to error message if status/code not matched', () => {
    const error: ApiError = { name: 'ApiError', message: '커스텀 메시지', status: 418 }
    expect(getErrorMessage(error)).toBe('커스텀 메시지')
  })

  it('returns generic message for unknown error types', () => {
    expect(getErrorMessage(123)).toBe('알 수 없는 오류가 발생했습니다')
    expect(getErrorMessage({})).toBe('알 수 없는 오류가 발생했습니다')
  })
})

describe('isRetryableError', () => {
  it('returns true for 5xx server errors', () => {
    expect(isRetryableError({ status: 500 } as ApiError)).toBe(true)
    expect(isRetryableError({ status: 502 } as ApiError)).toBe(true)
    expect(isRetryableError({ status: 503 } as ApiError)).toBe(true)
    expect(isRetryableError({ status: 504 } as ApiError)).toBe(true)
    expect(isRetryableError({ status: 599 } as ApiError)).toBe(true)
  })

  it('returns false for 4xx client errors', () => {
    expect(isRetryableError({ status: 400 } as ApiError)).toBe(false)
    expect(isRetryableError({ status: 401 } as ApiError)).toBe(false)
    expect(isRetryableError({ status: 404 } as ApiError)).toBe(false)
    expect(isRetryableError({ status: 429 } as ApiError)).toBe(false)
  })

  it('returns true for retryable network codes', () => {
    expect(isRetryableError({ code: 'ENOTFOUND' } as ApiError)).toBe(true)
    expect(isRetryableError({ code: 'ECONNREFUSED' } as ApiError)).toBe(true)
    expect(isRetryableError({ code: 'ENETUNREACH' } as ApiError)).toBe(true)
    expect(isRetryableError({ code: 'ERR_NETWORK' } as ApiError)).toBe(true)
  })

  it('returns false for non-retryable codes', () => {
    expect(isRetryableError({ code: 'ECONNABORTED' } as ApiError)).toBe(false)
    expect(isRetryableError({ code: 'ETIMEDOUT' } as ApiError)).toBe(false)
    expect(isRetryableError({ code: 'ERR_CANCELED' } as ApiError)).toBe(false)
  })

  it('returns false for unknown errors', () => {
    expect(isRetryableError(null)).toBe(false)
    expect(isRetryableError(undefined)).toBe(false)
    expect(isRetryableError('error string')).toBe(false)
    expect(isRetryableError({})).toBe(false)
  })
})

describe('isClientError', () => {
  it('returns true for 4xx status codes', () => {
    expect(isClientError({ status: 400 } as ApiError)).toBe(true)
    expect(isClientError({ status: 401 } as ApiError)).toBe(true)
    expect(isClientError({ status: 403 } as ApiError)).toBe(true)
    expect(isClientError({ status: 404 } as ApiError)).toBe(true)
    expect(isClientError({ status: 429 } as ApiError)).toBe(true)
    expect(isClientError({ status: 499 } as ApiError)).toBe(true)
  })

  it('returns false for non-4xx status codes', () => {
    expect(isClientError({ status: 200 } as ApiError)).toBe(false)
    expect(isClientError({ status: 500 } as ApiError)).toBe(false)
    expect(isClientError({ status: 502 } as ApiError)).toBe(false)
  })

  it('returns false for errors without status', () => {
    expect(isClientError({ code: 'ENOTFOUND' } as ApiError)).toBe(false)
    expect(isClientError(new Error('test'))).toBe(false)
    expect(isClientError(null)).toBe(false)
    expect(isClientError(undefined)).toBe(false)
  })
})
