# Pods Radio 📻

A daily radio show produced automatically from the YouTube and podcast feeds that Boyd's **Pods** bot watches:
All-In, Moonshots (Peter Diamandis), Jesse Michels, and Bill Simmons / The Ringer.
Each episode covers **7:00 AM ET the day before → 7:00 AM ET** on the episode date, which is when Pods sends its brief.

**The rule:** every spoken line comes from feed **titles, dates and descriptions**. There are no transcripts and no guesses about what anyone said.
Sponsor reads, links and credits are stripped out. A quiet channel is reported as quiet. `tests/test_pods.py::test_script_never_invents`
checks that every content word spoken comes from the referenced feed item, the script templates, or the calendar.

- Player: **http://127.0.0.1:4849** (deep links `/e/2026-10-04?t=90`, local podcast feed `/feed.xml`)
- Offline: `dist/pods-radio-snapshot.html` is one file of about 23 MB with all 7 episodes. The audio (16.7 MB of MP3) is embedded, so it plays with no server.

## Episodes

| Date | Length | Words | Uploads (videos / shorts / podcast) | Active channels |
|---|---|---|---|---|
| Wed Oct 7 | 6:00 | 809 | 0 / 7 / 0* | 4 of 4 |
| Tue Oct 6 | 6:45 | 909 | 1 / 7 / 1 | 3 of 4 |
| Mon Oct 5 | 6:33 | 873 | 0 / 2 / 1 | 1 of 4 |
| Sun Oct 4 | 6:36 | 833 | 1 / 5 / 1 | 3 of 4 |
| Sat Oct 3 | 6:48 | 919 | 2 / 7 / 1 | 3 of 4 |
| Fri Oct 2 | 6:31 | 884 | 0 / 9 / 1 | 3 of 4 |
| Thu Oct 1 | 7:08 | 966 | 2 / 7 / 1 | 3 of 4 |

\*The podcast RSS snapshots were last fetched Tue Oct 6, 6:49 AM ET. The Oct 7 show says so on air and doesn't guess.

Each show has the same running order:
1. Cold open over a music bed, with the theme sting.
2. One segment per channel, each with its own sox stinger. Full episodes come with description sentences and chapter topics; shorts come with their titles.
3. **Through the Pods lens**: keyword matches for AI and agents, Musk companies, acceleration, Ravens/Orioles/Chelsea/Terps, and NFL picks.
4. **Numbers and the week so far**: the most-watched new upload, plus a recap of real earlier items.
5. Outro.

The recap is longer on light days, so every show lands between 5 and 8 minutes without padding.

## Pipeline

```
feeds.py   parse every Atom/RSS snapshot (/workspace/feed_*.xml, /workspace/pods/*.xml, /workspace/pods-rss/*.xml), merge by id,
           and prove coverage: a 15-entry snapshot is complete from its oldest entry to its fetch time; chains join where they overlap
script.py  window → segments → sentences, each tagged with the feed item ids it reads from (refs)
music.py   sox: 24 s Dmaj7 pad bed, theme and outro stings, one 3-note stinger per segment → music/*.wav
build.py   Piper TTS per sentence (cached in data/tts) → numpy mix (gaps, music bed, stingers, normalize) → MP3 48 kbps (ffmpeg)
           + episode.json (chapters, captions with timings and refs, 1600-bin peaks/RMS, show notes) + script.md
server.py  stdlib HTTP on 127.0.0.1:4849, Range support for seeking, /api/index, /api/episode/<date>, /feed.xml, /api/health
web/       player: waveform with chapter tints and markers, transport, live captions, show notes that light up as each item is read,
           a follow-along script (click a line to seek), earlier this week, about/coverage, archive with mini-waveforms
```

- **Voice:** Piper TTS 1.8 (local, open source), `en_US-ryan-high`, 22.05 kHz. No cloud calls and no API keys.
- **Voice QA:** `tests/voice_qa.py` runs faster-whisper base.en locally and transcribes 12 random sentences.
  - Raw WER is 20%, but nearly all of it is spelling and formatting: "AI" for "A.I.", "two" for "2", "Kathy" for "Cathie", "boy" for "Boyd".
  - The real misses are rare proper names, e.g. "Emad Mostaque".
  - Verdict: clearly intelligible, so the audio is the main deliverable. Results are in `data/voice_qa.json`.

## Run

```bash
./run.sh start|restart|stop|status        # server on :4849 (pid in data/server.pid)
.venv/bin/python music.py                 # regenerate stingers/beds
.venv/bin/python build.py --workers 3     # (re)build every supported date; --dates 2026-10-07 for one
python3 export_snapshot.py                # dist/pods-radio-snapshot.html (embeds audio if MP3s < 25 MB; --link to force linking)
./refresh_screenshots.sh                  # or: node --experimental-websocket tests/shot.mjs <url> <out.png> …
tests/run.sh                              # 14 unit tests + 31-check CDP smoke test
```

Player URL flags: `?ep=YYYY-MM-DD`, `?t=<sec>`, `?tab=notes|script|week|about`, `?autoplay=1`, `?continuous=1` (rolls into the next episode), `?kiosk=1`, `?still=1`, `?burn=1`, and `?empty=1` (shows the honest empty state).
Keys: space for play/pause, ←/→ to skip 15 s, `[` `]` for chapters, `,` `.` for episodes, `s` for speed.

## Gaps and honesty notes

- **Dates:** Oct 1–7 only. A date is supported when all four YouTube channels cover the full window. Moonshots' snapshot chain starts Sep 29 4:04 PM ET, so earlier dates aren't provable.
  - The Oct 7 window ends 7:00 AM, but the feeds were fetched at 6:48 AM, so its last 12 minutes aren't covered. Within the 30-minute tolerance, this is disclosed in the About tab.
- **Podcast RSS** (Moonshots and Bill Simmons) ends Oct 6, 6:49 AM ET. Later audio-only episodes are flagged on air, not guessed.
  - All-In and Jesse Michels have no podcast RSS in the Pods sources.
- **Descriptions only:** shorts (especially Bill Simmons') often have no description, so only the title is read.
- View counts are as of the feed snapshot.
- Thumbnails are remote YouTube images, so they're blank when offline.
- The Pods lens is keyword matching, not judgment.
- Pods' `store.db` was not read. Only the feed files and the Pods profile (for channels and the lens) were used, all read-only.
- Nothing is sent or published anywhere. `/feed.xml` is served on localhost only.

## Layout

```
feeds.py script.py music.py build.py server.py export_snapshot.py run.sh screenshot.sh refresh_screenshots.sh
voices/ (Piper models)  music/ (sox-made audio)  data/tts (sentence cache)  data/voice_qa.json
episodes/<date>/{pods-radio-<date>.mp3, episode.json, script.md}  episodes/index.json
web/{index.html, style.css, app.js, fonts/}  dist/pods-radio-snapshot.html  screenshots/*.png  tests/
```


---
## Repo notes
- **Built:** 2026-10-04, by TokenMax (Boyd's Grok Bot) on the Grok Bot box.
- **Run:** `./run.sh` (then open the localhost URL it prints).
- Imported from `/workspace/tokenmax/pods-radio` on Oct 23, 2026. node_modules, virtualenvs, logs and files over 20 MB were left out.
