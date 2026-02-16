import { describe, it, expect, beforeEach } from 'vitest'
import { useBookmarkStore } from './useBookmarkStore'

describe('useBookmarkStore', () => {
  beforeEach(() => {
    useBookmarkStore.setState({ bookmarks: [] })
  })

  it('starts with empty bookmarks', () => {
    const state = useBookmarkStore.getState()
    expect(state.bookmarks).toEqual([])
  })

  it('adds a bookmark with timestamp', () => {
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-1',
      title: '테스트 기사',
      publisher: '테스트 언론사',
      url: 'https://example.com',
    })

    const bookmarks = useBookmarkStore.getState().bookmarks
    expect(bookmarks).toHaveLength(1)
    expect(bookmarks[0].articleId).toBe('article-1')
    expect(bookmarks[0].title).toBe('테스트 기사')
    expect(bookmarks[0].publisher).toBe('테스트 언론사')
    expect(bookmarks[0].url).toBe('https://example.com')
    expect(bookmarks[0].bookmarkedAt).toBeTruthy()
  })

  it('prevents duplicate bookmarks', () => {
    const bookmark = {
      articleId: 'article-1',
      title: '테스트 기사',
      url: 'https://example.com',
    }

    useBookmarkStore.getState().addBookmark(bookmark)
    useBookmarkStore.getState().addBookmark(bookmark)

    expect(useBookmarkStore.getState().bookmarks).toHaveLength(1)
  })

  it('adds new bookmark to the beginning', () => {
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-1',
      title: '첫번째',
      url: 'https://example.com/1',
    })
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-2',
      title: '두번째',
      url: 'https://example.com/2',
    })

    const bookmarks = useBookmarkStore.getState().bookmarks
    expect(bookmarks[0].articleId).toBe('article-2')
    expect(bookmarks[1].articleId).toBe('article-1')
  })

  it('removes a bookmark by articleId', () => {
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-1',
      title: '기사 1',
      url: 'https://example.com/1',
    })
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-2',
      title: '기사 2',
      url: 'https://example.com/2',
    })

    useBookmarkStore.getState().removeBookmark('article-1')

    const bookmarks = useBookmarkStore.getState().bookmarks
    expect(bookmarks).toHaveLength(1)
    expect(bookmarks[0].articleId).toBe('article-2')
  })

  it('isBookmarked returns true for bookmarked article', () => {
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-1',
      title: '기사',
      url: 'https://example.com',
    })

    expect(useBookmarkStore.getState().isBookmarked('article-1')).toBe(true)
    expect(useBookmarkStore.getState().isBookmarked('article-2')).toBe(false)
  })

  it('getBookmarks returns all bookmarks', () => {
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-1',
      title: '기사 1',
      url: 'https://example.com/1',
    })
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-2',
      title: '기사 2',
      url: 'https://example.com/2',
    })

    const bookmarks = useBookmarkStore.getState().getBookmarks()
    expect(bookmarks).toHaveLength(2)
  })

  it('clearBookmarks removes all bookmarks', () => {
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-1',
      title: '기사 1',
      url: 'https://example.com/1',
    })
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-2',
      title: '기사 2',
      url: 'https://example.com/2',
    })

    useBookmarkStore.getState().clearBookmarks()

    expect(useBookmarkStore.getState().bookmarks).toEqual([])
  })

  it('handles bookmark without publisher', () => {
    useBookmarkStore.getState().addBookmark({
      articleId: 'article-1',
      title: '기사',
      url: 'https://example.com',
    })

    const bookmark = useBookmarkStore.getState().bookmarks[0]
    expect(bookmark.publisher).toBeUndefined()
  })
})
