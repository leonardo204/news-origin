import { test, expect } from '@playwright/test'

const ADMIN_URL = 'http://localhost:10880'

async function login(page: import('@playwright/test').Page) {
  const username = process.env.ADMIN_USERNAME || 'admin'
  const password = process.env.ADMIN_PASSWORD || 'admin'

  // Navigate to admin to set origin, then authenticate via API directly
  await page.goto(`${ADMIN_URL}/admin/login`)

  // Call login API and store token directly (bypasses UI race conditions)
  const token = await page.evaluate(
    async ({ url, user, pass }) => {
      const res = await fetch(`${url}/api/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: user, password: pass }),
      })
      const data = await res.json()
      const t = data.token
      localStorage.setItem('admin_token', t)
      return t
    },
    { url: ADMIN_URL, user: username, pass: password }
  )

  if (!token) throw new Error('Login failed: no token received')
}

test.describe('Admin Dashboard - Collection Page', () => {
  test('shows feed sources cards', async ({ page }) => {
    await login(page)
    await page.goto(`${ADMIN_URL}/admin/collection`)
    await page.waitForLoadState('networkidle')

    // Verify category feeds card exists
    await expect(page.locator('text=카테고리 피드')).toBeVisible({ timeout: 10000 })

    // Verify publisher feeds card exists
    await expect(page.locator('text=언론사 피드')).toBeVisible()

    // Verify specific category feeds are shown
    await expect(page.locator('text=헤드라인').first()).toBeVisible()
    await expect(page.locator('text=정치').first()).toBeVisible()
    await expect(page.locator('text=경제').first()).toBeVisible()

    // Verify specific publisher feeds are shown
    await expect(page.locator('text=조선일보').first()).toBeVisible()
    await expect(page.locator('text=한겨레').first()).toBeVisible()

    // Verify feed limits are shown
    await expect(page.locator('text=피드당 최대 15건')).toBeVisible()
    await expect(page.locator('text=피드당 최대 10건')).toBeVisible()
  })
})

test.describe('Admin Dashboard - MLOps Page', () => {
  test('shows pipeline visualization', async ({ page }) => {
    await login(page)
    await page.goto(`${ADMIN_URL}/admin/mlops`)
    await page.waitForLoadState('networkidle')

    // Verify pipeline card exists
    await expect(page.locator('text=MLOps 파이프라인')).toBeVisible({ timeout: 10000 })

    // Verify all 6 pipeline stages are shown
    await expect(page.locator('text=데이터 수집').first()).toBeVisible()
    await expect(page.locator('text=품질 평가').first()).toBeVisible()
    await expect(page.locator('text=학습 준비').first()).toBeVisible()
    await expect(page.locator('text=Fine-tuning').first()).toBeVisible()
    await expect(page.locator('text=모델 배포').first()).toBeVisible()
    await expect(page.locator('text=키워드 재추출').first()).toBeVisible()

    // Verify progress summary bar
    await expect(page.locator('text=학습 데이터 진행률')).toBeVisible()
    await expect(page.locator('text=/\\d+ \\/ \\d+건/')).toBeVisible()
  })

  test('shows predictions banner', async ({ page }) => {
    await login(page)
    await page.goto(`${ADMIN_URL}/admin/mlops`)
    await page.waitForLoadState('networkidle')

    // Verify predictions banner exists
    await expect(page.locator('text=현재 상태')).toBeVisible({ timeout: 20000 })
    await expect(page.locator('text=일일 수집률')).toBeVisible()

    // Verify current phase badge
    await expect(page.locator('text=데이터 수집 중').first()).toBeVisible()
  })

  test('shows schedule table with KST times', async ({ page }) => {
    await login(page)
    await page.goto(`${ADMIN_URL}/admin/mlops`)
    await page.waitForLoadState('networkidle')

    // Verify schedule card exists (scroll into view if needed)
    const scheduleCard = page.locator('text=MLOps 스케줄')
    await scheduleCard.scrollIntoViewIfNeeded()
    await expect(scheduleCard).toBeVisible({ timeout: 10000 })

    // Verify updated schedule items
    await expect(page.locator('text=뉴스 수집 + 인라인 평가')).toBeVisible()
    await expect(page.locator('text=데이터 수집 (GPT-5 평가)')).toBeVisible()
    await expect(page.locator('text=6시간마다')).toBeVisible()
    await expect(page.locator('text=학습 준비 확인')).toBeVisible()
    await expect(page.locator('text=매일 11:00 KST')).toBeVisible()
    await expect(page.locator('text=자동 (준비 완료 시)').first()).toBeVisible()

    // Verify KST next-run column header
    await expect(page.locator('text=다음 실행 (KST)')).toBeVisible()

    // Verify KST time badges are shown (format: MM/DD HH:MM KST)
    await expect(page.locator('text=/\\d{2}\\/\\d{2} \\d{2}:\\d{2} KST/').first()).toBeVisible()
  })
})
