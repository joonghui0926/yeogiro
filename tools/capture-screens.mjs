import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
import puppeteer from 'puppeteer-core'

const edge = process.env.BROWSER ?? 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const ROOT = fileURLToPath(new URL('../docs/screens', import.meta.url))
const PHONE = 'http://localhost:5199'
const CONSOLE = 'http://localhost:5174/console'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const clickText = (page, text) =>
  page.evaluate((t) => {
    const el = [...document.querySelectorAll('button')].find((b) => b.innerText.trim() === t)
    el?.click()
    return Boolean(el)
  }, text)

const pressDigit = (page, d) =>
  page.evaluate((digit) => {
    const el = [...document.querySelectorAll('button')].find((b) => b.querySelector('span')?.textContent?.trim() === digit)
    el?.click()
  }, d)

const pinKeys = (page, count) =>
  page.evaluate((n) => {
    const keys = [...document.querySelectorAll('button')].filter((b) => /^\d$/.test(b.innerText.trim()))
    keys.slice(0, n).forEach((k) => k.click())
  }, count)

const phoneShots = [
  ['01-no-tester', async (p) => { await p.goto(`${PHONE}/`, { waitUntil: 'domcontentloaded' }) }],
  ['02-keypad', async (p) => { await p.goto(`${PHONE}/?preview=keypad`) }],
  ['03-keypad-typed', async (p) => {
    await p.goto(`${PHONE}/?preview=keypad`); await sleep(500)
    for (const d of '1666') { await pressDigit(p, d); await sleep(80) }
  }],
  ['04-keypad-menu', async (p) => {
    await p.goto(`${PHONE}/?preview=keypad`); await sleep(500)
    await p.click('button[aria-label="더보기"]')
  }],
  ['05-contacts', async (p) => { await p.goto(`${PHONE}/?preview=contacts`) }],
  ['06-recents', async (p) => { await p.goto(`${PHONE}/?preview=recents`) }],
  ['07-dialing', async (p) => { await p.goto(`${PHONE}/?preview=dialing`) }],
  ['08-in-call', async (p) => { await p.goto(`${PHONE}/?preview=call`) }],
  ['09-in-call-keypad', async (p) => {
    await p.goto(`${PHONE}/?preview=call`); await sleep(500)
    await clickText(p, '키패드\n키패드') || await p.evaluate(() => {
      const el = [...document.querySelectorAll('button')].find((b) => b.innerText.includes('키패드'))
      el?.click()
    })
    await sleep(300)
    for (const d of ['1', '2', '3']) {
      await p.evaluate((x) => [...document.querySelectorAll('button')].find((b) => b.innerText.trim() === x)?.click(), d)
    }
  }],
  ['10-pay-notice', async (p) => { await p.goto(`${PHONE}/?preview=pay-notice`) }],
  ['11-pay-sheet', async (p) => { await p.goto(`${PHONE}/?preview=pay`) }],
  ['12-pay-password', async (p) => {
    await p.goto(`${PHONE}/?preview=pay`); await sleep(500)
    await p.evaluate(() => [...document.querySelectorAll('button')].find((b) => b.innerText.includes('결제하기'))?.click())
    await sleep(400); await pinKeys(p, 3)
  }],
  ['13-pay-done', async (p) => {
    await p.goto(`${PHONE}/?preview=pay`); await sleep(500)
    await p.evaluate(() => [...document.querySelectorAll('button')].find((b) => b.innerText.includes('결제하기'))?.click())
    await sleep(400)
    for (let i = 0; i < 6; i++) { await pinKeys(p, 1); await sleep(60) }
    await sleep(1500)
  }],
  ['14-sms-notice', async (p) => { await p.goto(`${PHONE}/?preview=sms-notice`) }],
  ['15-sms-list', async (p) => { await p.goto(`${PHONE}/?preview=sms-list`) }],
  ['16-sms-thread', async (p) => { await p.goto(`${PHONE}/?preview=sms`) }],
  ['17-call-ended', async (p) => { await p.goto(`${PHONE}/?preview=ended`) }],
]

const consoleShots = [
  ['01-login', `${CONSOLE}/`],
  ['02-overview', `${CONSOLE}/?demo=1`],
  ['03-calls', `${CONSOLE}/calls?demo=1`],
  ['04-call-detail', `${CONSOLE}/calls/d4?demo=1`],
  ['05-live', `${CONSOLE}/live?demo=1`],
  ['06-testers', `${CONSOLE}/testers?demo=1`],
]

const browser = await puppeteer.launch({ executablePath: edge, headless: 'new', args: ['--force-color-profile=srgb'] })
for (const scheme of ['light', 'dark']) {
  fs.mkdirSync(`${ROOT}/phone/${scheme}`, { recursive: true })
  fs.mkdirSync(`${ROOT}/console/${scheme}`, { recursive: true })

  for (const [name, act] of phoneShots) {
    const ctx = await browser.createBrowserContext()
    const p = await ctx.newPage()
    await p.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: scheme }])
    await p.setViewport({ width: 412, height: 892, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
    await act(p)
    await sleep(900)
    await p.screenshot({ path: `${ROOT}/phone/${scheme}/${name}.png` })
    await ctx.close()
  }

  for (const [name, url] of consoleShots) {
    for (const [device, vp] of [['desktop', { width: 1366, height: 900, deviceScaleFactor: 1.5 }], ['mobile', { width: 412, height: 892, deviceScaleFactor: 2, isMobile: true, hasTouch: true }]]) {
      const ctx = await browser.createBrowserContext()
      const p = await ctx.newPage()
      await p.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: scheme }])
      await p.setViewport(vp)
      await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 })
      await sleep(1600)
      await p.screenshot({ path: `${ROOT}/console/${scheme}/${name}-${device}.png`, fullPage: device === 'desktop' && name !== '04-call-detail' })
      await ctx.close()
    }
  }
}
await browser.close()
console.log('done')
