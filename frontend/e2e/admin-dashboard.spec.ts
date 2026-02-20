import { test, expect } from '@playwright/test'

const ADMIN_URL = 'http://localhost:10880'

async function login(page: import('@playwright/test').Page) {
  await page.goto(`${ADMIN_URL}/admin/login`)
  await page.waitForLoadState('networkidle')

  const username = process.env.ADMIN_USERNAME || 'admin'
  const password = process.env.ADMIN_PASSWORD || 'admin'

  // Use role-based locators to trigger React onChange
  const usernameInput = page.getByRole('textbox', { name: '사용자 이름' })
  const passwordInput = page.getByRole('textbox', { name: '비밀번호' })

  await usernameInput.fill(username)
  await passwordInput.fill(password)

  // Wait for button to become enabled
  const loginBtn = page.getByRole('button', { name: '로그인' })
  await expect(loginBtn).toBeEnabled({ timeout: 3000 })
  await loginBtn.click()

  // Wait for navigation away from login
  await page.waitForURL('**/admin', { timeout: 10000 })
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

  test('shows schedule table', async ({ page }) => {
    await login(page)
    await page.goto(`${ADMIN_URL}/admin/mlops`)
    await page.waitForLoadState('networkidle')

    // Verify schedule card exists (scroll into view if needed)
    const scheduleCard = page.locator('text=MLOps 스케줄')
    await scheduleCard.scrollIntoViewIfNeeded()
    await expect(scheduleCard).toBeVisible({ timeout: 10000 })

    // Verify schedule items
    await expect(page.locator('text=데이터 수집 (GPT-5 평가)')).toBeVisible()
    await expect(page.locator('text=6시간마다')).toBeVisible()
    await expect(page.locator('text=학습 준비 확인')).toBeVisible()
    await expect(page.locator('text=매일 02:00 UTC')).toBeVisible()
    await expect(page.locator('text=수동 실행').first()).toBeVisible()
  })
})
