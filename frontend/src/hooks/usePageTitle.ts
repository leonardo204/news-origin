import { useEffect } from 'react'

const BASE_TITLE = 'News Origin'
const BASE_DESCRIPTION = '뉴스 기사의 최초 출처를 추적하고 전파 과정을 시각화하는 서비스'

export function usePageTitle(title?: string, description?: string) {
  useEffect(() => {
    // Update title
    document.title = title ? `${title} - ${BASE_TITLE}` : `${BASE_TITLE} - 뉴스 기원 추적`

    // Update meta description
    const metaDescription = document.querySelector('meta[name="description"]')
    if (metaDescription) {
      metaDescription.setAttribute('content', description || BASE_DESCRIPTION)
    }

    // Update Open Graph description
    const ogDescription = document.querySelector('meta[property="og:description"]')
    if (ogDescription) {
      ogDescription.setAttribute('content', description || BASE_DESCRIPTION)
    }

    // Update Twitter description
    const twitterDescription = document.querySelector('meta[name="twitter:description"]')
    if (twitterDescription) {
      twitterDescription.setAttribute('content', description || BASE_DESCRIPTION)
    }

    return () => {
      document.title = `${BASE_TITLE} - 뉴스 기원 추적`
      if (metaDescription) {
        metaDescription.setAttribute('content', BASE_DESCRIPTION)
      }
      if (ogDescription) {
        ogDescription.setAttribute('content', BASE_DESCRIPTION)
      }
      if (twitterDescription) {
        twitterDescription.setAttribute('content', BASE_DESCRIPTION)
      }
    }
  }, [title, description])
}
