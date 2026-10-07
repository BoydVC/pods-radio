"""Synthesize Pods Radio's music with sox: theme sting, bed, per-segment stingers, outro. All original, all local."""
import os, subprocess, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "music")
SR = "22050"
NOTE = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3, "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}


def hz(n):
    name, octv = n[:-1], int(n[-1])
    return 440.0 * 2 ** ((NOTE[name] + 12 * (octv - 4)) / 12)


def sox(*args):
    subprocess.run(["sox", *map(str, args)], check=True, stderr=subprocess.DEVNULL)


def tone(path, dur, wave, freq, *fx):
    sox("-n", "-r", SR, "-c", "1", path, "synth", dur, wave, f"{freq:.2f}", *fx)


def mix(out, parts, *fx):
    """parts: [(path, delay_s, gain_db)] → mixed mono file."""
    tmp = []
    for i, (p, delay, gain) in enumerate(parts):
        t = out + f".p{i}.wav"
        sox(p, t, "gain", gain, "pad", delay)
        tmp.append(t)
    if len(tmp) == 1:
        sox(tmp[0], out, *fx)
    else:
        sox("-m", *tmp, out, *fx)
    for t in tmp:
        os.remove(t)


def motif(out, notes, step, wave="pluck", ring=1.1, extra=()):
    d = tempfile.mkdtemp()
    parts = []
    for i, n in enumerate(notes):
        p = os.path.join(d, f"n{i}.wav")
        if wave == "pluck":
            tone(p, ring, "pluck", hz(n), "fade", "q", 0.005, ring, ring * 0.8)
        else:
            tone(p, ring, wave, hz(n), "fade", "q", 0.01, ring, ring * 0.85)
        parts.append((p, i * step, -6))
    parts.extend(extra)
    mix(out, parts, "pad", 0, 0.6, "reverb", 45, 50, 70, "gain", "-n", -3)


def build():
    os.makedirs(OUT, exist_ok=True)
    d = tempfile.mkdtemp()
    # bed: soft D-major-7 pad with slow tremolo
    pads = []
    for i, n in enumerate(["D3", "A3", "C#4", "F#4"]):
        p = os.path.join(d, f"pad{i}.wav")
        tone(p, 24, "sine" if i % 2 == 0 else "triangle", hz(n), "tremolo", 0.15 + i * 0.07, 40, "lowpass", 1800)
        pads.append((p, 0, -10))
    mix(os.path.join(OUT, "bed.wav"), pads, "reverb", 60, "fade", "t", 1.5, 24, 2.5, "gain", "-n", -6)
    # boom for the theme
    boom = os.path.join(d, "boom.wav")
    tone(boom, 1.6, "sine", 55, "fade", "q", 0.005, 1.6, 1.5)
    whoosh = os.path.join(d, "whoosh.wav")
    sox("-n", "-r", SR, "-c", "1", whoosh, "synth", 0.9, "pinknoise", "highpass", 1500, "lowpass", 7000,
        "fade", "t", 0.6, 0.9, 0.3, "gain", -16)
    # theme sting (after the cold open) and outro (descending, ringing chord)
    motif(os.path.join(OUT, "theme.wav"), ["D4", "F#4", "A4", "D5", "F#5", "A5"], 0.11, ring=2.6,
          extra=[(boom, 0, -4), (whoosh, 0, -2)] + [(_pad(d, n, 3.4), 0.0, -14) for n in ("D3", "A3", "F#4")])
    motif(os.path.join(OUT, "outro.wav"), ["A5", "F#5", "D5", "A4", "F#4", "D4"], 0.14, ring=3.4,
          extra=[(boom, 0.84, -6)] + [(_pad(d, n, 4.6), 0.2, -14) for n in ("D3", "A3", "C#4", "F#4")])
    # segment stingers: a three-note signature per channel
    stings = {
        "allin": (["D5", "F#5", "A5"], "pluck"),
        "moon": (["A4", "E5", "A5"], "sine"),
        "jesse": (["E4", "G4", "B4"], "triangle"),
        "bill": (["G4", "B4", "D5"], "pluck"),
        "lens": (["C#5", "E5"], "pluck"),
        "week": (["F#4", "A4", "C#5"], "pluck"),
    }
    for k, (notes, wave) in stings.items():
        motif(os.path.join(OUT, f"sting_{k}.wav"), notes, 0.09, wave=wave, ring=0.9, extra=[(whoosh, 0, -6)])
    for f in sorted(os.listdir(OUT)):
        print(f, subprocess.run(["soxi", "-D", os.path.join(OUT, f)], capture_output=True, text=True).stdout.strip())


def _pad(d, n, dur):
    p = os.path.join(d, f"cp_{n}_{dur}.wav")
    if not os.path.exists(p):
        tone(p, dur, "triangle", hz(n), "fade", "q", 0.3, dur, dur * 0.7, "lowpass", 2000)
    return p


if __name__ == "__main__":
    build()
