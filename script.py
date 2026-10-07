"""Write the Pods Radio script for one date, using ONLY feed titles, dates, descriptions (and feed numbers).

Episode window: 7:00 AM ET the day before → 7:00 AM ET on the episode date (Pods' daily brief time).
Output: list of segments, each {id, chapter, stinger, music, paras:[[{text, refs}]]} plus show notes.
`detail` (0–3) controls how much of each description is read; build.py picks it to land in 5–8 minutes.
"""
import re
from datetime import datetime, timedelta, time as dtime
from feeds import CHANNELS, ET_TZ

LENS = [  # Pods' interest lens (from the Pods bot profile): keyword → label
    (r"\bAI\b|artificial intelligence|superintelligen|\bagents?\b|LLM|Anthropic|OpenAI|Sonnet|Claude|Grok|xAI", "AI and agents"),
    (r"\bElon\b|Musk|Tesla|SpaceX|Starship|Neuralink", "Musk companies"),
    (r"singularity|accelerat|moonshot|exponential", "acceleration"),
    (r"Ravens|Orioles|Chelsea|Terps|Maryland|Lamar", "your teams"),
    (r"\bNFL\b|Week \d|QB|quarterback|Guess the Lines|picks|betting|gambl", "NFL and picks"),
]
DROP_LINE = re.compile(r"(^host:|^hosts?:|^guests?:|^producers?:|^produced by|thanks to our partners|partners? for making|^chapters:?$|^timestamps:?$|follow|subscribe|sponsor|intro music|video credit|referenced in|get access|learn more|"
                       r"apply |download|join |newsletter|^#|instagram|tiktok|linkedin|patreon|merch|promo code|"
                       r"use code|visit |sign up|check out|support the show|brought to you|ad choices|privacy|"
                       r"^-+$|^_+$|\bhttps?://)", re.I)
CHAPTER = re.compile(r"^\(?\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\)?\s*[-–:]?\s*(.+)$")
BORING_CH = re.compile(r"^(intro|intros|bestie intros!?|outro|ad|ads|sponsor|cold open|start)$", re.I)
KEEP_CAPS = {"NASA", "ECNL", "NCBA", "SNL", "NFL", "NBA", "MLB", "UFO", "UFOS", "CEO", "IBM", "MIT", "GDP", "IPO", "UHI", "ASI", "AGI"}
EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200d]")


def clean_desc(desc):
    """→ (prose sentences, chapter topics). Drops links, socials, sponsor reads, hashtags."""
    prose, chapters = [], []
    stop = False
    for raw in (desc or "").replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if re.search(r"thanks to our (partners|sponsors)|today'?s sponsors?|this episode is (sponsored|brought)|^sponsors?:|^partners?:", line, re.I):
            stop = True          # everything after the sponsor marker is ad copy or socials
            continue
        if stop:
            continue
        m = CHAPTER.match(line)
        if m:
            topic = m.group(2).strip(" .")
            if not BORING_CH.match(topic) and not DROP_LINE.search(topic):
                chapters.append(topic)
            continue
        # inline chapter runs "(0:00) Intro (1:08) Lions-Panthers ..." in RSS descriptions
        if re.search(r"\(\d{1,2}:\d{2}", line):
            parts = re.split(r"\(\d{1,2}:\d{2}(?::\d{2})?\)", line)
            head = parts[0].strip()
            for p in parts[1:]:
                p = p.strip(" .")
                if p and not BORING_CH.match(p) and not DROP_LINE.search(p):
                    chapters.append(p)
            line = head
            if not line:
                continue
        if re.search(r"https?://|www\.", line) or DROP_LINE.search(line):
            continue             # promo/link lines are dropped whole
        prose.append(line)
    text = " ".join(prose)
    raw = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“'])", text) if s.strip()]
    sents = []
    for s in raw:   # re-join splits after initials like "Peter H." or "U.S."
        if sents and re.search(r"(\b[A-Z]\.|\bU\.S\.|\bDr\.|\bMr\.|\bMs\.|\bSt\.)$", sents[-1]):
            sents[-1] += " " + s
        else:
            sents.append(s)
    sents = [s for s in sents if len(s) > 3 and not DROP_LINE.search(s) and not re.match(r"^(thanks|sponsor|ad)\b", s, re.I)]
    return sents, chapters


