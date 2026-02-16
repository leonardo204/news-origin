import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTheme } from './useTheme'

describe('useTheme', () => {
  let matchMediaMock: ReturnType<typeof vi.fn>
  const localStorageMock = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
    length: 0,
    key: vi.fn(),
  }

  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', { value: localStorageMock, writable: true })

    matchMediaMock = vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })
    Object.defineProperty(window, 'matchMedia', { value: matchMediaMock, writable: true })

    document.documentElement.classList.remove('dark')
    vi.clearAllMocks()
  })

  afterEach(() => {
    document.documentElement.classList.remove('dark')
  })

  it('defaults to dark theme when no stored preference', () => {
    localStorageMock.getItem.mockReturnValue(null)

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('dark')
    expect(result.current.resolvedTheme).toBe('dark')
  })

  it('restores stored theme preference', () => {
    localStorageMock.getItem.mockReturnValue('light')

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('light')
    expect(result.current.resolvedTheme).toBe('light')
  })

  it('setTheme changes theme and persists to localStorage', () => {
    localStorageMock.getItem.mockReturnValue('dark')

    const { result } = renderHook(() => useTheme())

    act(() => {
      result.current.setTheme('light')
    })

    expect(result.current.theme).toBe('light')
    expect(localStorageMock.setItem).toHaveBeenCalledWith('theme', 'light')
  })

  it('system theme resolves based on matchMedia', () => {
    localStorageMock.getItem.mockReturnValue('system')
    matchMediaMock.mockReturnValue({
      matches: true, // prefers dark
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('system')
    expect(result.current.resolvedTheme).toBe('dark')
  })

  it('system theme resolves to light when no dark preference', () => {
    localStorageMock.getItem.mockReturnValue('system')
    matchMediaMock.mockReturnValue({
      matches: false, // prefers light
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('system')
    expect(result.current.resolvedTheme).toBe('light')
  })

  it('adds dark class to documentElement when dark theme', () => {
    localStorageMock.getItem.mockReturnValue('dark')

    renderHook(() => useTheme())

    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('removes dark class when light theme', () => {
    document.documentElement.classList.add('dark')
    localStorageMock.getItem.mockReturnValue('light')

    renderHook(() => useTheme())

    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('listens for system theme changes when in system mode', () => {
    const addListener = vi.fn()
    const removeListener = vi.fn()
    localStorageMock.getItem.mockReturnValue('system')
    matchMediaMock.mockReturnValue({
      matches: false,
      addEventListener: addListener,
      removeEventListener: removeListener,
    })

    const { unmount } = renderHook(() => useTheme())

    expect(addListener).toHaveBeenCalledWith('change', expect.any(Function))

    unmount()
    expect(removeListener).toHaveBeenCalledWith('change', expect.any(Function))
  })

  it('does not listen for system changes when not in system mode', () => {
    const addListener = vi.fn()
    localStorageMock.getItem.mockReturnValue('dark')
    matchMediaMock.mockReturnValue({
      matches: false,
      addEventListener: addListener,
      removeEventListener: vi.fn(),
    })

    renderHook(() => useTheme())

    expect(addListener).not.toHaveBeenCalled()
  })
})
