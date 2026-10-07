/* Pods Radio player: vanilla JS, no dependencies. Data: /api/index + /api/episode/<date>, or window.__PODS_SNAPSHOT__ offline. */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const Q = new URLSearchParams(location.search);
  const SNAP = window.__PODS_SNAPSHOT__ || null;
  const TZ = "America/New_York";
  const CH = {
    open: { name: "Cold open", c: "--c-open" }, allin: { name: "All-In Podcast", c: "--c-allin" },
    moon: { name: "Moonshots · Peter Diamandis", c: "--c-moon" }, jesse: { name: "Jesse Michels", c: "--c-jesse" },
    bill: { name: "Bill Simmons · The Ringer", c: "--c-bill" }, lens: { name: "Through the Pods lens", c: "--c-lens" },
    week: { name: "The week so far", c: "--c-week" }, outro: { name: "Outro", c: "--c-outro" },
  };
  const SHORT = { open: "Cold open", allin: "All-In", moon: "Moonshots", jesse: "Jesse Michels", bill: "Bill Simmons", lens: "Pods lens", week: "The week", outro: "Outro" };
  const shortName = (ch) => SHORT[ch.id] || ch.title;
  const ORDER = ["allin", "moon", "jesse", "bill"];
  const css = getComputedStyle(document.documentElement);
  const col = (id) => css.getPropertyValue((CH[id] || CH.open).c).trim() || "#5eead4";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const setHTML = (el, h) => { if (el && el.__h !== h) { el.innerHTML = h; el.__h = h; } };
  const mmss = (s) => { s = Math.max(0, Math.floor(s || 0)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
  const fmt = (iso, o) => new Intl.DateTimeFormat("en-US", { timeZone: TZ, ...o }).format(new Date(iso));
  const dayName = (d) => fmt(d + "T12:00:00-04:00", { weekday: "long", month: "long", day: "numeric" });
  const short = (d) => fmt(d + "T12:00:00-04:00", { weekday: "short", month: "short", day: "numeric" });
  const when = (iso) => fmt(iso, { weekday: "short", hour: "numeric", minute: "2-digit" }) + " ET";
  const dur = (v) => { const x = +v; if (!isFinite(x)) return String(v); const h = Math.floor(x / 3600), m = Math.round(x % 3600 / 60); return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m} min`; };
  const num = (n) => n == null ? "" : n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? (n / 1e3).toFixed(n >= 1e4 ? 0 : 1) + "K" : String(n);

  if (Q.has("still")) document.body.classList.add("still");
  if (Q.has("kiosk")) document.body.classList.add("kiosk");
  if (innerWidth >= 1300 && innerHeight >= 1000 && !Q.has("scroll")) document.body.classList.add("fit");  // QA 2026-10-07: fit-to-screen needs a TV-height window; shorter laptops scroll

  const audio = $("#audio");
  const S = { index: null, eps: {}, cur: null, tab: Q.get("tab") || "notes", liveRef: null, liveCap: -1, hover: null };

  /* ---------- data ---------- */
  async function getIndex() {
    if (Q.has("empty")) return { episodes: [], error: "Simulated empty state (?empty=1)" };
    if (SNAP) return SNAP.index;
    try { const r = await fetch("/api/index", { cache: "no-store" }); return await r.json(); }
    catch (e) { return { episodes: [], error: "Pods Radio server unreachable: " + e.message }; }
  }
  async function getEp(d) {
    if (S.eps[d]) return S.eps[d];
    const e = SNAP ? SNAP.episodes[d] : await (await fetch("/api/episode/" + d, { cache: "no-store" })).json();
    S.eps[d] = e; return e;
  }
  const audioSrc = (e) => SNAP ? (SNAP.audio[e.date] || `../episodes/${e.date}/${e.audio}`) : `/episodes/${e.date}/${e.audio}`;

  /* ---------- starfield ---------- */
  const sky = $("#sky"), sx = sky.getContext("2d");
  let stars = [];
  function sizeSky() {
    sky.width = innerWidth * devicePixelRatio; sky.height = innerHeight * devicePixelRatio;
    let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    stars = Array.from({ length: 260 }, () => ({ x: rnd(), y: rnd(), r: rnd() * 1.3 + .2, p: rnd() * 6.28, s: rnd() * .6 + .2 }));
  }
  function drawSky(t) {
    const w = sky.width, h = sky.height; sx.clearRect(0, 0, w, h);
    const g = sx.createRadialGradient(w * .22, h * .1, 0, w * .22, h * .1, w * .7);
    g.addColorStop(0, "rgba(94,234,212,.07)"); g.addColorStop(1, "rgba(0,0,0,0)"); sx.fillStyle = g; sx.fillRect(0, 0, w, h);
    const g2 = sx.createRadialGradient(w * .85, h * .95, 0, w * .85, h * .95, w * .6);
    g2.addColorStop(0, "rgba(248,113,113,.06)"); g2.addColorStop(1, "rgba(0,0,0,0)"); sx.fillStyle = g2; sx.fillRect(0, 0, w, h);
    for (const s of stars) {
      const a = Q.has("still") ? .55 : .35 + .35 * Math.sin(t / 1000 * s.s + s.p);
      sx.fillStyle = `rgba(220,235,255,${a})`; sx.beginPath(); sx.arc(s.x * w, s.y * h, s.r * devicePixelRatio, 0, 6.28); sx.fill();
    }
  }

  /* ---------- waveform ---------- */
  const wave = $("#wave"), wx = wave.getContext("2d");
  function chapAt(e, t) { let c = e.chapters[0]; for (const ch of e.chapters) if (ch.start <= t + .01) c = ch; return c; }
  function drawWave() {
    const e = S.cur; if (!e) return;
    const W = wave.clientWidth, H = wave.clientHeight, dpr = devicePixelRatio;
    if (wave.width !== W * dpr || wave.height !== H * dpr) { wave.width = W * dpr; wave.height = H * dpr; }
    wx.setTransform(dpr, 0, 0, dpr, 0, 0); wx.clearRect(0, 0, W, H);
    const dur = e.duration, t = audio.currentTime || 0, mid = H * .56;
    // chapter tints
    e.chapters.forEach((ch, i) => {
      const x0 = ch.start / dur * W, x1 = (e.chapters[i + 1] ? e.chapters[i + 1].start : dur) / dur * W;
      wx.fillStyle = col(ch.id) + (chapAt(e, t).id === ch.id ? "14" : "08"); wx.fillRect(x0, 0, x1 - x0, H);
    });
    const step = 3, bw = 2, n = Math.floor(W / step), P = e.peaks, R = e.rms;
    for (let i = 0; i < n; i++) {
      const a = Math.floor(i / n * P.length), b = Math.max(a + 1, Math.floor((i + 1) / n * P.length));
      let pk = 0, rm = 0; for (let j = a; j < b; j++) { pk = Math.max(pk, P[j]); rm = Math.max(rm, R[j]); }
      const x = i * step, tt = x / W * dur, played = tt <= t;
      const c = col(chapAt(e, tt).id);
      const hp = Math.max(1.5, pk * mid * .95), hr = Math.max(1, rm * mid * 1.35);
      wx.fillStyle = played ? c : "rgba(148,163,184,.22)"; wx.globalAlpha = played ? .45 : 1;
      wx.fillRect(x, mid - hp, bw, hp + (H - mid) * pk * .5);
      wx.globalAlpha = 1; wx.fillStyle = played ? c : "rgba(203,213,225,.42)";
      wx.fillRect(x, mid - hr, bw, hr + (H - mid) * rm * .5);
    }
    wx.fillStyle = "rgba(148,163,184,.18)"; wx.fillRect(0, mid, W, 1);
    // playhead
    const px = t / dur * W;
    wx.shadowColor = "#5eead4"; wx.shadowBlur = 14; wx.fillStyle = "#e6fffa"; wx.fillRect(px - 1, 0, 2, H); wx.shadowBlur = 0;
    wx.beginPath(); wx.arc(px, 4, 4.5, 0, 6.28); wx.fill();
    if (S.hover != null) { wx.fillStyle = "rgba(255,255,255,.35)"; wx.fillRect(S.hover - .5, 0, 1, H); }
  }
  function seekFromX(clientX) { const r = wave.getBoundingClientRect(); seek((clientX - r.left) / r.width * S.cur.duration); }
  wave.addEventListener("click", (ev) => seekFromX(ev.clientX));
  wave.addEventListener("mousemove", (ev) => {
    const r = wave.getBoundingClientRect(), x = ev.clientX - r.left, t = x / r.width * S.cur.duration, ht = $("#hoverT");
    S.hover = x; ht.style.left = x + "px"; ht.style.opacity = 1; ht.textContent = `${mmss(t)} · ${chapAt(S.cur, t).title}`; drawWave();
  });
  wave.addEventListener("mouseleave", () => { S.hover = null; $("#hoverT").style.opacity = 0; drawWave(); });

  /* ---------- VU meter (driven by the episode's own RMS envelope) ---------- */
  const vu = $("#vu"), vx = vu.getContext("2d");
  function drawVU() {
    const e = S.cur; const W = vu.width, H = vu.height; vx.clearRect(0, 0, W, H);
    let lvl = 0;
    if (e && !audio.paused) { const i = Math.min(e.rms.length - 1, Math.floor(audio.currentTime / e.duration * e.rms.length)); lvl = Math.min(1, e.rms[i] * 1.6); }
    const n = 18, gw = W / n;
    for (let i = 0; i < n; i++) {
      const on = i / n < lvl; vx.fillStyle = i > 14 ? "#f87171" : i > 10 ? "#fbbf24" : "#5eead4"; vx.globalAlpha = on ? 1 : .14;
      vx.fillRect(i * gw + 1, 4, gw - 3, H - 8);
    }
    vx.globalAlpha = 1;
  }

  /* ---------- rendering ---------- */
  function renderHeader() {
    const e = S.cur, idx = S.index;
    const w = e ? `<b>WINDOW</b> ${fmt(e.window[0], { weekday: "short", hour: "numeric", minute: "2-digit" })} → ${fmt(e.window[1], { weekday: "short", hour: "numeric", minute: "2-digit" })} ET` : "";
    const cov = idx && idx.coverage ? Object.entries(idx.coverage) : [];
    const rss = cov.filter(([k]) => k.endsWith(":rss")).map(([, v]) => v.end).sort()[0];
    const stale = e && rss && rss < e.window[1].replace("-04:00", "") ? `<div class="warn">PODCAST RSS LAST CHECKED ${fmt(rss, { weekday: "short", hour: "numeric", minute: "2-digit" })} ET</div>` : "";
    setHTML($("#meta"), `${w}<div><b>VOICE</b> ${esc(e ? e.voice : "")} · ${esc(e ? e.engine : "")}</div>${SNAP ? '<div><b>OFFLINE SNAPSHOT</b> ' + esc(SNAP.builtAt) + "</div>" : ""}${stale}`);
  }
  function renderHero() {
    const e = S.cur, c = e.counts;
    const vids = c.videos ?? 0, shorts = c.shorts ?? 0, pods = c.podcast ?? 0;
    setHTML($("#hero"), `<div><div class="kicker mono">DAILY EPISODE · ${esc(short(e.date)).toUpperCase()}</div><h1>${esc(dayName(e.date))}</h1>
      <div class="sub">What's new on Boyd's four watched channels, read straight from the feeds. ${mmss(e.duration)} · ${e.words} words</div></div>
      <div class="stats"><div class="stat"><div class="v">${vids}</div><div class="k">VIDEOS</div></div><div class="stat"><div class="v">${shorts}</div><div class="k">SHORTS</div></div>
      <div class="stat"><div class="v">${pods}</div><div class="k">PODCAST EPS</div></div><div class="stat"><div class="v">${c.channels ?? 0}/4</div><div class="k">CHANNELS ACTIVE</div></div></div>`);
    $("#tDur").textContent = mmss(e.duration);
    const W = 100;
    setHTML($("#chapMarks"), e.chapters.map((ch, i) => {
      const nx = e.chapters[i + 1] ? e.chapters[i + 1].start : e.duration;
      return `<span style="left:${ch.start / e.duration * W}%;max-width:calc(${(nx - ch.start) / e.duration * W}% - 6px);color:${col(ch.id)}" title="${esc(ch.title)}">${esc((ch.id === "open" ? "Open" : shortName(ch)).toUpperCase())}</span>`;
    }).join(""));
    setHTML($("#chapters"), e.chapters.map((ch, i) => {
      const nx = e.chapters[i + 1] ? e.chapters[i + 1].start : e.duration;
      return `<button class="ch${ch.quiet ? " quiet" : ""}" data-i="${i}" style="--cc:${col(ch.id)}"><span class="n">${i + 1}</span><span class="tx"><div class="t" title="${esc(ch.title)}">${esc(shortName(ch))}</div>
        <div class="s">${i + 1} · ${mmss(ch.start)} · ${mmss(nx - ch.start)}${ch.items && ch.items.length && !["open", "week", "outro"].includes(ch.id) ? ` · ${ch.items.length}` : ch.quiet ? " · quiet" : ""}</div></span><span class="bar"></span></button>`;
    }).join(""));
    $$("#chapters .ch").forEach((b) => b.onclick = () => { seek(e.chapters[+b.dataset.i].start + .01); if (audio.paused && !Q.has("still")) play(); });
  }
  function itemHTML(n, gid) {
    const kd = n.kind === "short" ? "SHORT" : n.kind === "podcast" ? "PODCAST" : "VIDEO";
    const meta = [when(n.published), kd.toLowerCase(), n.views != null ? num(n.views) + " views" : "", n.duration ? dur(n.duration) : ""].filter(Boolean).map(esc).join(" · ");
    const thumb = n.thumb ? `<div class="thumb"><img loading="lazy" src="${esc(n.thumb)}" alt="" onerror="this.remove()"><span class="kd">${kd}</span></div>` : "";
    const topics = n.chapters && n.chapters.length ? `<details class="topics"><summary>${n.chapters.length} TOPICS FROM THE DESCRIPTION</summary><ol>${n.chapters.map((c) => `<li>${esc(c)}</li>`).join("")}</ol></details>` : "";
    return `<div class="item${thumb ? "" : " noimg"}" data-id="${esc(n.id)}" style="--gc:${col(gid)}">${thumb}<div><h4><a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a></h4>
      <div class="im">${meta}</div>${n.summary && n.summary !== n.title ? `<div class="sum">${esc(n.summary.length > 320 ? n.summary.slice(0, 317).replace(/\s\S*$/, "") + "…" : n.summary)}</div>` : ""}
      ${n.lens && n.lens.length ? `<div class="tags">${n.lens.map((l) => `<span class="tag">${esc(l)}</span>`).join("")}</div>` : ""}${topics}</div></div>`;
  }
  function renderTab() {
    const e = S.cur, body = $("#tabBody");
    $$(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === S.tab));
    let h = "";
    if (S.tab === "notes") {
      h = ORDER.map((id) => {
        const items = e.notes.filter((n) => n.channel === id);
        return `<div class="grp" style="--gc:${col(id)}"><div class="grp-h">${esc(CH[id].name.toUpperCase())}<span class="c">${items.length || "quiet"}</span><span class="ln"></span></div>
          ${items.length ? items.map((n) => itemHTML(n, id)).join("") : `<div class="quietnote">Nothing new from this channel between ${esc(fmt(e.window[0], { weekday: "short", hour: "numeric" }))} and ${esc(fmt(e.window[1], { weekday: "short", hour: "numeric" }))} ET in the feeds.</div>`}</div>`;
      }).join("");
    } else if (S.tab === "script") {
      const segs = [];
      e.captions.forEach((c, i) => {
        let s = segs[segs.length - 1];
        if (!s || s.id !== c.seg) segs.push(s = { id: c.seg, paras: [[]] });
        const prev = e.captions[i - 1];
        if (prev && prev.seg === c.seg && c.t - (prev.t + prev.d) > .5) s.paras.push([]);
        s.paras[s.paras.length - 1].push([c, i]);
      });
      h = `<div class="script">${segs.map((s) => {
        const ch = e.chapters.find((x) => x.id === s.id) || { title: s.id, start: 0 };
        return `<h3 style="--gc:${col(s.id)}">[${mmss(ch.start)}] ${esc(ch.title.toUpperCase())}</h3>${s.paras.map((p) => `<p>${p.map(([c, i]) => `<span class="s" data-c="${i}">${esc(c.text)}</span>`).join(" ")}</p>`).join("")}`;
      }).join("")}</div>`;
    } else if (S.tab === "week") {
      const w = e.weekNotes || [];
      const byDay = {};
      w.forEach((n) => { const k = fmt(n.published, { weekday: "long", month: "short", day: "numeric" }); (byDay[k] = byDay[k] || []).push(n); });
      h = w.length ? Object.entries(byDay).map(([k, items]) => `<div class="grp" style="--gc:var(--green)"><div class="grp-h">${esc(k.toUpperCase())}<span class="c">${items.length}</span><span class="ln"></span></div>${items.map((n) => itemHTML(n, n.channel)).join("")}</div>`).join("")
        : `<div class="quietnote">No full episodes earlier in this week in the feeds.</div>`;
    } else {
      const idx = S.index || {};
      const cov = Object.entries(idx.coverage || {}).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(fmt(v.start, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }))} → ${esc(fmt(v.end, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }))} ET</td><td>${v.gaps && v.gaps.length ? v.gaps.length + " gap(s)" : "continuous"}</td></tr>`).join("");
      h = `<div class="about"><h3>WHAT THIS IS</h3>A daily radio show auto-produced from the YouTube and podcast feeds Boyd's Pods bot watches. Each episode covers the 24 hours from 7:00 AM ET the day before to 7:00 AM ET on the episode date.
        <h3>THE RULE</h3>Every line comes from feed <b>titles, dates and descriptions</b>. Nothing is invented: no transcripts, no guesses about what was said. Sponsor reads, links and credits are stripped from descriptions. A quiet channel is reported as quiet.
        <h3>HOW IT'S MADE</h3>Script <code>script.py</code> → voice <code>${esc(e.voice)}</code> via ${esc(e.engine)} → cold open, stingers and outro synthesized with <code>sox</code> → mixed in numpy → MP3 via <code>ffmpeg</code>. Waveform, chapters and captions come from the same mix.
        <h3>KNOWN GAPS</h3>Descriptions only, never transcripts. YouTube shorts often have no description, so only the title is read. Views are as of the feed snapshot. The podcast RSS snapshots stop where the table below says, so later audio-only episodes are flagged, not guessed. The Pods lens is keyword matching. Thumbnails load from YouTube, so they are blank offline.
        <h3>FEED COVERAGE</h3><table>${cov}</table>
        ${SNAP ? "" : `<h3>SUBSCRIBE (LOCAL)</h3>Pods Radio is also a podcast feed: <code>${esc(location.origin)}/feed.xml</code>. It only works on this machine, and nothing is published.`}
        <h3>KEYS</h3><code>space</code> play/pause · <code>← →</code> 15 s · <code>[ ]</code> chapter · <code>, .</code> previous/next episode · <code>s</code> speed</div>`;
    }
    setHTML(body, h);
    if (S.tab === "script") $$(".script .s", body).forEach((el) => el.onclick = () => seek(e.captions[+el.dataset.c].t + .01));
    S.liveRef = null; S.liveCap = -1; tick(true);
  }
  function spark(cv, e) {
    const W = cv.clientWidth || 200, H = cv.clientHeight || 30, dpr = devicePixelRatio; cv.width = W * dpr; cv.height = H * dpr;
    const x = cv.getContext("2d"); x.scale(dpr, dpr); const n = Math.floor(W / 3);
    for (let i = 0; i < n; i++) {
      const a = Math.floor(i / n * e.rms.length), t = i / n * e.duration; let v = 0;
      for (let j = a; j < Math.floor((i + 1) / n * e.rms.length); j++) v = Math.max(v, e.rms[j]);
      const h = Math.max(1, v * H * 1.2); x.fillStyle = col(chapAt(e, t).id); x.globalAlpha = .8; x.fillRect(i * 3, (H - h) / 2, 2, h);
    }
  }
  async function renderArchive() {
    const list = S.index.episodes;
    setHTML($("#eps"), list.map((m) => `<button class="ep${S.cur && S.cur.date === m.date ? " on" : ""}" data-d="${m.date}"><div class="d"><span class="dw">${esc(short(m.date))}</span><span class="du">${mmss(m.duration)}</span></div>
      <canvas></canvas><div class="hl"></div><div class="cn">${ORDER.map((id) => `<i style="--cc:${col(id)}" data-ch="${id}">${esc(id === "allin" ? "AI" : id === "moon" ? "MS" : id === "jesse" ? "JM" : "BS")}</i>`).join("")}</div></button>`).join(""));
    $$("#eps .ep").forEach((b) => b.onclick = () => load(b.dataset.d, true));
    for (const b of $$("#eps .ep")) {
      const e = await getEp(b.dataset.d); spark($("canvas", b), e);
      const first = e.captions.find((c) => c.seg === "open" && c.refs.length);
      const n = first && e.notes.find((x) => x.id === first.refs[0]);
      $(".hl", b).textContent = n ? n.title : "Quiet day on the feeds";
      $$(".cn i", b).forEach((i) => { const k = e.notes.filter((x) => x.channel === i.dataset.ch).length; i.textContent += " " + k; i.classList.toggle("z", !k); });
    }
  }

  /* ---------- playback ---------- */
  const SPEEDS = [1, 1.25, 1.5, .85];
  function play() { audio.play().catch(() => {}); }
  function seek(t) { audio.currentTime = Math.max(0, Math.min(S.cur.duration - .05, t)); tick(true); }
  function chapStep(d) {
    const e = S.cur, t = audio.currentTime; const i = e.chapters.indexOf(chapAt(e, t));
    const j = d < 0 && t - e.chapters[i].start > 2 ? i : i + d;
    seek((e.chapters[Math.max(0, Math.min(e.chapters.length - 1, j))] || e.chapters[0]).start + .01);
  }
  $("#bPlay").onclick = () => audio.paused ? play() : audio.pause();
  $("#bBack").onclick = () => seek(audio.currentTime - 15);
  $("#bFwd").onclick = () => seek(audio.currentTime + 30);
  $("#bPrevCh").onclick = () => chapStep(-1);
  $("#bNextCh").onclick = () => chapStep(1);
  $("#bSpeed").onclick = () => { const i = (SPEEDS.indexOf(audio.playbackRate) + 1) % SPEEDS.length; audio.playbackRate = SPEEDS[i]; $("#bSpeed").textContent = SPEEDS[i] + "×"; };
  $$(".tabs button").forEach((b) => b.onclick = () => { S.tab = b.dataset.tab; renderTab(); });
  audio.addEventListener("play", () => document.body.classList.add("playing"));
  audio.addEventListener("pause", () => document.body.classList.remove("playing"));
  audio.addEventListener("ended", () => { document.body.classList.remove("playing"); const l = S.index.episodes, i = l.findIndex((m) => m.date === S.cur.date); if (Q.has("continuous") && l[i + 1]) load(l[i + 1].date, true); });
  addEventListener("keydown", (ev) => {
    if (!S.cur || (ev.target.closest && ev.target.closest("input,textarea"))) return;
    const l = S.index.episodes, i = l.findIndex((m) => m.date === S.cur.date);
    const k = ev.key;
    if (k === " ") { ev.preventDefault(); $("#bPlay").click(); }
    else if (k === "ArrowLeft") seek(audio.currentTime - 15);
    else if (k === "ArrowRight") seek(audio.currentTime + 30);
    else if (k === "[") chapStep(-1); else if (k === "]") chapStep(1);
    else if (k === ",") l[i + 1] && load(l[i + 1].date); else if (k === ".") l[i - 1] && load(l[i - 1].date);
    else if (k === "s") $("#bSpeed").click();
  });

  function tick(force) {
    const e = S.cur; if (!e) return;
    const t = audio.currentTime || 0;
    $("#tCur").textContent = mmss(t);
    const chap = chapAt(e, t), ci = e.chapters.indexOf(chap);
    $$("#chapters .ch").forEach((b, i) => {
      b.classList.toggle("on", i === ci);
      const nx = e.chapters[i + 1] ? e.chapters[i + 1].start : e.duration;
      $(".bar", b).style.width = (i < ci ? 100 : i === ci ? (t - e.chapters[i].start) / (nx - e.chapters[i].start) * 100 : 0) + "%";
    });
    // caption
    let k = -1; for (let i = 0; i < e.captions.length; i++) { if (e.captions[i].t <= t + .05) k = i; else break; }
    const c = e.captions[k];
    const active = c && t <= c.t + c.d + .7;
    if (k !== S.liveCap || force) {
      S.liveCap = k;
      const cap = $("#caption");
      if (!c || (t === 0 && audio.paused && !Q.has("t"))) {
        cap.classList.add("idle"); setHTML($(".prev", cap), "");
        setHTML($(".cur", cap), `Press play for ${esc(dayName(e.date))}. Captions follow along, and the show notes light up as each item is read.`);
      } else {
        cap.classList.remove("idle");
        const p = e.captions[k - 1];
        setHTML($(".prev", cap), p ? esc(p.text) : "");
        setHTML($(".cur", cap), `<span class="seg" style="color:${col(c.seg)}">${esc((c.seg === "open" ? "COLD OPEN" : (CH[c.seg] || { name: c.seg }).name).toUpperCase())}</span>${esc(c.text)}`);
      }
      $$(".script .s.live").forEach((x) => x.classList.remove("live"));
      const sl = $(`.script .s[data-c="${k}"]`); if (sl) { sl.classList.add("live"); if (!audio.paused || force) scrollInto(sl); }
    }
    // live show-note item
    let ref = null;
    for (let i = k; i >= 0 && i > k - 3; i--) { const cc = e.captions[i]; if (cc && cc.seg === chap.id && cc.refs.length) { ref = cc.refs[0]; break; } }
    if (!active) ref = ref;
    if (ref !== S.liveRef || force) {
      S.liveRef = ref;
      $$(".item.live").forEach((x) => x.classList.remove("live"));
      if (ref) { const el = $(`.item[data-id="${CSS.escape(ref)}"]`); if (el) { el.classList.add("live"); scrollInto(el); } }
    }
    drawWave();
  }
  function scrollInto(el) {
    const box = $("#tabBody"), r = el.getBoundingClientRect(), b = box.getBoundingClientRect();
    if (r.top < b.top + 10 || r.bottom > b.bottom - 10) box.scrollTop += r.top - b.top - 60;
  }

  async function load(d, autoplay) {
    const e = await getEp(d);
    S.cur = e;
    audio.src = audioSrc(e);
    audio.playbackRate = parseFloat($("#bSpeed").textContent) || 1;
    if (!SNAP && history.replaceState && !Q.has("ep")) history.replaceState(null, "", "/e/" + d + location.search);
    renderHeader(); renderHero(); renderTab();
    $$("#eps .ep").forEach((b) => b.classList.toggle("on", b.dataset.d === d));
    document.title = `Pods Radio · ${short(d)}`;
    const t0 = parseFloat(Q.get("t"));
    if (t0 >= 0) { const go = () => { audio.currentTime = t0; tick(true); }; audio.readyState >= 1 ? go() : audio.addEventListener("loadedmetadata", go, { once: true }); }
    if (autoplay) play();
    tick(true);
  }

  function renderEmpty(msg) {
    $("#main").innerHTML = `<section class="panel empty" style="grid-column:1/-1"><div><h2>No episodes on air</h2><p>${esc(msg || "No episodes have been built yet.")}</p>
      <p class="mono" style="font-size:13px">Run <b>.venv/bin/python build.py</b> in /workspace/tokenmax/pods-radio, then reload. Nothing is made up to fill the gap.</p></div></section>`;
    $("#archive").style.display = "none";
    setHTML($("#meta"), `<div class="warn">${esc(msg || "")}</div>`);
  }

  /* ---------- boot ---------- */
  async function boot() {
    sizeSky(); addEventListener("resize", () => { sizeSky(); drawWave(); });
    S.index = await getIndex();
    if (!S.index.episodes || !S.index.episodes.length) { renderEmpty(S.index.error); return loop(); }
    const fromPath = (location.pathname.match(/\/e\/(\d{4}-\d{2}-\d{2})/) || [])[1];
    const want = Q.get("ep") || fromPath;
    const d = S.index.episodes.some((m) => m.date === want) ? want : S.index.episodes[0].date;
    await load(d, Q.has("autoplay"));
    renderArchive();
    if (Q.has("burn")) { document.body.classList.add("burn"); let i = 0; setInterval(() => { i++; document.body.style.setProperty("--bx", (i % 3 - 1) * 3 + "px"); document.body.style.setProperty("--by", ((i >> 1) % 3 - 1) * 3 + "px"); }, 60000); }
    window.__podsReady = true;
    loop();
  }
  let last = 0;
  function loop(ts = 0) {
    if (ts - last > 33) { last = ts; drawSky(ts); if (S.cur && !audio.paused) tick(); drawVU(); }
    if (!Q.has("still")) requestAnimationFrame(loop); else { drawSky(0); drawVU(); }
  }
  window.__pods = { S, audio, seek, load };
  boot();
})();
