"""Unit + data tests for Pods Radio. Run: .venv/bin/python -m unittest discover -s tests -v"""
import json, os, re, subprocess, sys, unittest
from datetime import date, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import feeds, script, build  # noqa: E402

DATA = feeds.load()
BY_ID = {i["id"]: i for i in DATA["items"]}
EPDIR = os.path.join(HERE, "episodes")
INDEX = json.load(open(os.path.join(EPDIR, "index.json"))) if os.path.exists(os.path.join(EPDIR, "index.json")) else {"episodes": []}
EPS = {m["date"]: json.load(open(os.path.join(EPDIR, m["date"], "episode.json"))) for m in INDEX["episodes"]}
WORD = re.compile(r"[a-z][a-z']{3,}")
TEMPLATE = set(WORD.findall(open(os.path.join(HERE, "script.py")).read().lower()))
CAL = set("monday tuesday wednesday thursday friday saturday sunday january february march april may june july august september october november december morning afternoon evening tonight overnight".split())


def words(t):
    return set(WORD.findall(script.say(t).lower().replace("’", "'")))


class Feeds(unittest.TestCase):
    def test_loads_items_from_all_channels(self):
        chans = {i["channel"] for i in DATA["items"]}
        self.assertEqual(chans, {"allin", "moon", "jesse", "bill"})
        self.assertGreater(len(DATA["items"]), 100)

    def test_items_are_timezone_aware_and_linked(self):
        for i in DATA["items"]:
            self.assertIsNotNone(i["published"].tzinfo, i["id"])
            self.assertTrue(i["link"].startswith("http"), i["id"])

    def test_supported_dates_need_full_youtube_coverage(self):
        ds = build.supported_dates(DATA)
        self.assertTrue(ds, "no supported dates")
        for d in ds:
            w0, w1 = script.window(d)
            for ch in ("allin", "moon", "jesse", "bill"):
                c = DATA["coverage"][f"{ch}:atom"]
                self.assertLessEqual(c["start"], w0, (d, ch))
                self.assertGreaterEqual(c["end"] + timedelta(minutes=30), w1, (d, ch))  # feeds are fetched ~6:48 AM, just before the 7 AM brief


class Text(unittest.TestCase):
    def test_clean_desc_drops_sponsors_links_and_credits(self):
        desc = "Big news on rockets.\nHost: Somebody\n(0:00) Intro\n(1:05) Starship flight\nFollow us on X\nhttps://example.com/x\nThanks to our partners for making this happen!\nBuy stuff at shop."
        sents, chapters = script.clean_desc(desc)
        self.assertEqual(sents, ["Big news on rockets."])
        self.assertEqual(chapters, ["Starship flight"])

    def test_clean_desc_keeps_initials_together(self):
        sents, _ = script.clean_desc("Peter H. Diamandis talks with Dr. Who. Then the U.S. economy.")
        self.assertEqual(sents[0], "Peter H. Diamandis talks with Dr. Who.")

    def test_say_normalizes_for_tts(self):
        self.assertEqual(script.say("AI & robots"), "A.I. and robots")
        self.assertIn("670 million dollar", script.say("a $670M deal"))
        self.assertIn("episode 299", script.say("EP #299"))
        self.assertIn("Breaking", script.say("BREAKING news"))
        self.assertIn("NFL", script.say("NFL picks"))
        self.assertNotIn("http", script.say("see https://x.com/y now"))


@unittest.skipUnless(EPS, "episodes not built")
class Episodes(unittest.TestCase):
    def test_one_episode_per_supported_date(self):
        self.assertEqual(sorted(EPS), sorted(d.isoformat() for d in build.supported_dates(DATA)))

    def test_duration_between_5_and_8_minutes(self):
        for d, e in EPS.items():
            self.assertGreaterEqual(e["duration"], 300, d)
            self.assertLessEqual(e["duration"], 480, d)

    def test_mp3_matches_metadata(self):
        for d, e in EPS.items():
            p = os.path.join(EPDIR, d, e["audio"])
            self.assertTrue(os.path.exists(p), p)
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout
            self.assertAlmostEqual(float(out), e["duration"], delta=0.6, msg=d)

    def test_chapters_and_captions_are_ordered_and_in_range(self):
        for d, e in EPS.items():
            starts = [c["start"] for c in e["chapters"]]
            self.assertEqual(starts, sorted(starts), d)
            self.assertEqual(e["chapters"][0]["id"], "open")
            self.assertEqual(e["chapters"][-1]["id"], "outro")
            for c in e["captions"]:
                self.assertLessEqual(c["t"] + c["d"], e["duration"] + .01, d)
            self.assertEqual(len(e["peaks"]), len(e["rms"]))

    def test_every_note_is_a_real_feed_item_in_the_window(self):
        for d, e in EPS.items():
            w0, w1 = script.window(date.fromisoformat(d))
            for n in e["notes"]:
                src = BY_ID.get(n["id"])
                self.assertIsNotNone(src, (d, n["id"]))
                self.assertEqual(n["title"], src["title"])
                self.assertEqual(n["link"], src["link"])
                self.assertTrue(w0 <= src["published"] < w1, (d, n["title"]))

    def test_every_reference_resolves_to_a_note_or_week_item(self):
        for d, e in EPS.items():
            known = {n["id"] for n in e["notes"]} | {n["id"] for n in e["weekNotes"]}
            for c in e["captions"]:
                for r in c["refs"]:
                    self.assertIn(r, BY_ID, (d, r))
                    self.assertIn(r, known, (d, r, c["text"]))

    def test_script_never_invents(self):
        """Every content word spoken must come from the referenced feed items, the script templates, or the calendar."""
        for d, e in EPS.items():
            day_items = set()
            for n in e["notes"] + e["weekNotes"]:
                s = BY_ID[n["id"]]
                day_items |= words(s["title"] + " " + (s["desc"] or ""))
            for c in e["captions"]:
                if c["refs"]:
                    pool = set()
                    for r in c["refs"]:
                        pool |= words(BY_ID[r]["title"] + " " + (BY_ID[r]["desc"] or ""))
                else:
                    pool = day_items
                pool |= TEMPLATE | CAL | words(" ".join(ch["spoken"] if "spoken" in ch else ch["name"] for ch in feeds.CHANNELS))
                spoken = words(c["text"])
                unknown = {w for w in spoken if w not in pool and w.rstrip("s") not in pool and w + "s" not in pool}
                self.assertFalse(unknown, f"{d}: {c['text']!r} has words not in the feeds: {unknown}")

    def test_quiet_channels_are_reported_not_filled(self):
        for d, e in EPS.items():
            for ch in e["chapters"]:
                if ch["id"] in ("allin", "moon", "jesse", "bill") and not ch["items"]:
                    self.assertTrue(ch["quiet"], (d, ch["id"]))


if __name__ == "__main__":
    unittest.main()
