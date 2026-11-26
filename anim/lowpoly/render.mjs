// node render.mjs <workdir> snap <t1,t2,...> | all   -> PNG frames of the low-poly scene (360x640) via headless Chrome.
// <workdir> holds spec.json; frames go to <workdir>/frames, snaps to <workdir>/snaps.
import { chromium } from 'playwright-core';
import fs from 'fs'; import http from 'http'; import path from 'path';
const dir = path.dirname(new URL(import.meta.url).pathname);
const work = path.resolve(process.argv[2]);
const CHROME = process.env.CHROME || ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].find((p) => fs.existsSync(p));
const mime = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json' };
const srv = http.createServer((q, r) => { const u = decodeURIComponent(q.url.split('?')[0]); const f = u === '/spec.json' ? path.join(work, 'spec.json') : path.join(dir, u); fs.readFile(f, (e, b) => { if (e) { r.writeHead(404); r.end(); } else { r.writeHead(200, { 'content-type': mime[path.extname(f)] || 'application/octet-stream' }); r.end(b); } }); }).listen(0);
const port = srv.address().port;
const browser = await chromium.launch({ executablePath: CHROME, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 400, height: 700 } });
page.on('console', (m) => { if (m.type() === 'error') console.log('ERR', m.text()); }); page.on('pageerror', (e) => console.log('PAGEERR', e.message));
await page.goto(`http://localhost:${port}/index.html`); await page.waitForFunction('window.ready === true', null, { timeout: 30000 });
const spec = JSON.parse(fs.readFileSync(path.join(work, 'spec.json')));
const shot = async (t, out) => { const url = await page.evaluate((t) => { window.renderAt(t); return document.getElementById('c').toDataURL('image/png'); }, t); fs.writeFileSync(out, Buffer.from(url.split(',')[1], 'base64')); };
const mode = process.argv[3];
if (mode === 'snap') { fs.mkdirSync(path.join(work, 'snaps'), { recursive: true }); for (const t of process.argv[4].split(',').map(Number)) await shot(t, path.join(work, 'snaps', `s_${t.toFixed(2).padStart(6, '0')}.png`)); }
else { const od = path.join(work, 'frames'); fs.rmSync(od, { recursive: true, force: true }); fs.mkdirSync(od); const n = Math.round(spec.total * spec.fps); const t0 = Date.now();
  for (let i = 0; i < n; i++) await shot(i / spec.fps, path.join(od, `f_${String(i).padStart(5, '0')}.png`)); console.log('frames', n, 'secs', (Date.now() - t0) / 1000); }
await browser.close(); srv.close();
