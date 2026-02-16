import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import EmptyState from './EmptyState'

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="데이터 없음" description="아직 데이터가 없습니다." />)
    expect(screen.getByText('데이터 없음')).toBeInTheDocument()
    expect(screen.getByText('아직 데이터가 없습니다.')).toBeInTheDocument()
  })

  it('renders title only without description', () => {
    render(<EmptyState title="빈 상태" />)
    expect(screen.getByText('빈 상태')).toBeInTheDocument()
    expect(screen.queryByText('아직 데이터가 없습니다.')).not.toBeInTheDocument()
  })

  it('renders action button when provided', () => {
    const onClick = vi.fn()
    render(<EmptyState title="없음" action={{ label: '새로고침', onClick }} />)

    const button = screen.getByText('새로고침')
    expect(button).toBeInTheDocument()

    fireEvent.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('renders icon when provided', () => {
    render(<EmptyState title="없음" icon={<span data-testid="custom-icon">아이콘</span>} />)
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument()
    expect(screen.getByText('아이콘')).toBeInTheDocument()
  })

  it('renders without icon when not provided', () => {
    render(<EmptyState title="없음" />)
    expect(screen.queryByTestId('custom-icon')).not.toBeInTheDocument()
  })

  it('renders all props together', () => {
    const onClick = vi.fn()
    render(
      <EmptyState
        title="검색 결과 없음"
        description="다른 키워드로 검색해보세요"
        icon={<span data-testid="search-icon">🔍</span>}
        action={{ label: '다시 검색', onClick }}
      />
    )

    expect(screen.getByText('검색 결과 없음')).toBeInTheDocument()
    expect(screen.getByText('다른 키워드로 검색해보세요')).toBeInTheDocument()
    expect(screen.getByTestId('search-icon')).toBeInTheDocument()
    expect(screen.getByText('다시 검색')).toBeInTheDocument()

    fireEvent.click(screen.getByText('다시 검색'))
    expect(onClick).toHaveBeenCalled()
  })

  it('button has correct styling classes', () => {
    const onClick = vi.fn()
    render(<EmptyState title="없음" action={{ label: '액션', onClick }} />)

    const button = screen.getByText('액션')
    expect(button).toHaveClass('rounded-lg', 'border', 'border-border')
  })
})
