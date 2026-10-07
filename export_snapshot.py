"""Build dist/pods-radio-snapshot.html: one self-contained offline file (CSS, JS, fonts, every episode, and the audio).
Audio is embedded as base64 data URIs when the MP3s total under 25 MB; otherwise the page links ../episodes/<date>/<file>.mp3.
Usage: python3 export_snapshot.py [--link]"""
import base64, json, os, sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
EPS, WEB = os.path.join(HERE, "episodes"), os.path.join(HERE, "web")
LIMIT = 25 * 1024 * 1024


def main():
    index = json.load(open(os.path.join(EPS, "index.json")))
    episodes = {m["date"]: json.load(open(os.path.join(EPS, m["date"], "episode.json"))) for m in index["episodes"]}
    mp3s = {d: os.path.join(EPS, d, e["audio"]) for d, e in episodes.items()}
    total = sum(os.path.getsize(p) for p in mp3s.values())
    embed = total < LIMIT and "--link" not in sys.argv
    audio = {d: ("data:audio/mpeg;base64," + base64.b64encode(open(p, "rb").read()).decode()) if embed else f"../episodes/{d}/{os.path.basename(p)}"
             for d, p in mp3s.items()}
    et = timezone(timedelta(hours=-4))
    snap = {"index": index, "episodes": episodes, "audio": audio, "embedded": embed, "audioBytes": total,
            "builtAt": datetime.now(et).strftime("%b %-d, %-I:%M %p ET")}
    html = open(os.path.join(WEB, "index.html")).read()
    css = open(os.path.join(WEB, "style.css")).read()
    for f in ("SpaceGrotesk.ttf", "JetBrainsMono.ttf"):
        b64 = base64.b64encode(open(os.path.join(WEB, "fonts", f), "rb").read()).decode()
        css = css.replace(f"url(fonts/{f})", f'url("data:font/ttf;base64,{b64}")')
    js = open(os.path.join(WEB, "app.js")).read()
    payload = json.dumps(snap, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace('<link rel="stylesheet" href="style.css">', f"<style>{css}</style>")
    html = html.replace('<script src="app.js"></script>', f"<script>window.__PODS_SNAPSHOT__ = {payload};</script>\n<script>{js}</script>")
    html = html.replace("<title>Pods Radio</title>", "<title>Pods Radio (offline snapshot)</title>")
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    out = os.path.join(HERE, "dist", "pods-radio-snapshot.html")
    open(out, "w").write(html)
    print(out, f"{os.path.getsize(out) / 1e6:.2f} MB; audio {total / 1e6:.2f} MB {'embedded' if embed else 'linked'}; {len(episodes)} episodes")


if __name__ == "__main__":
    main()
