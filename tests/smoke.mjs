// Pods Radio smoke test (headless Chrome over CDP). Run: node --experimental-websocket tests/smoke.mjs
import {launch, sleep} from './cdp.mjs';
import {readFileSync, existsSync} from 'node:fs';
const BASE = 'http://127.0.0.1:4849';
const ROOT = new URL('..', import.meta.url).pathname;
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('  ✓', m); } else { fail++; console.log('  ✗', m); } };

const health = await (await fetch(BASE + '/api/health')).json();
ok(health.ok && health.episodes >= 1, `server healthy, ${health.episodes} episodes`);
const idx = await (await fetch(BASE + '/api/index')).json();
const latest = idx.episodes[0];
const ep = await (await fetch(`${BASE}/api/episode/${latest.date}`)).json();
const r = await fetch(`${BASE}/episodes/${latest.date}/${latest.audio}`, {headers: {Range: 'bytes=1000-1999'}});
ok(r.status === 206 && (await r.arrayBuffer()).byteLength === 1000, 'audio supports HTTP Range (206, exact bytes)');
ok((await fetch(BASE + '/api/episode/1999-01-01')).status === 404, 'unknown episode → 404');
ok((await fetch(BASE + '/../server.py')).status === 404, 'no path traversal');
const feed = await (await fetch(BASE + '/feed.xml')).text();
ok((feed.match(/<enclosure /g) || []).length === idx.episodes.length, 'local podcast feed lists every episode');
ok(idx.episodes.every((e) => e.duration >= 300 && e.duration <= 480), 'every episode is 5–8 minutes');

const b = await launch();
try {
  await b.open(BASE + '/', 3500);
  ok(await b.ev('window.__podsReady === true'), 'player boots');
  ok(b.errors.length === 0, 'no console errors' + (b.errors.length ? ': ' + b.errors.join(' | ') : ''));
  ok((await b.ev('document.querySelector("#hero h1").textContent')).length > 5, 'hero shows the episode day');
  ok(await b.ev(`document.querySelectorAll("#chapters .ch").length === ${ep.chapters.length}`), `${ep.chapters.length} chapter buttons`);
  ok(await b.ev(`(() => { const c = document.querySelector("#wave"); const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n > 5000; })()`), 'waveform drawn');
  ok(await b.ev(`document.querySelectorAll("#tabBody .item").length === ${ep.notes.length}`), `show notes list all ${ep.notes.length} items`);
  ok(await b.ev(`[...document.querySelectorAll("#tabBody .item h4 a")].every((a) => /^https:\\/\\/(www\\.youtube\\.com|.+)/.test(a.href))`), 'every show note links out');
  await sleep(1500);
  ok(await b.ev(`document.querySelectorAll("#eps .ep").length === ${idx.episodes.length}`), `archive shows ${idx.episodes.length} episodes`);
  // seek to a referenced caption → caption + live note
  const cap = ep.captions.find((c) => c.refs.length && ep.notes.some((n) => n.id === c.refs[0]) && c.seg !== 'open');
  if (cap) {
    await b.ev(`window.__pods.seek(${cap.t + 0.2})`); await sleep(300);
    ok((await b.ev('document.querySelector("#caption .cur").textContent')).includes(cap.text.slice(0, 30)), 'caption follows the playhead');
    ok(await b.ev(`document.querySelector(".item.live")?.dataset.id === ${JSON.stringify(cap.refs[0])}`), 'show note lights up for the item being read');
    ok(await b.ev(`document.querySelector("#chapters .ch.on .t").title === ${JSON.stringify(ep.chapters.filter((c) => c.start <= cap.t + .2).pop().title)}`), 'current chapter highlighted');
  }
  await b.ev('window.__pods.seek(0)');
  await b.ev('document.querySelector("#bPlay").click()'); await sleep(2000);
  const ct = await b.ev('window.__pods.audio.currentTime');
  ok(ct > 0.5 && await b.ev('document.body.classList.contains("playing")'), `audio plays (t=${ct.toFixed(2)}s, ON AIR lit)`);
  await b.ev('document.querySelector("#bPlay").click()');
  await b.ev('document.dispatchEvent(new KeyboardEvent("keydown", {key: "]", bubbles: true}))'); await sleep(200);
  ok(await b.ev(`window.__pods.audio.currentTime >= ${ep.chapters[1].start - .1}`), '] jumps to the next chapter');
  await b.ev('document.querySelector(".tabs button[data-tab=script]").click()'); await sleep(200);
  ok(await b.ev(`document.querySelectorAll(".script .s").length === ${ep.captions.length}`), 'script tab shows every spoken line');
  await b.ev('document.querySelectorAll(".script .s")[5].click()'); await sleep(200);
  ok(await b.ev(`Math.abs(window.__pods.audio.currentTime - ${ep.captions[5].t}) < 0.3`), 'clicking a script line seeks to it');
  await b.ev('document.querySelector(".tabs button[data-tab=about]").click()'); await sleep(100);
  ok((await b.ev('document.querySelector(".about").textContent')).includes('Nothing is invented'), 'about tab states the no-invention rule');
  if (idx.episodes.length > 1) {
    await b.ev('document.querySelectorAll("#eps .ep")[1].click()'); await sleep(800);
    ok(await b.ev(`window.__pods.S.cur.date === ${JSON.stringify(idx.episodes[1].date)} && document.querySelectorAll("#eps .ep")[1].classList.contains("on")`), 'archive card loads that episode');
  }
  await b.open(`${BASE}/e/${idx.episodes.at(-1).date}?t=90`, 3500);
  ok(await b.ev(`window.__pods.S.cur.date === ${JSON.stringify(idx.episodes.at(-1).date)}`), '/e/<date> deep link');
  ok(await b.ev('Math.abs(window.__pods.audio.currentTime - 90) < 1'), '?t= deep link seeks');
  await b.open(BASE + '/?empty=1', 2000);
  ok((await b.ev('document.body.textContent')).includes('No episodes on air'), 'honest empty state');
  await b.send('Emulation.setDeviceMetricsOverride', {width: 390, height: 844, deviceScaleFactor: 2, mobile: true});
  await b.open(BASE + '/', 3500);
  ok(await b.ev('document.documentElement.scrollWidth <= 392'), 'phone width: no horizontal overflow');
  await b.send('Emulation.setDeviceMetricsOverride', {width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false});
  const snap = ROOT + 'dist/pods-radio-snapshot.html';
  if (existsSync(snap)) {
    await b.open('file://' + snap, 6000);
    ok(await b.ev('window.__podsReady === true') && b.errors.filter((e) => !/ytimg|ERR_/.test(e)).length === 0, 'offline snapshot boots without errors');
    const emb = await b.ev('window.__PODS_SNAPSHOT__.embedded');
    ok(await b.ev(`window.__pods.audio.src.startsWith(${emb ? '"data:audio/mpeg"' : '"file:"'})`), `snapshot audio ${emb ? 'embedded' : 'linked'}`);
    ok(await b.ev(`document.querySelectorAll("#eps .ep").length === ${idx.episodes.length}`), 'snapshot carries the whole archive');
    await b.ev('document.querySelector("#bPlay").click()'); await sleep(1500);
    ok(await b.ev('window.__pods.audio.currentTime > 0.3'), 'snapshot audio plays offline');
  } else ok(false, 'snapshot exists');
} finally { b.close(); }
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
