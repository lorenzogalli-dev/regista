// Screenshots and short videos of the web app through headless Chrome and the DevTools
// protocol (no dependencies: Node's built-in WebSocket). Runs in real time, so animations
// look exactly as in a browser.
//
//   node scripts/capture.mjs shot  <url> <out.png> [width] [height] [waitMs]
//   node scripts/capture.mjs video <url> <out.mp4> [seconds] [width] [height]   (needs ffmpeg;
//                                                         SCROLL=1 scrolls to the bottom)
//   node scripts/capture.mjs audit <url>          design audit of a /broadcast URL (exit 1 on problems)
//
// CHROME overrides the browser path (default: Google Chrome on macOS). TRANSPARENT=1 captures
// with a transparent page background (for /graphics).

import { spawn, spawnSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const CHROME = process.env.CHROME ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function launch(width, height) {
  const profile = mkdtempSync(join(tmpdir(), 'gtf-chrome-'))
  const proc = spawn(CHROME, [
    '--headless=new',
    '--hide-scrollbars',
    '--remote-debugging-port=0',
    `--user-data-dir=${profile}`,
    `--window-size=${width},${height}`,
    '--force-device-scale-factor=1',
    'about:blank',
  ])
  const wsUrl = await new Promise((resolve, reject) => {
    let buf = ''
    proc.stderr.on('data', (d) => {
      buf += d
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/)
      if (m) resolve(m[1])
    })
    proc.on('exit', () => reject(new Error('chrome exited')))
  })
  const port = new URL(wsUrl).port
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()
  const page = targets.find((t) => t.type === 'page')
  const ws = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((r) => ws.addEventListener('open', r, { once: true }))
  let id = 0
  const pending = new Map()
  const listeners = new Map()
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data)
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id)
      pending.delete(msg.id)
      if (msg.error) reject(new Error(msg.error.message))
      else resolve(msg.result)
    } else if (msg.method) listeners.get(msg.method)?.(msg.params)
  })
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      pending.set(++id, { resolve, reject })
      ws.send(JSON.stringify({ id, method, params }))
    })
  await send('Page.enable')
  if (process.env.TRANSPARENT === '1') {
    await send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } })
  }
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 })
  const close = async () => {
    ws.close()
    const exited = new Promise((r) => proc.once('exit', r))
    proc.kill()
    await exited
    try {
      rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
    } catch {
      // Chrome helpers may still be writing their profile; a stale temp dir is harmless.
    }
  }
  return { send, on: (m, fn) => listeners.set(m, fn), close }
}

async function open(cdp, url) {
  const loaded = new Promise((r) => cdp.on('Page.loadEventFired', r))
  await cdp.send('Page.navigate', { url })
  await loaded
  await cdp.send('Runtime.evaluate', { expression: 'document.fonts.ready', awaitPromise: true })
}

async function shot(url, out, width = 1920, height = 1080, waitMs = 2500) {
  const cdp = await launch(Number(width), Number(height))
  try {
    await open(cdp, url)
    await sleep(Number(waitMs))
    const full = Number(width) < 600 // phone width: capture the whole page
    let clip
    if (full) {
      const { contentSize } = await cdp.send('Page.getLayoutMetrics')
      clip = { x: 0, y: 0, width: Number(width), height: Math.ceil(contentSize.height), scale: 1 }
    }
    const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: full, clip })
    writeFileSync(out, Buffer.from(data, 'base64'))
  } finally {
    await cdp.close()
  }
}

