import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import BookmarkButton from './BookmarkButton'
import { useBookmarkStore } from '@/stores/useBookmarkStore'

describe('BookmarkButton', () => {
  const defaultProps = {
    articleId: 'article-1',
    title: '테스트 기사',
    publisher: '테스트 언론사',
    url: 'https://example.com/article-1',
  }

  beforeEach(() => {
    useBookmarkStore.setState({ bookmarks: [] })
  })

  it('renders unbookmarked state by default', () => {
    render(<BookmarkButton {...defaultProps} />)

    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-label', '북마크 추가')
    expect(button).toHaveAttribute('title', '북마크 추가')
  })

  it('renders bookmarked state when article is bookmarked', () => {
    useBookmarkStore.getState().addBookmark(defaultProps)

    render(<BookmarkButton {...defaultProps} />)

    const button = screen.getByRole('button')
    expect(button).toHaveAttribute('aria-label', '북마크 제거')
    expect(button).toHaveAttribute('title', '북마크 제거')
  })

  it('adds bookmark on click when not bookmarked', async () => {
    const user = userEvent.setup()
    render(<BookmarkButton {...defaultProps} />)

    await user.click(screen.getByRole('button'))

    expect(useBookmarkStore.getState().isBookmarked('article-1')).toBe(true)
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', '북마크 제거')
  })

  it('removes bookmark on click when already bookmarked', async () => {
    const user = userEvent.setup()
    useBookmarkStore.getState().addBookmark(defaultProps)

    render(<BookmarkButton {...defaultProps} />)

    await user.click(screen.getByRole('button'))

    expect(useBookmarkStore.getState().isBookmarked('article-1')).toBe(false)
    expect(screen.getByRole('button')).toHaveAttribute('aria-label', '북마크 추가')
  })

  it('stops event propagation on click', async () => {
    const user = userEvent.setup()
    const parentClickHandler = vi.fn()

    render(
      <div onClick={parentClickHandler}>
        <BookmarkButton {...defaultProps} />
      </div>,
    )

    await user.click(screen.getByRole('button'))

    expect(parentClickHandler).not.toHaveBeenCalled()
  })

  it('renders with custom className', () => {
    render(<BookmarkButton {...defaultProps} className="custom-class" />)

    const button = screen.getByRole('button')
    expect(button.className).toContain('custom-class')
  })

  it('works without publisher prop', async () => {
    const user = userEvent.setup()
    const props = {
      articleId: 'article-2',
      title: '기사 제목',
      url: 'https://example.com/2',
    }

    render(<BookmarkButton {...props} />)

    await user.click(screen.getByRole('button'))

    const bookmarks = useBookmarkStore.getState().bookmarks
    expect(bookmarks[0].publisher).toBeUndefined()
  })
})
