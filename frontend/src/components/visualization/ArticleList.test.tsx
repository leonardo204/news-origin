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
    summary: null,
    is_origin: true,
    is_user_selected: false,
  },
  {
    article_id: '2',
    title: '확산 기사 제목',
    publisher: '조선일보',
    published_at: '2024-01-15T12:00:00Z',
    similarity_score: 0.85,
    lifecycle_stage: 'spread',
    url: 'https://example.com/2',
    summary: null,
    is_origin: false,
    is_user_selected: true,
  },
  {
    article_id: '3',
    title: '폭발 기사 제목',
    publisher: '중앙일보',
    published_at: '2024-01-15T14:00:00Z',
    similarity_score: 0.72,
    lifecycle_stage: 'explosion',
    url: null,
    summary: null,
    is_origin: false,
    is_user_selected: false,
  },
]

describe('ArticleList', () => {
  it('renders nothing when items is empty', () => {
    const { container } = render(<ArticleList items={[]} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders article count', () => {
    render(<ArticleList items={mockItems} />)
    expect(screen.getByText('3건')).toBeInTheDocument()
  })

  it('renders all article titles', () => {
    render(<ArticleList items={mockItems} />)
    // Desktop + mobile layouts both render, so titles appear twice
    expect(screen.getAllByText('기원 기사 제목').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('확산 기사 제목').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('폭발 기사 제목').length).toBeGreaterThanOrEqual(1)
  })

  it('renders publisher names', () => {
    render(<ArticleList items={mockItems} />)
    expect(screen.getAllByText('한국일보').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('조선일보').length).toBeGreaterThanOrEqual(1)
  })

  it('renders similarity scores', () => {
    render(<ArticleList items={mockItems} />)
    expect(screen.getAllByText('100.0%').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('85.0%').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('72.0%').length).toBeGreaterThanOrEqual(1)
  })

  it('renders lifecycle badges', () => {
    render(<ArticleList items={mockItems} />)
    expect(screen.getAllByText('기원').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('확산').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('폭발').length).toBeGreaterThanOrEqual(1)
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
    expect(screen.getByText(/1건 \/ 전체 3건/)).toBeInTheDocument()
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
    expect(screen.getByText('3건')).toBeInTheDocument()
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
        summary: null,
        is_origin: true,
        is_user_selected: false,
      },
    ]
    render(<ArticleList items={items} />)
    fireEvent.click(screen.getByText('필터'))
    // Filter by "폭발" which doesn't exist
    fireEvent.click(screen.getByText('폭발'))
    // Desktop + mobile both show empty state
    expect(screen.getAllByText('필터 조건에 맞는 기사가 없습니다.').length).toBeGreaterThanOrEqual(1)
  })

  it('sorts by similarity score descending when header clicked', () => {
    render(<ArticleList items={mockItems} />)
    // Click similarity header (use getAllByText since both desktop header and mobile sort show '유사도')
    const similarityButtons = screen.getAllByText('유사도')
    fireEvent.click(similarityButtons[0])

    // Get all score elements
    const scores = screen.getAllByText(/%$/)
    expect(scores[0].textContent).toBe('100.0%')
    expect(scores[1].textContent).toBe('85.0%')
    expect(scores[2].textContent).toBe('72.0%')
  })

  it('toggles sort direction on re-click', () => {
    render(<ArticleList items={mockItems} />)
    // Click similarity header twice (first = desc default, second = asc)
    const similarityButtons = screen.getAllByText('유사도')
    fireEvent.click(similarityButtons[0])
    fireEvent.click(similarityButtons[0])

    const scores = screen.getAllByText(/%$/)
    expect(scores[0].textContent).toBe('72.0%')
    expect(scores[2].textContent).toBe('100.0%')
  })

  it('renders links for articles with URLs', () => {
    render(<ArticleList items={mockItems} />)
    const links = screen.getAllByRole('link')
    expect(links.length).toBeGreaterThan(0)
    const firstLink = links.find((l) => l.getAttribute('href') === 'https://example.com/1')
    expect(firstLink).toBeTruthy()
  })
})
