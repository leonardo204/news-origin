import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ArticleList from './ArticleList'
import type { TimelineItem } from '@/types'

const mockItems: TimelineItem[] = [
  {
    article_id: '1',
    title: '기원 기사 제목',
    publisher: '한국일보',
    published_at: '2024-01-15T10:00:00Z',
    similarity_score: 1.0,
    lifecycle_stage: 'origin',
    url: 'https://example.com/1',
  },
  {
    article_id: '2',
    title: '확산 기사 제목',
    publisher: '조선일보',
    published_at: '2024-01-15T12:00:00Z',
    similarity_score: 0.85,
    lifecycle_stage: 'spread',
    url: 'https://example.com/2',
  },
  {
    article_id: '3',
    title: '폭발 기사 제목',
    publisher: '중앙일보',
    published_at: '2024-01-15T14:00:00Z',
    similarity_score: 0.72,
    lifecycle_stage: 'explosion',
    url: null,
  },
  {
    article_id: '4',
    title: '고립 기사 제목',
    publisher: '매일경제',
    published_at: '2024-01-15T16:00:00Z',
    similarity_score: 0.45,
    lifecycle_stage: 'isolated',
    url: 'https://example.com/4',
  },
]

describe('ArticleList', () => {
  it('renders nothing when items is empty', () => {
    const { container } = render(<ArticleList items={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders article count', () => {
    render(<ArticleList items={mockItems} />)
    expect(screen.getByText('4건')).toBeInTheDocument()
  })

  it('renders all article titles', () => {
    render(<ArticleList items={mockItems} />)
    expect(screen.getByText('기원 기사 제목')).toBeInTheDocument()
    expect(screen.getByText('확산 기사 제목')).toBeInTheDocument()
    expect(screen.getByText('폭발 기사 제목')).toBeInTheDocument()
    expect(screen.getByText('고립 기사 제목')).toBeInTheDocument()
  })

  it('renders publisher names', () => {
    render(<ArticleList items={mockItems} />)
    expect(screen.getByText('한국일보')).toBeInTheDocument()
    expect(screen.getByText('조선일보')).toBeInTheDocument()
  })

  it('renders similarity scores', () => {
    render(<ArticleList items={mockItems} />)
    expect(screen.getByText('100.0%')).toBeInTheDocument()
    expect(screen.getByText('85.0%')).toBeInTheDocument()
    expect(screen.getByText('72.0%')).toBeInTheDocument()
  })

  it('renders lifecycle badges', () => {
    render(<ArticleList items={mockItems} />)
    expect(screen.getByText('기원')).toBeInTheDocument()
    expect(screen.getByText('확산')).toBeInTheDocument()
    expect(screen.getByText('폭발')).toBeInTheDocument()
    expect(screen.getByText('고립')).toBeInTheDocument()
  })

  it('shows filter panel when filter button is clicked', () => {
    render(<ArticleList items={mockItems} />)
    fireEvent.click(screen.getByText('필터'))
    expect(screen.getByText('단계별 필터')).toBeInTheDocument()
  })

  it('filters by lifecycle stage', () => {
    render(<ArticleList items={mockItems} />)
    // Open filter
    fireEvent.click(screen.getByText('필터'))
    // Click on "기원" filter button (first "기원" = filter panel, second = badge in table)
    const stageButtons = screen.getAllByText('기원')
    fireEvent.click(stageButtons[0])

    // Should show filtered count
    expect(screen.getByText(/1건 \/ 전체 4건/)).toBeInTheDocument()
  })

  it('resets filter when reset button is clicked', () => {
    render(<ArticleList items={mockItems} />)
    fireEvent.click(screen.getByText('필터'))
    // Activate a filter (first "기원" = filter button)
    const stageButtons = screen.getAllByText('기원')
    fireEvent.click(stageButtons[0])
    // Click reset
    fireEvent.click(screen.getByText('초기화'))
    // Should show full count again
    expect(screen.getByText('4건')).toBeInTheDocument()
  })

  it('shows empty state when filter matches nothing', () => {
    const items: TimelineItem[] = [
      {
        article_id: '1',
        title: '기사',
        publisher: '뉴스',
        published_at: '2024-01-15T10:00:00Z',
        similarity_score: 1.0,
        lifecycle_stage: 'origin',
        url: null,
      },
    ]
    render(<ArticleList items={items} />)
    fireEvent.click(screen.getByText('필터'))
    // Filter by "폭발" which doesn't exist
    fireEvent.click(screen.getByText('폭발'))
    expect(screen.getByText('필터 조건에 맞는 기사가 없습니다.')).toBeInTheDocument()
  })

  it('sorts by similarity score descending when header clicked', () => {
    render(<ArticleList items={mockItems} />)
    // Click similarity header
    fireEvent.click(screen.getByText('유사도'))

    // Get all score elements
    const scores = screen.getAllByText(/%$/)
    expect(scores[0].textContent).toBe('100.0%')
    expect(scores[1].textContent).toBe('85.0%')
    expect(scores[2].textContent).toBe('72.0%')
    expect(scores[3].textContent).toBe('45.0%')
  })

  it('toggles sort direction on re-click', () => {
    render(<ArticleList items={mockItems} />)
    // Click similarity header twice (first = desc default, second = asc)
    fireEvent.click(screen.getByText('유사도'))
    fireEvent.click(screen.getByText('유사도'))

    const scores = screen.getAllByText(/%$/)
    expect(scores[0].textContent).toBe('45.0%')
    expect(scores[3].textContent).toBe('100.0%')
  })

  it('renders links for articles with URLs', () => {
    render(<ArticleList items={mockItems} />)
    const links = screen.getAllByRole('link')
    expect(links.length).toBeGreaterThan(0)
    const firstLink = links.find((l) => l.getAttribute('href') === 'https://example.com/1')
    expect(firstLink).toBeTruthy()
  })
})
