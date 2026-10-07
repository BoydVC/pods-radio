// CDP screenshots: node --experimental-websocket tests/shot.mjs <url> <out.png> [W H] [url out W H ...]
import {launch, sleep} from './cdp.mjs';
import {writeFileSync} from 'node:fs';
const a = process.argv.slice(2), jobs = [];
for (let i = 0; i < a.length;) { const j = {url: a[i], out: a[i + 1], w: 1920, h: 1080}; i += 2; if (/^\d+$/.test(a[i] || '')) { j.w = +a[i]; j.h = +a[i + 1]; i += 2; } jobs.push(j); }
const b = await launch();
try {
  for (const j of jobs) {
    await b.send('Emulation.setDeviceMetricsOverride', {width: j.w, height: j.h, deviceScaleFactor: 1, mobile: j.w < 800});
    await b.open(j.url, 1500);
    for (let k = 0; k < 40 && !(await b.ev('!!window.__podsReady || !!document.querySelector(".empty")')); k++) await sleep(250);
    await sleep(2500);
    const full = j.w < 800;
    const opts = {format: 'png'};
    if (full) { const h = await b.ev('document.documentElement.scrollHeight'); await b.send('Emulation.setDeviceMetricsOverride', {width: j.w, height: Math.min(h, 4000), deviceScaleFactor: 1, mobile: true}); await sleep(600); }
    const r = await b.send('Page.captureScreenshot', opts);
    writeFileSync(j.out, Buffer.from(r.result.data, 'base64'));
    console.log(j.out, b.errors.length ? 'errors: ' + b.errors.join(' | ') : 'ok');
  }
} finally { b.close(); }
