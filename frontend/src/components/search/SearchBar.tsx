import { useState, useCallback, useEffect, useRef, useMemo, type FormEvent } from 'react'
import { Search, Link as LinkIcon, Clock, X, Command } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useTrackingStore } from '@/stores/useTrackingStore'

const STORAGE_KEY = 'news-origin:recent-searches'
const MAX_RECENT = 5

function getRecentSearches(): string[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

function addRecentSearch(query: string) {
  const recent = getRecentSearches().filter((q) => q !== query)
  recent.unshift(query)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)))
}

function removeRecentSearch(query: string) {
  const recent = getRecentSearches().filter((q) => q !== query)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(recent))
}

function clearRecentSearches() {
  localStorage.removeItem(STORAGE_KEY)
}

export default function SearchBar() {
  const { searchQuery, setSearchQuery, submitSearch, isSearching } = useTrackingStore()
  const [focused, setFocused] = useState(false)
  const [recentSearches, setRecentSearches] = useState<string[]>(getRecentSearches)
  const inputRef = useRef<HTMLInputElement>(null)

  // Ctrl+K / Cmd+K to focus search, Escape to clear
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
      if (e.key === 'Escape' && document.activeElement === inputRef.current) {
        setSearchQuery('')
        inputRef.current?.blur()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [setSearchQuery])

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault()
      if (!searchQuery.trim()) return
      addRecentSearch(searchQuery.trim())
      setRecentSearches(getRecentSearches())
      submitSearch()
    },
    [searchQuery, submitSearch],
  )

  const handleRecentClick = useCallback(
    (query: string) => {
      setSearchQuery(query)
      addRecentSearch(query)
      setRecentSearches(getRecentSearches())
      // Defer submit to next tick so store updates
      setTimeout(() => {
        useTrackingStore.getState().submitSearch()
      }, 0)
    },
    [setSearchQuery],
  )

  const handleRemoveRecent = useCallback((query: string) => {
    removeRecentSearch(query)
    setRecentSearches(getRecentSearches())
  }, [])

  const handleClearRecent = useCallback(() => {
    clearRecentSearches()
    setRecentSearches([])
  }, [])

  // Animated dots: 검색중. → 검색중.. → 검색중...
  const [dotCount, setDotCount] = useState(1)
  useEffect(() => {
    if (!isSearching) { setDotCount(1); return }
    const id = setInterval(() => setDotCount((c) => (c % 3) + 1), 500)
    return () => clearInterval(id)
  }, [isSearching])
  const searchingText = useMemo(() => `검색중${'.'.repeat(dotCount)}`, [dotCount])

  const isUrl = searchQuery.startsWith('http://') || searchQuery.startsWith('https://')

  return (
    <div className="w-full max-w-2xl">
      <form onSubmit={handleSubmit}>
        <div
          className={`flex items-center gap-2 rounded-xl border bg-gray-100/50 px-4 py-3 transition-all dark:bg-gray-900/50 ${
            focused
              ? 'border-lifecycle-origin shadow-lg shadow-lifecycle-origin/10'
              : 'border-border'
          }`}
        >
          {isUrl ? (
            <LinkIcon className="h-5 w-5 shrink-0 text-lifecycle-origin" />
          ) : (
            <Search className="h-5 w-5 shrink-0 text-muted-foreground" />
          )}
          <input
            ref={inputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setTimeout(() => setFocused(false), 150)}
            placeholder="뉴스 URL 또는 기사 제목 입력..."
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            disabled={isSearching}
            aria-label="뉴스 기사 검색"
            autoComplete="off"
          />
          {!focused && !searchQuery && (
            <kbd className="hidden items-center gap-0.5 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground sm:flex">
              <Command className="h-2.5 w-2.5" />K
            </kbd>
          )}
          <Button type="submit" size="sm" disabled={isSearching || !searchQuery.trim()}>
            {isSearching ? searchingText : '추적'}
          </Button>
        </div>
        <p className={`mt-2 text-center text-[11px] text-muted-foreground transition-all duration-300 sm:text-xs ${
          focused || searchQuery ? 'max-h-6 opacity-100' : 'max-h-0 overflow-hidden opacity-0'
        }`}>
          URL → 기원점 추적 · 제목 → 관련 기사 검색
        </p>
      </form>

      {/* Recent searches - only visible on focus */}
      {recentSearches.length > 0 && !searchQuery && focused && (
        <div className="mt-3 rounded-lg border border-border bg-gray-100/30 p-3 animate-in fade-in slide-in-from-top-1 duration-200 dark:bg-gray-900/30">
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Clock className="h-3 w-3" />
              최근 검색
            </span>
            <button
              onClick={handleClearRecent}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
              삭제
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {recentSearches.map((query) => (
              <span
                key={query}
                className="group flex items-center gap-1 rounded-md bg-secondary/50 py-1 pl-2.5 pr-1 text-xs text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                <button onClick={() => handleRecentClick(query)} className="truncate">
                  {query.length > 40 ? query.slice(0, 40) + '...' : query}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleRemoveRecent(query)
                  }}
                  className="ml-0.5 rounded p-0.5 opacity-0 transition-opacity hover:bg-destructive/20 hover:text-destructive group-hover:opacity-100"
                  aria-label={`'${query}' 삭제`}
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
