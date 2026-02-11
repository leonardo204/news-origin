import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useToastStore, toast } from './useToastStore'

describe('useToastStore', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useToastStore.setState({ toasts: [] })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts with empty toasts', () => {
    expect(useToastStore.getState().toasts).toEqual([])
  })

  it('adds a toast', () => {
    useToastStore.getState().addToast('success', 'Test message')
    const toasts = useToastStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0].type).toBe('success')
    expect(toasts[0].message).toBe('Test message')
  })

  it('removes a toast by id', () => {
    useToastStore.getState().addToast('info', 'Toast 1')
    const id = useToastStore.getState().toasts[0].id
    useToastStore.getState().removeToast(id)
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('auto-dismisses after 4 seconds', () => {
    useToastStore.getState().addToast('error', 'Will disappear')
    expect(useToastStore.getState().toasts).toHaveLength(1)

    vi.advanceTimersByTime(4000)
    expect(useToastStore.getState().toasts).toHaveLength(0)
  })

  it('supports multiple toasts', () => {
    useToastStore.getState().addToast('success', 'First')
    useToastStore.getState().addToast('error', 'Second')
    expect(useToastStore.getState().toasts).toHaveLength(2)
  })
})

describe('toast helpers', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useToastStore.setState({ toasts: [] })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('toast.success adds success toast', () => {
    toast.success('OK!')
    const toasts = useToastStore.getState().toasts
    expect(toasts[0].type).toBe('success')
  })

  it('toast.error adds error toast', () => {
    toast.error('Failed!')
    const toasts = useToastStore.getState().toasts
    expect(toasts[0].type).toBe('error')
  })

  it('toast.info adds info toast', () => {
    toast.info('FYI')
    const toasts = useToastStore.getState().toasts
    expect(toasts[0].type).toBe('info')
  })
})
