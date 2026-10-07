"""Load every feed snapshot Boyd's Pods bot keeps (read-only) and merge them into one item list.

Sources (never modified):
  /workspace/feed_*.xml                latest YouTube Atom snapshots (15 newest per channel)
  /workspace/pods/*.xml                Pods' earlier snapshots + full podcast RSS feeds
  /workspace/pods-rss/*.xml            Pods' oldest snapshots
Only titles, dates, descriptions, links, durations and view counts are used.
"""
import email.utils, glob, html, os, re, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET_TZ = ZoneInfo("America/New_York")
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/", "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
      "content": "http://purl.org/rss/1.0/modules/content/"}
SOURCES = ["/workspace/pods-rss/*.xml", "/workspace/pods/*.xml", "/workspace/feed_*.xml"]
# channel key, display name, spoken name, Atom title match, podcast RSS title match
CHANNELS = [
    {"key": "allin", "name": "All-In Podcast", "spoken": "the All-In Podcast", "yt": "All-In Podcast", "rss": None},
    {"key": "moon", "name": "Moonshots · Peter H. Diamandis", "spoken": "Moonshots with Peter Diamandis", "yt": "Peter H. Diamandis", "rss": "Moonshots with Peter Diamandis"},
    {"key": "jesse", "name": "Jesse Michels", "spoken": "Jesse Michels", "yt": "Jesse Michels", "rss": None},
    {"key": "bill", "name": "Bill Simmons · The Ringer", "spoken": "Bill Simmons and The Ringer", "yt": "Bill Simmons", "rss": "The Bill Simmons Podcast"},
]


def _aware(d):
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _t(el):
    return (el.text or "").strip() if el is not None else ""


def parse_file(path):
    """Returns (kind, channel_title, items, fetched) for one feed file; never raises on bad XML."""
    try:
        root = ET.parse(path).getroot()
    except Exception as e:  # noqa
        return None, None, [], None
    items = []
    fetched = datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)
    if root.tag.endswith("feed"):
        title = _t(root.find("a:title", NS))
        for e in root.findall("a:entry", NS):
            link = e.find("a:link", NS).get("href")
            stats = e.find("media:group/media:community/media:statistics", NS)
            items.append({
                "id": "yt:" + _t(e.find("yt:videoId", NS)), "src": "youtube",
                "title": html.unescape(_t(e.find("a:title", NS))),
                "published": datetime.fromisoformat(_t(e.find("a:published", NS))),
                "desc": _t(e.find("media:group/media:description", NS)),
                "link": link.replace("/shorts/", "/shorts/"),
                "kind": "short" if "/shorts/" in link else "video",
                "views": int(stats.get("views")) if stats is not None and stats.get("views") else None,
                "thumb": (e.find("media:group/media:thumbnail", NS).get("url") if e.find("media:group/media:thumbnail", NS) is not None else None),
                "duration": None, "file": path,
            })
        return "atom", title, items, fetched
    ch = root.find("channel")
    title = _t(ch.find("title"))
    for it in ch.findall("item"):
        pd = it.find("pubDate")
        if pd is None:
            continue
        dur = _t(it.find("itunes:duration", NS))
        secs = None
        if dur:
            parts = [int(p) for p in dur.split(":") if p.isdigit()]
            secs = 0
            for p in parts:
                secs = secs * 60 + p
        desc = _t(it.find("description")) or _t(it.find("itunes:summary", NS))
        desc = re.sub(r"<[^>]+>", "\n", desc)
        enc = it.find("enclosure")
        items.append({
            "id": "rss:" + (_t(it.find("guid")) or _t(it.find("title"))), "src": "podcast",
            "title": html.unescape(_t(it.find("title"))), "published": _aware(email.utils.parsedate_to_datetime(pd.text)),
            "desc": html.unescape(desc), "link": _t(it.find("link")) or (enc.get("url") if enc is not None else None),
            "kind": "podcast", "views": None, "thumb": None, "duration": secs, "file": path,
        })
    return "rss", title, items, fetched


def load(sources=SOURCES):
    """Merge all snapshots. Later files win for mutable fields (views). Returns dict with items + coverage."""
    by_id, snaps = {}, []
    files = [f for pat in sources for f in sorted(glob.glob(pat))]
    for f in files:
        kind, title, items, fetched = parse_file(f)
        if not kind:
            continue
        ch = next((c for c in CHANNELS if title in (c["yt"], c["rss"])), None)
        if not ch:
            continue
        if items:
            newest = max(i["published"] for i in items)
            oldest = min(i["published"] for i in items)
            snaps.append({"file": f, "kind": kind, "channel": ch["key"], "count": len(items),
                          "oldest": oldest, "newest": newest, "fetched": max(fetched, newest)})
        for i in items:
            i["channel"] = ch["key"]
            prev = by_id.get(i["id"])
            if prev and prev["views"] and not i["views"]:
                i["views"] = prev["views"]
            by_id[i["id"]] = i
    items = sorted(by_id.values(), key=lambda i: i["published"])
    return {"items": items, "snapshots": snaps, "coverage": coverage(snaps)}


def coverage(snaps):
    """Per channel+kind: the continuous window the snapshots prove complete.
    A snapshot (15 newest) proves completeness from its oldest entry up to its fetch time; chains join when they overlap."""
    out = {}
    for key in {(s["channel"], s["kind"]) for s in snaps}:
        ss = sorted([s for s in snaps if (s["channel"], s["kind"]) == key], key=lambda s: s["fetched"])
        start, end = ss[-1]["oldest"], ss[-1]["fetched"]
        gaps = []
        for s in reversed(ss[:-1]):
            if s["fetched"] >= start:          # overlaps the chain → extends it back
                start = min(start, s["oldest"])
            else:
                gaps.append((s["fetched"].isoformat(), start.isoformat()))
                break
        out[f"{key[0]}:{key[1]}"] = {"start": start, "end": end, "gaps": gaps}
    return out


if __name__ == "__main__":
    d = load()
    print(len(d["items"]), "items")
    for k, v in sorted(d["coverage"].items()):
        print(k, v["start"].astimezone(ET_TZ).isoformat(timespec="minutes"), "→", v["end"].astimezone(ET_TZ).isoformat(timespec="minutes"), v["gaps"])
