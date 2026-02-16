import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ThemeToggle from './ThemeToggle'

// Mock useTheme hook
const mockSetTheme = vi.fn()
vi.mock('@/hooks/useTheme', () => ({
  useTheme: vi.fn(() => ({
    theme: 'dark',
    setTheme: mockSetTheme,
    resolvedTheme: 'dark',
  })),
}))

import { useTheme } from '@/hooks/useTheme'

describe('ThemeToggle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useTheme).mockReturnValue({
      theme: 'dark',
      setTheme: mockSetTheme,
      resolvedTheme: 'dark',
    })
  })

  it('renders with current theme label', () => {
    render(<ThemeToggle />)

    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-label', '테마: 다크')
    expect(button).toHaveAttribute('title', '현재: 다크 모드')
  })

  it('renders light theme label when light', () => {
    vi.mocked(useTheme).mockReturnValue({
      theme: 'light',
      setTheme: mockSetTheme,
      resolvedTheme: 'light',
    })

    render(<ThemeToggle />)

    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-label', '테마: 라이트')
  })

  it('renders system theme label when system', () => {
    vi.mocked(useTheme).mockReturnValue({
      theme: 'system',
      setTheme: mockSetTheme,
      resolvedTheme: 'dark',
    })

    render(<ThemeToggle />)

    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-label', '테마: 시스템')
  })

  it('cycles from light → dark on click', async () => {
    const user = userEvent.setup()
    vi.mocked(useTheme).mockReturnValue({
      theme: 'light',
      setTheme: mockSetTheme,
      resolvedTheme: 'light',
    })

    render(<ThemeToggle />)

    await user.click(screen.getByRole('button'))
    expect(mockSetTheme).toHaveBeenCalledWith('dark')
  })

  it('cycles from dark → system on click', async () => {
    const user = userEvent.setup()
    vi.mocked(useTheme).mockReturnValue({
      theme: 'dark',
      setTheme: mockSetTheme,
      resolvedTheme: 'dark',
    })

    render(<ThemeToggle />)

    await user.click(screen.getByRole('button'))
    expect(mockSetTheme).toHaveBeenCalledWith('system')
  })

  it('cycles from system → light on click', async () => {
    const user = userEvent.setup()
    vi.mocked(useTheme).mockReturnValue({
      theme: 'system',
      setTheme: mockSetTheme,
      resolvedTheme: 'dark',
    })

    render(<ThemeToggle />)

    await user.click(screen.getByRole('button'))
    expect(mockSetTheme).toHaveBeenCalledWith('light')
  })
})
