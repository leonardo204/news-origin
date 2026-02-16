import { Bookmark, BookmarkCheck } from 'lucide-react'
import { useBookmarkStore } from '@/stores/useBookmarkStore'
import { cn } from '@/lib/utils'

interface BookmarkButtonProps {
  articleId: string
  title: string
  publisher?: string
  url: string
  className?: string
  size?: 'sm' | 'md'
}

export default function BookmarkButton({
  articleId,
  title,
  publisher,
  url,
  className,
  size = 'md',
}: BookmarkButtonProps) {
  const { isBookmarked, addBookmark, removeBookmark } = useBookmarkStore()
  const bookmarked = isBookmarked(articleId)

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    if (bookmarked) {
      removeBookmark(articleId)
    } else {
      addBookmark({
        articleId,
        title,
        publisher,
        url,
      })
    }
  }

  const iconSize = size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4'

  return (
    <button
      onClick={handleClick}
      className={cn(
        'rounded-md p-1.5 transition-colors hover:bg-secondary',
        bookmarked ? 'text-yellow-500 hover:text-yellow-600' : 'text-muted-foreground hover:text-foreground',
        className,
      )}
      aria-label={bookmarked ? '북마크 제거' : '북마크 추가'}
      title={bookmarked ? '북마크 제거' : '북마크 추가'}
    >
      {bookmarked ? (
        <BookmarkCheck className={iconSize} />
      ) : (
        <Bookmark className={iconSize} />
      )}
    </button>
  )
}
