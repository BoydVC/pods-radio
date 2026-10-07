#!/usr/bin/env bash
# Regenerate screenshots/ from the running server (:4849) and the offline snapshot.
cd "$(dirname "$0")"; mkdir -p screenshots
B=http://127.0.0.1:4849
read -r LATEST T1 T2 T3 OLD T4 <<<"$(python3 - <<'PY'
import json
idx = json.load(open("episodes/index.json"))["episodes"]
def t(d, seg, k=0):
    e = json.load(open(f"episodes/{d}/episode.json"))
    cs = [c for c in e["captions"] if c["seg"] == seg and c["refs"]] or [c for c in e["captions"] if c["seg"] == seg] or e["captions"]
    return round(cs[min(k, len(cs) - 1)]["t"] + .4, 1)
L, O = idx[0]["date"], idx[min(3, len(idx) - 1)]["date"]
print(L, t(L, "allin"), t(L, "lens"), t(L, "jesse"), O, t(O, "moon", 1))
PY
)"
./screenshot.sh "$B/?still=1&t=$T1" screenshots/01-player-latest.png
./screenshot.sh "$B/?still=1&t=$T2" screenshots/02-lens-segment-captions.png
./screenshot.sh "$B/?still=1&tab=script&t=$T3" screenshots/03-script-follow-along.png
./screenshot.sh "$B/e/$OLD?still=1&t=$T4" screenshots/04-archive-episode-$OLD.png
./screenshot.sh "$B/?still=1&tab=week" screenshots/05-earlier-this-week.png
./screenshot.sh "$B/?still=1&tab=about" screenshots/06-about-coverage.png
./screenshot.sh "file://$PWD/dist/pods-radio-snapshot.html?still=1&t=$T1" screenshots/07-offline-snapshot.png
./screenshot.sh "$B/?still=1&empty=1" screenshots/08-empty-state.png
./screenshot.sh "$B/?still=1&scroll=1&t=$T1" screenshots/09-phone.png 390,1500
