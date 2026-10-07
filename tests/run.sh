#!/usr/bin/env bash
# Runs unit tests + the CDP smoke test against the live server on :4849.
cd "$(dirname "$0")/.." || exit 1
.venv/bin/python -m unittest discover -s tests -v 2>&1 | tail -4
node --experimental-websocket tests/smoke.mjs
