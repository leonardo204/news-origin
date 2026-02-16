import { create } from 'zustand'

export type ToastType = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number
}

interface ToastState {
  toasts: Toast[]
  addToast: (type: ToastType, message: string, duration?: number) => void
  removeToast: (id: string) => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (type, message, duration = 3000) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    const toast: Toast = { id, type, message, duration }

    set((state) => ({
      toasts: [...state.toasts.slice(-2), toast], // Keep max 3 (2 existing + 1 new)
    }))

    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }))
      }, duration)
    }
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}))

// Convenience helpers
export const toast = {
  success: (message: string, duration?: number) => useToastStore.getState().addToast('success', message, duration),
  error: (message: string, duration?: number) => useToastStore.getState().addToast('error', message, duration),
  warning: (message: string, duration?: number) => useToastStore.getState().addToast('warning', message, duration),
  info: (message: string, duration?: number) => useToastStore.getState().addToast('info', message, duration),
}
