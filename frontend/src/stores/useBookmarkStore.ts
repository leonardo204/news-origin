import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Bookmark {
  articleId: string
  title: string
  publisher?: string
  url: string
  bookmarkedAt: string
}

interface BookmarkState {
  bookmarks: Bookmark[]
  addBookmark: (bookmark: Omit<Bookmark, 'bookmarkedAt'>) => void
  removeBookmark: (articleId: string) => void
  isBookmarked: (articleId: string) => boolean
  getBookmarks: () => Bookmark[]
  clearBookmarks: () => void
}

export const useBookmarkStore = create<BookmarkState>()(
  persist(
    (set, get) => ({
      bookmarks: [],

      addBookmark: (bookmark) => {
        const { bookmarks } = get()
        // 중복 방지
        if (bookmarks.some((b) => b.articleId === bookmark.articleId)) {
          return
        }
        set({
          bookmarks: [
            {
              ...bookmark,
              bookmarkedAt: new Date().toISOString(),
            },
            ...bookmarks,
          ],
        })
      },

      removeBookmark: (articleId) => {
        set({
          bookmarks: get().bookmarks.filter((b) => b.articleId !== articleId),
        })
      },

      isBookmarked: (articleId) => {
        return get().bookmarks.some((b) => b.articleId === articleId)
      },

      getBookmarks: () => {
        return get().bookmarks
      },

      clearBookmarks: () => {
        set({ bookmarks: [] })
      },
    }),
    {
      name: 'news-origin:bookmarks',
    },
  ),
)
