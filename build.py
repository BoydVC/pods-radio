"""Produce Pods Radio episodes: script → Piper TTS (per sentence, cached) → mix with sox-made music → MP3 + peaks + chapters.
Usage: .venv/bin/python build.py [--dates 2026-10-07,...] [--workers 3]"""
import argparse, hashlib, json, os, subprocess, sys, time, wave
from datetime import date, datetime, timedelta
from multiprocessing import Pool
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import feeds, script  # noqa: E402

SR = 22050
VOICE = os.environ.get("PODS_VOICE", "en_US-ryan-high")
LENGTH_SCALE = 1.0
WPS = 2.75                      # measured for ryan-high at length_scale 1.0
TARGET, LO, HI = 6.5 * 60, 5 * 60 + 10, 7 * 60 + 50
CACHE = os.path.join(HERE, "data", "tts")
EPDIR = os.path.join(HERE, "episodes")
GAP_SENT, GAP_PARA, GAP_SEG = 0.30, 0.55, 0.45


def supported_dates(data):
    """Dates whose full 7 AM → 7 AM window is covered by every YouTube channel's snapshot chain."""
    cov = data["coverage"]
    atoms = [v for k, v in cov.items() if k.endswith(":atom")]
    first = max(v["start"] for v in atoms)
    last = min(v["end"] for v in atoms)
    out, d = [], first.astimezone(feeds.ET_TZ).date()
    while True:
        s, e = script.window(d)
        if s >= first and e <= last + timedelta(minutes=30):
            out.append(d)
        if s > last:
            break
        d += timedelta(days=1)
    return out


def load_wav(p):
    with wave.open(p) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        assert w.getframerate() == SR, (p, w.getframerate())
    return a


_voice = None


def tts(text):
    global _voice
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(f"{VOICE}|{LENGTH_SCALE}|{text}".encode()).hexdigest()[:20]
    f = os.path.join(CACHE, key + ".npy")
    if os.path.exists(f):
        return np.load(f)
    if _voice is None:
        from piper import PiperVoice
        _voice = PiperVoice.load(os.path.join(HERE, "voices", VOICE + ".onnx"))
    from piper.config import SynthesisConfig
    chunks = [np.frombuffer(c.audio_int16_bytes, dtype=np.int16) for c in _voice.synthesize(text, SynthesisConfig(length_scale=LENGTH_SCALE))]
    a = (np.concatenate(chunks).astype(np.float32) / 32768) if chunks else np.zeros(1, np.float32)
    # trim leading/trailing near-silence so our own gaps control pacing
    nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz):
        a = a[max(0, nz[0] - 400): nz[-1] + 1200]
    np.save(f, a)
    return a


def estimate(ep):
    n_w = script.word_count(ep)
    n_s = sum(len(p) for s in ep["segments"] for p in s["paras"])
    n_p = sum(len(s["paras"]) for s in ep["segments"])
    return n_w / WPS + n_s * GAP_SENT + n_p * GAP_PARA + 7 * 1.5 + 12


def pick_detail(d, data):
    best = None
    for lvl in range(6):
        est = estimate(script.build(d, data, lvl))
        score = abs(est - TARGET)
        if best is None or score < best[1]:
            best = (lvl, score, est)
    return best[0]


def assemble(ep):
    M = {k: load_wav(os.path.join(HERE, "music", f"{k}.wav")) for k in
         ["bed", "theme", "outro", "sting_allin", "sting_moon", "sting_jesse", "sting_bill", "sting_lens", "sting_week"]}
    track, t = [], 0.0
    chapters, captions = [], []
    voice_regions = []

    def put(arr, at):
        track.append((arr, at))

    for seg in ep["segments"]:
        start = t
        if seg["stinger"]:
            st = M[f"sting_{seg['stinger']}"]
            put(st * 0.8, t)
            t += len(st) / SR - 0.35
        if seg["music"] == "open":
            t += 1.2                      # bed fades in first
        elif seg["music"] == "outro":
            t += 0.6
        vstart = t
        for pi, para in enumerate(seg["paras"]):
            for si, s in enumerate(para):
                a = tts(s["text"])
                put(a, t)
                captions.append({"t": round(t, 2), "d": round(len(a) / SR, 2), "text": s["text"], "refs": s["refs"], "seg": seg["id"]})
                t += len(a) / SR + GAP_SENT
            t += GAP_PARA - GAP_SENT
        voice_regions.append((vstart, t))
        if seg["music"] == "open":
            bed_len = t - start + 0.4
            bed = np.resize(M["bed"], int(bed_len * SR)) * 0.55
            fade = np.minimum(1, np.arange(len(bed)) / (1.2 * SR)) * np.minimum(1, (len(bed) - np.arange(len(bed))) / (1.5 * SR))
            put(bed * fade, start)
            put(M["theme"] * 0.9, t - 0.2)
            t += len(M["theme"]) / SR - 0.4
        elif seg["music"] == "outro":
            bed_len = t - start + 1.5
            bed = np.resize(M["bed"], int(bed_len * SR)) * 0.5
            fade = np.minimum(1, np.arange(len(bed)) / (0.8 * SR)) * np.minimum(1, (len(bed) - np.arange(len(bed))) / (2.0 * SR))
            put(bed * fade, start)
            put(M["outro"] * 0.9, t - 0.3)
            t += len(M["outro"]) / SR
        else:
            t += GAP_SEG
        chapters.append({"id": seg["id"], "title": seg["chapter"], "start": round(start, 2), "items": seg.get("items", []), "quiet": seg.get("quiet", False)})
    total = int((t + 0.5) * SR)
    out = np.zeros(total, np.float32)
    for arr, at in track:
        i = int(at * SR)
        n = min(len(arr), total - i)
        if n > 0:
            out[i:i + n] += arr[:n]
    peak = np.max(np.abs(out)) or 1
    out = out / peak * 0.89
    return out, chapters, captions