def say(text):
    """Normalize text for TTS (keeps meaning; feed text only)."""
    t = EMOJI.sub("", text)
    t = re.sub(r"https?://\S+", "", t)
    t = t.replace("&", " and ").replace("|", ", ").replace("w/", "with ").replace("…", "...").replace("—", ", ").replace("–", ", ")
    t = re.sub(r"\bEP\s*#?\s*(\d+)", r"episode \1", t, flags=re.I)
    t = re.sub(r"\bP\(Doom\)", "P of doom", t, flags=re.I)
    t = re.sub(r"\b[A-Z]{4,}\b", lambda m: m.group(0) if m.group(0) in KEEP_CAPS else m.group(0).capitalize(), t)
    t = re.sub(r"#(\d+)", r"number \1", t)
    unit = lambda rest: "dollar" if re.match(r"\s+[A-Za-z]", rest) else "dollars"
    t = re.sub(r"\$(\d+(?:\.\d+)?)\s*([KMB])\b(?=(.{0,3}))", lambda m: f"{m.group(1)} {dict(K='thousand', M='million', B='billion')[m.group(2)]} {unit(m.group(3))}", t)
    t = re.sub(r"\$(\d[\d,]*(?:\.\d+)?)\s+(million|billion|trillion)\b(?=(.{0,3}))", lambda m: f"{m.group(1)} {m.group(2)} {unit(m.group(3))}", t)
    t = re.sub(r"\b1¢", "1 cent", t)
    t = re.sub(r"(\d+)¢", r"\1 cents", t).replace("/L", " per liter")
    t = re.sub(r"\bYrs\b", "years", t)
    t = re.sub(r"\b(\d+)x\b", r"\1 times", t)
    t = re.sub(r"\bvs\.?\s", "versus ", t)
    t = re.sub(r"\bU\.S\.", "U S", t)
    t = re.sub(r"\bDAL’s\b|\bDAL's\b", "Dallas's", t)
    t = re.sub(r"\bAI\b", "A.I.", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace(" ,", ",")
    return t


def end(t):
    t = t.strip()
    return t if t[-1:] in ".?!" else t.rstrip(".,;:") + "."


def cap(t):
    return t[:1].upper() + t[1:]


def similar(a, b):
    wa = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", a)}
    wb = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", b)}
    return len(wa & wb) >= 3


def words(n, sents, cap_words):
    out, w = [], 0
    for s in sents:
        sw = len(s.split())
        if out and w + sw > cap_words:
            break
        out.append(s); w += sw
        if len(out) >= n:
            break
    return out


def when(dt, ref_date):
    d = dt.astimezone(ET_TZ)
    day = "this morning" if d.date() == ref_date and d.hour < 12 else ("yesterday" if d.date() == ref_date - timedelta(days=1) else d.strftime("%A"))
    h = d.hour % 12 or 12
    part = "morning" if d.hour < 12 else "afternoon" if d.hour < 17 else "evening"
    if day == "this morning":
        return f"at {h} this morning" if d.minute < 10 else f"at {h}:{d.minute:02d} this morning"
    return f"{day} {part}"


def hm(secs):
    h, m = divmod(round(secs / 60), 60)
    if h and m:
        return f"{h} hour{'s' if h > 1 else ''} {m} minutes"
    return f"{h} hour{'s' if h > 1 else ''}" if h else f"{m} minutes"


def window(date):
    end = datetime.combine(date, dtime(7), ET_TZ)
    return end - timedelta(days=1), end


def lens_tags(item):
    hay = item["title"] + " " + (item["desc"] or "")[:600]
    return sorted({lab for pat, lab in LENS if re.search(pat, hay)})


def build(date, data, detail=1):
    cov = data.get("coverage", {})
    start, end_ = window(date)
    ch_by = {c["key"]: c for c in CHANNELS}
    new = [i for i in data["items"] if start <= i["published"] < end_]
    yt = [i for i in new if i["src"] == "youtube"]
    pods = [i for i in new if i["src"] == "podcast"]
    nice = date.strftime("%A, %B ") + str(date.day)
    segs = []

    def P(*sents):
        return [{"text": say(t), "refs": r} for t, r in sents if t]

    # ---- cold open
    top = sorted([i for i in yt if i["kind"] == "video"] + pods, key=lambda i: (i["kind"] != "video", -(len(i["desc"] or ""))))
    jesse = [i for i in yt if i["channel"] == "jesse"]          # Pods: "always brief Jesse when he posts"
    lensy = sorted([i for i in yt if lens_tags(i)], key=lambda i: -(i["views"] or 0))
    headline = (top or jesse or lensy or sorted(yt, key=lambda i: -(i["views"] or 0)) or [None])[0]
    chans = sorted({i["channel"] for i in yt}, key=lambda k: [c["key"] for c in CHANNELS].index(k))
    open_paras = [P((f"Good morning, Boyd. This is Pods Radio for {nice}.", []))]
    if new:
        cnt = f"{len(yt)} new upload{'s' if len(yt) != 1 else ''} on {len(chans)} of your {len(CHANNELS)} watched channels"
        if pods:
            cnt += f", plus {len(pods)} new podcast episode{'s' if len(pods) != 1 else ''}"
        open_paras.append(P((f"Since yesterday's show: {cnt}.", [])))
        if headline:
            open_paras.append(P((f"Leading the show, from {ch_by[headline['channel']]['spoken']}: {end(headline['title'])}", [headline["id"]])))
    else:
        open_paras.append(P(("It was a quiet day on the feeds: nothing new since yesterday's show.", [])))
    segs.append({"id": "open", "chapter": "Cold open", "stinger": None, "music": "open", "paras": open_paras, "items": [headline["id"]] if headline else []})

    # ---- one segment per channel (Pods' priority order)
    for c in CHANNELS:
        items = [i for i in yt if i["channel"] == c["key"]]
        audio = [i for i in pods if i["channel"] == c["key"]]
        rc = cov.get(f"{c['key']}:rss")
        stale_rss = rc and rc["end"] < end_
        if not items and not audio:
            extra = [P((f"Its podcast feed was last checked {when(rc['end'], date)}.", []))] if stale_rss else []
            segs.append({"id": c["key"], "chapter": c["name"], "stinger": c["key"], "music": None, "quiet": True,
                         "paras": [P((f"{cap(c['spoken'])}: nothing new since yesterday's show.", []))] + extra, "items": []})
            continue
        paras = []
        vids = [i for i in items if i["kind"] == "video"]
        shorts = [i for i in items if i["kind"] == "short"]
        bits = []
        if vids:
            bits.append(f"{len(vids)} full episode{'s' if len(vids) > 1 else ''}")
        if shorts:
            bits.append(f"{len(shorts)} short{'s' if len(shorts) > 1 else ''}")
        if audio:
            bits.append(f"{len(audio)} podcast episode{'s' if len(audio) > 1 else ''}")
        paras.append(P((f"{cap(c['spoken'])}. New today: {' and '.join(bits)}.", [])))
        for v in vids:
            sents, chapters = clean_desc(v["desc"])
            p = [(f"The full episode, posted {when(v['published'], date)}: {end(v['title'])}", [v["id"]])]
            for s in words(1 + detail, sents, 30 + 18 * detail):
                p.append((s, [v["id"]]))
            if chapters:
                k = min(len(chapters), 2 + detail)
                ch = [x.rstrip(".") for x in chapters[:k]]
                p.append((("The chapters run through " + (", ".join(ch[:-1]) + ", and " + ch[-1] if len(ch) > 1 else ch[0]) + "."), [v["id"]]))
            paras.append(P(*p))
        for a in audio:
            sents, chapters = clean_desc(a["desc"])
            p = [(f"In the podcast feed: {a['title']}" + (f", running {hm(a['duration'])}." if a.get("duration") else "."), [a["id"]])]
            for s in words(1 + detail, sents, 26 + 16 * detail):
                p.append((s, [a["id"]]))
            if chapters and detail >= 1:
                ch = [x.rstrip(".") for x in chapters[:1 + detail]]
                p.append(("Segments include " + (", ".join(ch[:-1]) + ", and " + ch[-1] if len(ch) > 1 else ch[0]) + ".", [a["id"]]))
            paras.append(P(*p))
        if shorts:
            max_read = 4 + 2 * detail
            p = [("On the shorts shelf." if len(shorts) > 1 else "Just one short this time.", [])]
            for s in shorts[:max_read]:
                sents, _ = clean_desc(s["desc"])
                p.append((end(s["title"]), [s["id"]]))
                if detail >= 1 and sents and not similar(sents[0], s["title"]):
                    for x in words(1, sents, 22):
                        p.append((x, [s["id"]]))
            if len(shorts) > max_read:
                p.append((f"Plus {len(shorts) - max_read} more shorts in the show notes.", [x["id"] for x in shorts[max_read:]]))
            paras.append(P(*p))
        rc = cov.get(f"{c['key']}:rss")
        if rc and rc["end"] < end_:
            paras.append(P((f"Note: the podcast feed for this show was last checked {when(rc['end'], date)}, so audio-only episodes after that aren't here yet.", [])))
        segs.append({"id": c["key"], "chapter": c["name"], "stinger": c["key"], "music": None, "paras": paras,
                     "items": [i["id"] for i in vids + audio + shorts]})

    # ---- Pods lens
    tagged = [(i, lens_tags(i)) for i in new]
    tagged = [(i, t) for i, t in tagged if t]
    if tagged:
        labels = {}
        for i, t in tagged:
            for lab in t:
                labels.setdefault(lab, []).append(i)
        p = [("Through your Pods lens, by keywords in the titles and descriptions.", [])]
        for lab, its in sorted(labels.items(), key=lambda kv: -len(kv[1])):
            first = its[0]
            p.append((f"{cap(lab)}: {len(its)} item{'s' if len(its) > 1 else ''}, including {end(first['title'])}", [first["id"]]))
        segs.append({"id": "lens", "chapter": "Through the Pods lens", "stinger": "lens", "music": None, "paras": [P(*p)],
                     "items": [i["id"] for i, _ in tagged]})

    # ---- numbers + the week so far (recap of real earlier items; detail decides length)
    p = []
    seen = [i for i in yt if i["views"]]
    if seen:
        mv = max(seen, key=lambda i: i["views"])
        p.append((f"By the numbers: the most-watched new upload, as of the last feed check, has {mv['views']:,} views. That's {end(mv['title'])}", [mv["id"]]))
    runtime = sum(i["duration"] or 0 for i in pods)
    if runtime:
        p.append((f"New podcast audio today adds up to {hm(runtime)}.", []))
    week = [i for i in data["items"] if start - timedelta(days=6) <= i["published"] < start and (i["kind"] in ("video", "podcast"))]
    week = [i for i in week if i["channel"] in ch_by]
    nweek = [0, 3, 4, 6, 8, 10][min(detail, 5)]
    if week and nweek:
        pick = []
        for i in sorted(week, key=lambda i: i["published"], reverse=True):
            fs = (clean_desc(i["desc"])[0] or [""])[0][:80]
            if not any(similar(i["title"], j["title"]) or (fs and fs == (clean_desc(j["desc"])[0] or [""])[0][:80]) for j in pick):
                pick.append(i)
            if len(pick) >= nweek:
                break
        p.append(("Earlier this week, in case you missed them.", []))
        for i in pick:
            d = i["published"].astimezone(ET_TZ)
            p.append((f"{d.strftime('%A')}, from {ch_by[i['channel']]['spoken']}: {end(i['title'])}", [i["id"]]))
            if detail >= 2:
                for x in words(1 if detail < 4 else 2, clean_desc(i["desc"])[0], 26 if detail < 4 else 44):
                    p.append((x, [i["id"]]))
    if detail >= 3:   # channel check: posting pace over the last 7 days (counts from the feeds)
        q = [("Channel check, over the past seven days.", [])]
        for c in CHANNELS:
            wk = [i for i in data["items"] if i["channel"] == c["key"] and end_ - timedelta(days=7) <= i["published"] < end_]
            v = len([i for i in wk if i["kind"] == "video"]); sh = len([i for i in wk if i["kind"] == "short"]); pc = len([i for i in wk if i["kind"] == "podcast"])
            bits = [f"{v} full episode{'s' if v != 1 else ''}"] if v else []
            if sh: bits.append(f"{sh} short{'s' if sh != 1 else ''}")
            if pc: bits.append(f"{pc} podcast episode{'s' if pc != 1 else ''}")
            q.append((f"{cap(c['spoken'])}: {', '.join(bits) if bits else 'nothing new'}.", []))
        p.extend(q)
    if p:
        segs.append({"id": "week", "chapter": "Numbers and the week so far", "stinger": "week", "music": None, "paras": [P(*p)],
                     "items": [r for s in p for r in s[1]]})

    # ---- outro
    segs.append({"id": "outro", "chapter": "Outro", "stinger": None, "music": "outro", "paras": [P(
        (f"That's Pods Radio for {nice}.", []),
        ("Everything you heard came straight from the feed titles, dates, and descriptions. Nothing was added.", []),
        ("Links for every item are in the show notes. See you tomorrow morning.", []))], "items": []})

    notes = [{"id": i["id"], "channel": i["channel"], "title": i["title"], "kind": i["kind"], "link": i["link"],
              "published": i["published"].isoformat(), "views": i["views"], "duration": i["duration"],
              "thumb": i.get("thumb"), "summary": " ".join(clean_desc(i["desc"])[0][:2])[:400],
              "chapters": clean_desc(i["desc"])[1][:12], "lens": lens_tags(i)} for i in new]
    week_notes = [{"id": i["id"], "channel": i["channel"], "title": i["title"], "kind": i["kind"], "link": i["link"],
                   "published": i["published"].isoformat(), "duration": i["duration"]}
                  for i in data["items"] if any(i["id"] in s.get("items", []) for s in segs if s["id"] == "week")]
    return {"date": date.isoformat(), "title": f"Pods Radio · {nice}", "window": [start.isoformat(), end_.isoformat()],
            "counts": {"youtube": len(yt), "podcast": len(pods), "channels": len(chans),
                       "videos": len([i for i in yt if i["kind"] == "video"]), "shorts": len([i for i in yt if i["kind"] == "short"])},
            "segments": segs, "notes": notes, "weekNotes": week_notes, "detail": detail}


def word_count(ep):
    return sum(len(s["text"].split()) for seg in ep["segments"] for para in seg["paras"] for s in para)


if __name__ == "__main__":
    import sys, feeds
    from datetime import date as D
    data = feeds.load()
    d = D.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2026-10-07")
    for lvl in range(6):
        ep = build(d, data, lvl)
        print(lvl, word_count(ep), "words")
    ep = build(d, data, int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    for seg in ep["segments"]:
        print(f"\n## {seg['chapter']}")
        for para in seg["paras"]:
            print("  " + " ".join(s["text"] for s in para))
