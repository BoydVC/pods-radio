#!/usr/bin/env bash
# screenshot.sh <url> <out.png> [WxH]  (headless Chrome, fresh profile each run so CSS is never stale)
URL="$1"; OUT="$2"; SIZE="${3:-1920,1080}"
PROFILE=$(mktemp -d /tmp/pr-shot-XXXX)
google-chrome --headless=new --user-data-dir="$PROFILE" --no-sandbox --disable-gpu --hide-scrollbars --window-size="$SIZE" \
  --autoplay-policy=no-user-gesture-required --virtual-time-budget=9000 --run-all-compositor-stages-before-draw --screenshot="$OUT" "$URL" >/dev/null 2>&1
rm -rf "$PROFILE"; echo "$OUT"