def peaks(a, bins=1600):
    n = len(a) // bins
    p = np.abs(a[: n * bins]).reshape(bins, n)
    pk = p.max(axis=1)
    rms = np.sqrt((p ** 2).mean(axis=1))
    s = max(pk.max(), 1e-6)
    return [round(float(x / s), 3) for x in pk], [round(float(x / s), 3) for x in rms]


def produce(dstr):
    data = feeds.load()
    d = date.fromisoformat(dstr)
    lvl = pick_detail(d, data)
    for attempt in range(4):
        ep = script.build(d, data, lvl)
        audio, chapters, captions = assemble(ep)
        dur = len(audio) / SR
        if dur < LO and lvl < 5:
            lvl += 1; continue
        if dur > HI and lvl > 0:
            lvl -= 1; continue
        break
    od = os.path.join(EPDIR, dstr)
    os.makedirs(od, exist_ok=True)
    wavp = os.path.join(od, "episode.wav")
    with wave.open(wavp, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    mp3 = os.path.join(od, f"pods-radio-{dstr}.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wavp, "-c:a", "libmp3lame", "-b:a", "48k", "-ar", str(SR), "-ac", "1",
                    "-metadata", f"title={ep['title']}", "-metadata", "artist=Pods Radio (TokenMax)", "-metadata", "album=Pods Radio",
                    "-metadata", f"date={dstr}", mp3], check=True)
    os.remove(wavp)
    pk, rms = peaks(audio)
    meta = {k: ep[k] for k in ("date", "title", "window", "counts", "notes", "weekNotes", "detail")}
    meta.update(duration=round(dur, 2), audio=os.path.basename(mp3), bytes=os.path.getsize(mp3), chapters=chapters,
                captions=captions, peaks=pk, rms=rms, voice=VOICE, engine="Piper TTS 1.8 (local, open source)",
                words=script.word_count(ep), builtAt=datetime.now(feeds.ET_TZ).isoformat(timespec="seconds"))
    with open(os.path.join(od, "episode.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False)
    with open(os.path.join(od, "script.md"), "w") as f:
        f.write(f"# {ep['title']}\n\nWindow: {ep['window'][0]} → {ep['window'][1]} · voice {VOICE} · detail {lvl}\n")
        for seg, ch in zip(ep["segments"], chapters):
            m, s = divmod(int(ch["start"]), 60)
            f.write(f"\n## [{m}:{s:02d}] {seg['chapter']}\n\n")
            for para in seg["paras"]:
                f.write(" ".join(x["text"] for x in para) + "\n\n")
    return dstr, round(dur, 1), lvl, script.word_count(ep)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    data = feeds.load()
    dates = [x.isoformat() for x in supported_dates(data)] if not a.dates else a.dates.split(",")
    print("dates:", dates, flush=True)
    t0 = time.time()
    with Pool(a.workers) as pool:
        for r in pool.imap_unordered(produce, sorted(dates, reverse=True)):
            print("done", r, f"{time.time() - t0:.0f}s", flush=True)
    idx = []
    for dstr in sorted(os.listdir(EPDIR), reverse=True):
        f = os.path.join(EPDIR, dstr, "episode.json")
        if os.path.exists(f):
            e = json.load(open(f))
            idx.append({k: e[k] for k in ("date", "title", "duration", "audio", "bytes", "counts", "voice", "words")})
    json.dump({"episodes": idx, "builtAt": datetime.now(feeds.ET_TZ).isoformat(timespec="seconds"),
               "coverage": {k: {"start": v["start"].isoformat(), "end": v["end"].isoformat(), "gaps": v["gaps"]} for k, v in data["coverage"].items()},
               "sources": sorted({s["file"] for s in data["snapshots"]})},
              open(os.path.join(EPDIR, "index.json"), "w"), indent=1)
    print("index written:", len(idx), "episodes")
