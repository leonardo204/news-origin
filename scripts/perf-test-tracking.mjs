/**
 * Playwright Performance Test - Instant Tracking Response Time
 *
 * Measures the time from clicking "대표기사 추적하기" on the Trends page
 * to receiving the completed tracking result (timeline page displayed).
 *
 * Target: < 3 seconds for instant tracking (DB/Qdrant lookup only)
 *
 * Usage: npx playwright test scripts/perf-test-tracking.mjs
 *   or:  node scripts/perf-test-tracking.mjs
 */

import { chromium } from 'playwright'

const BASE_URL = 'http://localhost:10880'
const TIMEOUT = 30000
const TARGET_MS = 3000

async function runTest() {
  console.log('=== Instant Tracking Performance Test ===\n')

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  })
  const page = await context.newPage()

  // Ignore Cloudflare Insights errors (ad blocker)
  page.on('pageerror', () => {})
  page.on('requestfailed', (req) => {
    if (req.url().includes('cloudflareinsights')) return
  })

  const results = []

  try {
    // 1. Navigate to Trends page
    console.log('1. Navigating to Trends page...')
    await page.goto(`${BASE_URL}/trends`, { waitUntil: 'networkidle', timeout: TIMEOUT })
    await page.waitForTimeout(2000) // Wait for data to load

    // 2. Find a clickable trend cluster
    console.log('2. Looking for trend clusters...')

    // Look for trend cards/items that are clickable
    const trendItems = await page.$$('[data-testid="trend-item"], .cursor-pointer, [role="button"]')
    console.log(`   Found ${trendItems.length} clickable elements`)

    // Try to find a trend cluster with articles
    let trendClicked = false

    // Strategy 1: Look for trend items in the main content area
    const trendCards = await page.$$('div.cursor-pointer')
    if (trendCards.length > 0) {
      console.log(`   Found ${trendCards.length} trend cards, clicking first one...`)
      await trendCards[0].click()
      trendClicked = true
    }

    if (!trendClicked) {
      // Strategy 2: Click any card-like element in the trends list
      const cards = await page.$$('.rounded-lg.border, .bg-card, [class*="trend"]')
      if (cards.length > 0) {
        console.log(`   Trying card elements (${cards.length} found)...`)
        await cards[0].click()
        trendClicked = true
      }
    }

    if (!trendClicked) {
      console.log('   No trend clusters found. Checking if page loaded correctly...')
      const pageText = await page.textContent('body')
      console.log(`   Page contains: ${pageText.substring(0, 200)}...`)
      throw new Error('No trend clusters found to click')
    }

    await page.waitForTimeout(1000)

    // 3. Find and click "대표기사 추적하기" button
    console.log('3. Looking for tracking button...')

    let trackButton = await page.$('button:has-text("추적")')
    if (!trackButton) {
      trackButton = await page.$('button:has-text("분석")')
    }
    if (!trackButton) {
      trackButton = await page.$('a:has-text("추적")')
    }
    if (!trackButton) {
      // Look in the detail panel
      const buttons = await page.$$('button')
      for (const btn of buttons) {
        const text = await btn.textContent()
        if (text && (text.includes('추적') || text.includes('분석') || text.includes('Track'))) {
          trackButton = btn
          break
        }
      }
    }

    if (!trackButton) {
      console.log('   No tracking button found. Taking screenshot for debug...')
      await page.screenshot({ path: 'perf-test-debug.png' })
      throw new Error('Tracking button not found')
    }

    // 4. Measure tracking response time
    console.log('4. Clicking tracking button and measuring response time...')

    const startTime = Date.now()

    // Listen for the confirm API call and its response
    const confirmPromise = page.waitForResponse(
      (resp) => resp.url().includes('/api/articles/confirm') && resp.status() === 200,
      { timeout: TIMEOUT }
    )

    await trackButton.click()

    // Wait for confirm API response
    const confirmResponse = await confirmPromise
    const confirmTime = Date.now() - startTime
    const confirmData = await confirmResponse.json()

    console.log(`   Confirm API response: ${confirmTime}ms`)
    console.log(`   Status: ${confirmData.status}`)
    console.log(`   Tracking type: ${confirmData.tracking_type}`)
    console.log(`   Message: ${confirmData.message}`)

    results.push({ name: 'Confirm API Response', timeMs: confirmTime })

    // 5. If completed synchronously, measure time to timeline display
    if (confirmData.status === 'completed') {
      console.log('\n   >> SYNC PATH: Tracking completed synchronously!')

      // Wait for timeline API call
      try {
        const timelinePromise = page.waitForResponse(
          (resp) => resp.url().includes('/api/timeline/') && !resp.url().includes('/status') && resp.status() === 200,
          { timeout: 10000 }
        )
        const timelineResponse = await timelinePromise
        const timelineTime = Date.now() - startTime
        console.log(`   Timeline API response: ${timelineTime}ms`)
        results.push({ name: 'Timeline API Response', timeMs: timelineTime })
      } catch {
        console.log('   Timeline API not called within 10s (may already be cached)')
      }

      // Wait for page navigation to timeline
      try {
        await page.waitForURL('**/timeline/**', { timeout: 10000 })
        const navTime = Date.now() - startTime
        console.log(`   Page navigation to timeline: ${navTime}ms`)
        results.push({ name: 'Page Navigation', timeMs: navTime })
      } catch {
        console.log('   No page navigation detected (may render in-place)')
      }

      const totalTime = Date.now() - startTime
      results.push({ name: 'Total End-to-End', timeMs: totalTime })
    } else {
      console.log('\n   >> ASYNC PATH: Tracking dispatched to Celery, polling...')

      // Wait for completion via polling
      try {
        await page.waitForURL('**/timeline/**', { timeout: 30000 })
        const totalTime = Date.now() - startTime
        console.log(`   Total time (with polling): ${totalTime}ms`)
        results.push({ name: 'Total End-to-End (async)', timeMs: totalTime })
      } catch {
        const totalTime = Date.now() - startTime
        console.log(`   Timed out waiting for navigation after ${totalTime}ms`)
        results.push({ name: 'Timeout', timeMs: totalTime })
      }
    }

  } catch (err) {
    console.error(`\nError: ${err.message}`)
  } finally {
    await browser.close()
  }

  // Print results summary
  console.log('\n=== Performance Results ===')
  console.log('─'.repeat(50))
  for (const r of results) {
    const status = r.timeMs <= TARGET_MS ? 'PASS' : 'SLOW'
    const icon = status === 'PASS' ? '[OK]' : '[!!]'
    console.log(`${icon} ${r.name}: ${r.timeMs}ms ${r.timeMs > TARGET_MS ? `(target: <${TARGET_MS}ms)` : ''}`)
  }
  console.log('─'.repeat(50))

  const mainResult = results.find(r => r.name.startsWith('Total') || r.name === 'Confirm API Response')
  if (mainResult) {
    if (mainResult.timeMs <= TARGET_MS) {
      console.log(`\nRESULT: PASS - Response time ${mainResult.timeMs}ms is within ${TARGET_MS}ms target`)
    } else {
      console.log(`\nRESULT: NEEDS IMPROVEMENT - Response time ${mainResult.timeMs}ms exceeds ${TARGET_MS}ms target`)
    }
  }

  return results
}

runTest().catch(console.error)