async function video(url, out, seconds = 15, width = 1920, height = 1080) {
  const dir = mkdtempSync(join(tmpdir(), 'gtf-frames-'))
  const cdp = await launch(Number(width), Number(height))
  const frames = []
  let stoppedAt = 0
  let openedAt = 0
  try {
    cdp.on('Page.screencastFrame', async (p) => {
      const file = join(dir, `f${String(frames.length).padStart(5, '0')}.jpg`)
      writeFileSync(file, Buffer.from(p.data, 'base64'))
      frames.push({ file, t: p.metadata.timestamp })
      await cdp.send('Page.screencastFrameAck', { sessionId: p.sessionId })
    })
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, everyNthFrame: 1 })
    await open(cdp, url)
    await sleep(Number(process.env.SETTLE_MS ?? 1200)) // first paint, fonts, first data
    openedAt = Date.now() / 1000
    if (process.env.SCROLL === '1') {
      // Scroll the page smoothly to the bottom over the recording (long pages).
      await sleep(1500)
      const ms = Number(seconds) * 1000 - 3000
      await cdp.send('Runtime.evaluate', {
        expression: `(() => { const end = document.documentElement.scrollHeight - innerHeight;
          const t0 = performance.now(); const step = (t) => { const k = Math.min(1, (t - t0) / ${ms});
          scrollTo(0, end * (0.5 - Math.cos(Math.PI * k) / 2)); if (k < 1) requestAnimationFrame(step) };
          requestAnimationFrame(step) })()`,
      })
      await sleep(ms + 1500)
    } else {
      await sleep(Number(seconds) * 1000)
    }
    stoppedAt = Date.now() / 1000
    await cdp.send('Page.stopScreencast')
  } finally {
    await cdp.close()
  }
  // Variable frame timing from Chrome → constant 30 fps via ffmpeg's concat demuxer. Chrome
  // only sends a frame when the page changes, so the last one lasts until the stop; the concat
  // demuxer ignores the last entry's duration unless the file is listed once more.
  // Drop the page load: start from the last frame painted before `openedAt`.
  const after = frames.findIndex((f) => f.t >= openedAt)
  frames.splice(0, after === -1 ? frames.length - 1 : Math.max(0, after - 1))
  if (frames.length) frames[0].t = Math.max(frames[0].t, openedAt)
  const lines = frames.flatMap((f, i) => {
    const next = frames[i + 1]?.t ?? Math.max(f.t + 1 / 30, stoppedAt)
    return [`file '${f.file}'`, `duration ${(next - f.t).toFixed(4)}`]
  })
  if (frames.length) lines.push(`file '${frames[frames.length - 1].file}'`)
  writeFileSync(join(dir, 'list.txt'), lines.join('\n') + '\n')
  const r = spawnSync(
    'ffmpeg',
    [
      '-y',
      '-loglevel',
      'error',
      '-f',
      'concat',
      '-safe',
      '0',
      '-i',
      join(dir, 'list.txt'),
      '-t',
      String(seconds),
      '-vf',
      `fps=30,scale=${width}:${height}`,
      '-c:v',
      'libx264',
      '-pix_fmt',
      'yuv420p',
      '-crf',
      '20',
      out,
    ],
    { stdio: 'inherit' },
  )
  rmSync(dir, { recursive: true, force: true })
  console.log(`${frames.length} frames captured over ${seconds} s → ${out}`)
  process.exitCode = r.status ?? 1
}

async function audit(url) {
  const cdp = await launch(1920, 1080)
  try {
    await open(cdp, url + (url.includes('?') ? '&' : '?') + 'audit=1')
    await sleep(4500)
    const { result } = await cdp.send('Runtime.evaluate', {
      expression: "document.getElementById('audit')?.textContent ?? 'null'",
    })
    const report = JSON.parse(result.value)
    if (!report) throw new Error('no audit report')
    console.log(`${url}: ${Object.keys(report.graphics).length} graphics, ${report.textChecked} text elements`)
    for (const p of report.problems) console.log(`  PROBLEM ${p}`)
    process.exitCode = report.problems.length ? 1 : 0
  } finally {
    await cdp.close()
  }
}

const [cmd, ...args] = process.argv.slice(2)
if (cmd === 'shot') await shot(...args)
else if (cmd === 'audit') await audit(...args)
else if (cmd === 'video') await video(...args)
else {
  console.error('usage: capture.mjs shot|video <url> <out> ...')
  process.exitCode = 2
}
