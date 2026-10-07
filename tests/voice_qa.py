"""Voice intelligibility QA: transcribe a sample of synthesized sentences with faster-whisper (base.en, local) and score word error rate.
Run: .venv/bin/python tests/voice_qa.py [N]   → writes data/voice_qa.json"""
import hashlib, json, os, random, re, sys
import numpy as np
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import build, feeds, script  # noqa: E402


def norm(t):
    t = t.lower().replace("a.i.", "ai").replace("-", " ")
    return re.findall(r"[a-z0-9']+", t)


def wer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return d[len(h)] / max(1, len(r))


def main(n=14):
    data = feeds.load()
    texts = set()
    for d in build.supported_dates(data):
        ep = script.build(d, data, build.pick_detail(d, data))
        for seg in ep["segments"]:
            for p in seg["paras"]:
                for s in p:
                    texts.add(s["text"])
    cached = []
    for t in sorted(texts):
        key = hashlib.sha1(f"{build.VOICE}|{build.LENGTH_SCALE}|{t}".encode()).hexdigest()[:20]
        f = os.path.join(build.CACHE, key + ".npy")
        if os.path.exists(f):
            cached.append((t, f))
    random.Random(4849).shuffle(cached)
    from faster_whisper import WhisperModel
    m = WhisperModel("base.en", device="cpu", compute_type="float32", cpu_threads=3)
    rows = []
    for t, f in cached[:n]:
        a = np.load(f)
        a16 = np.interp(np.arange(0, len(a), build.SR / 16000), np.arange(len(a)), a).astype(np.float32)
        hyp = " ".join(s.text for s in m.transcribe(a16, language="en", beam_size=1)[0]).strip()
        rows.append({"text": t, "heard": hyp, "wer": round(wer(t, hyp), 3)})
        print(f"{rows[-1]['wer']:.2f}  {t[:70]!r}\n      heard {hyp[:70]!r}", flush=True)
    tw = sum(len(norm(r["text"])) for r in rows)
    agg = sum(r["wer"] * len(norm(r["text"])) for r in rows) / max(1, tw)
    out = {"model": "faster-whisper base.en (float32, local; int8 decodes garbage on this CPU build)", "voice": build.VOICE, "sentences": len(rows), "words": tw, "wer": round(agg, 3), "rows": rows}
    json.dump(out, open(os.path.join(HERE, "data", "voice_qa.json"), "w"), indent=1, ensure_ascii=False)
    print(f"WER {agg:.1%} over {tw} words / {len(rows)} sentences")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 14)
