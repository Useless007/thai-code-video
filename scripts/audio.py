"""Synthesize background music and sound effects from audio.json into audio.wav.

    uv run --with numpy --with scipy python audio.py audio.json audio.wav

audio.json (times in seconds, same clock as the video):
{
  "dur": 30, "bpm": 100, "key": "D", "mode": "major",
  "chords": ["I", "V", "vi", "IV"],               # one chord per bar, looped
  "sections": [[0, 8, 0.3], [8, 26, 0.9], [26, 30, 0.5]],   # [start, end, energy 0..1]
  "song": {"path": "assets/song.mp3", "offset": 0},          # optional: a licensed track replaces the synthesized music
  "cues": [[1.0, "whoosh"], [3.5, "pop", 0.8], [4.0, "chime"]]   # [time, sfx, gain]
}
Energy < 0.35 plays pad only, < 0.7 adds bass and arpeggio, and higher adds drums.

Optional keys (8-bit / NES scoring):
  "arr": "chip"      NES arrangement: triangle tonic below 0.35, then Pulse 1 arpeggio ("arp_duty", default .125)
                     + triangle bass, noise drums from 0.7. Pulse 2 is left to motifs.
  "end": "i"         chord numeral forced on the last bar (either arrangement).
  "motifs": {"id": {"notes": [[semitone|null, beats], ...], "voice": "p12"|"p25"|"p50"|"tri", "octave": 1}}
                     semitones from the key root + 12*octave; null is a rest. Cue "motif:id" plays it.
  Cues may be objects: {"t", "name", "gain": 1, "variant", "midi", "duty", "lp", "transpose", "voice"}.
  Chip SFX: stinger (variant 1 question, 2 dun-dun-DUN, 3 flourish), blip (midi 72, duty .25; per-word voice),
  whistle, bark (midi shifts pitch), knock. Motif cues take voice, lp (Hz, "behind a door"), transpose, gain.
render.mjs muxes audio.wav into the video and normalizes loudness.
"""
import json
import subprocess
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000
NOTES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
         "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
DEGREES = {"i": 0, "ii": 2, "iii": 4, "iv": 5, "v": 7, "vi": 9, "vii": 11}
MINOR_SHIFT = {"iii": -1, "vi": -1, "vii": -1}  # natural minor lowers 3, 6, 7


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def chord_notes(root_midi, numeral, mode):
    """Roman numeral -> MIDI triad. Upper case = major triad, lower case = minor."""
    base = numeral.lower().rstrip("°")
    semis = DEGREES[base] + (MINOR_SHIFT.get(base, 0) if mode == "minor" else 0)
    third = 4 if numeral[0].isupper() else 3
    r = root_midi + semis
    return [r, r + third, r + 7]


def env(n, a=0.005, d=0.3, curve=4.0):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d * curve / 4)


def filt(x, kind, f):
    return sosfilt(butter(2, f, kind, fs=SR, output="sos"), x)


def tone(f, n, harm=(1, .5, .25), detune=0.0):
    t = np.arange(n) / SR
    return sum(a * np.sin(2 * np.pi * f * (k + 1) * t * (1 + detune)) for k, a in enumerate(harm))


def add(buf, x, t, gain=1.0):
    i = int(t * SR)
    if i >= len(buf) or i < 0:
        return
    x = x[: len(buf) - i]
    buf[i:i + len(x)] += x * gain


rng = np.random.default_rng(7)


def noise(n):
    return rng.standard_normal(n)


crng = np.random.default_rng(8)  # chip voices draw here so legacy renders stay bit-identical


def phase(f, n):
    """Running phase 0..1 of a frequency in Hz, scalar or per-sample (for bends)."""
    return np.cumsum(np.broadcast_to(np.asarray(f, float), (n,))) / SR % 1


def blep(p, dt):
    """PolyBLEP residual for a unit rising step at phase 0; tames the pulse's aliasing."""
    dt, y = np.broadcast_to(dt, p.shape), np.zeros_like(p)
    a, b = p < dt, p > 1 - dt
    x = p[a] / dt[a]
    y[a] = x + x - x * x - 1
    x = (p[b] - 1) / dt[b]
    y[b] = x * x + x + x + 1
    return y / 2


def pulse(f, n, duty=.5):
    """NES pulse channel: unipolar 0/1 wave at duty .125/.25/.5, DC removed."""
    p, dt = phase(f, n), np.asarray(f, float) / SR
    return (p < duty) - duty + blep(p, dt) - blep((p - duty) % 1, dt)


def tri(f, n):
    """NES triangle: a 4-bit ramp in 32 steps, 15..0..15."""
    s = np.floor(phase(f, n) * 32)
    return np.where(s < 16, 15 - s, s - 16) / 7.5 - 1


def lfsr(n, rate=SR):
    """NES noise channel: random +-1 held for SR/rate samples (lower rate = crunchier)."""
    h = max(1, round(SR / rate))
    return np.repeat(crng.choice([-1.0, 1.0], n // h + 1), h)[:n]


def fade(x, r=.006):
    """Short linear release so a gated chip note ends without a click."""
    k = min(len(x), int(r * SR))
    x[len(x) - k:] *= np.linspace(1, 0, k)
    return x


DUTY = {"p12": .125, "p25": .25, "p50": .5}


def seq(notes, base, voice, step):
    """[[semitone|None, length], ...] -> mono line on one chip voice; lengths are in units of `step` seconds."""
    out = []
    for s, d in notes:
        x = np.zeros(int(d * step * SR))
        g = int(len(x) * .9)  # articulation gap between notes
        if s is not None and g:
            f = hz(base + s)
            x[:g] = fade(tri(f, g) if voice == "tri" else pulse(f, g, DUTY[voice]) * env(g, .003, max(.15, d * step * 1.5)))
        out.append(x)
    return np.concatenate(out) if out else np.zeros(1)


SFX = {
    "whoosh": lambda: filt(noise(int(.6 * SR)), "bandpass", [400, 4000]) * np.sin(np.linspace(0, np.pi, int(.6 * SR))) ** 2 * .5,
    "pop": lambda: tone(hz(84) * np.exp(-np.arange(int(.12 * SR)) / SR * 18), int(.12 * SR), (1,)) * env(int(.12 * SR), .002, .08),
    "click": lambda: filt(noise(int(.03 * SR)), "highpass", 2500) * env(int(.03 * SR), .001, .01) * .6,
    "chime": lambda: tone(hz(88), int(1.6 * SR), (1, .4, .2, .1)) * env(int(1.6 * SR), .003, 1.2) * .35,
    "ping": lambda: tone(hz(91), int(1.2 * SR), (1, .15)) * env(int(1.2 * SR), .002, .9) * .3,
    "thud": lambda: tone(55 * np.exp(-np.arange(int(.35 * SR)) / SR * 6), int(.35 * SR), (1, .3)) * env(int(.35 * SR), .002, .25),
    "sand": lambda: filt(noise(int(1.5 * SR)), "lowpass", 1800) * np.sin(np.linspace(0, np.pi, int(1.5 * SR))) * .25,
    "wave": lambda: filt(noise(int(3 * SR)), "lowpass", 900) * np.sin(np.linspace(0, np.pi, int(3 * SR))) ** 2 * .3,
    "type": lambda: filt(noise(int(.02 * SR)), "bandpass", [1500, 6000]) * env(int(.02 * SR), .001, .006) * .5,
}


def stinger(c, root):
    """<=2 s chip punctuation, pitched from the key root. variant 1 asks, 2 threatens, 3 resolves."""
    base, v, x = root + 12, c.get("variant", 1), np.zeros(2 * SR)
    if v == 1:  # rising figure left hanging on the leading tone
        add(x, seq([[0, .12], [5, .12], [7, .12], [11, .9]], base, "p25", 1), 0, .85)
    elif v == 2:  # descending minor "dun-dun-DUN", doubled two octaves down, a crunch on the last hit
        add(x, seq([[3, .22], [2, .22], [1, 1.2]], base, "p50", 1), 0, .45)
        add(x, seq([[3, .22], [2, .22], [1, 1.2]], base - 24, "tri", 1), 0, .4)
        add(x, lfsr(int(.6 * SR), 6000) * env(int(.6 * SR), .001, .2), .44, .2)
    else:  # bright major run that lands on the octave
        add(x, seq([[0, .06], [4, .06], [7, .06], [12, .06], [16, .06], [19, .06], [24, .7]], base, "p25", 1), 0, .6)
        add(x, seq([[None, .36], [0, .7]], base - 12, "tri", 1), 0, .35)
    return x


def bark(c, root):
    """Small-dog "wuf": pulse+noise with a fast 700 -> 350 Hz drop, low-passed, over a noise chuff."""
    m = int(.18 * SR)
    f = hz(c.get("midi", 77)) * (.5 + .5 * np.exp(-np.arange(m) / SR / .04))
    body = filt(pulse(f, m, .25) + .4 * crng.standard_normal(m), "lowpass", 2000) * env(m, .004, .07)
    chuff = filt(crng.standard_normal(m), "bandpass", [300, 1400]) * env(m, .001, .025) * .8
    return fade(body + chuff) * .6


def whistle(c, root):
    """Guard's pea whistle: ~2.8 kHz pulse, trilled in pitch and level at 26 Hz."""
    m = int(.6 * SR)
    trill = np.sin(2 * np.pi * 26 * np.arange(m) / SR)
    return fade(pulse(2800 * (1 + .03 * trill), m, .5) * (.7 + .3 * np.sign(trill)) * env(m, .01, 2), .05) * .5


# SFX that read cue parameters; called as f(cue, key_root_midi)
PSFX = {
    "stinger": stinger,
    "blip": lambda c, root: fade(pulse(hz(c.get("midi", 72)), int(.04 * SR), c.get("duty", .25)) * env(int(.04 * SR), .001, .012), .004) * .45,
    "whistle": whistle,
    "bark": bark,
    "knock": lambda c, root: (filt(crng.standard_normal(int(.12 * SR)), "bandpass", [500, 2500]) * env(int(.12 * SR), .001, .015)
                              + tone(190, int(.12 * SR), (1, .4)) * env(int(.12 * SR), .001, .04)) * .35,
}


def motif(spec, c):
    """Cue {"name": "motif:id"} -> the motif line; the cue may override voice and add transpose and lp."""
    mid = c["name"][6:]
    if mid not in spec.get("motifs", {}):
        raise SystemExit(f"unknown motif '{mid}'. Defined: {', '.join(spec.get('motifs', {}))}")
    m = spec["motifs"][mid]
    base = 48 + NOTES[spec.get("key", "C")] + 12 * m.get("octave", 1) + c.get("transpose", 0)
    x = seq(m["notes"], base, c.get("voice", m.get("voice", "p50")), 60 / spec["bpm"]) * .5
    return filt(x, "lowpass", c["lp"]) if "lp" in c else x


def music(spec, n):
    bpm, beat = spec["bpm"], 60 / spec["bpm"]
    bar = beat * 4
    root = 48 + NOTES[spec.get("key", "C")]
    mode = spec.get("mode", "major")
    chords = spec.get("chords", ["I", "V", "vi", "IV"])
    sections = spec.get("sections", [[0, spec["dur"], 0.6]])
    energy = lambda t: next((e for a, b, e in sections if a <= t < b), sections[-1][2])
    bars = int(np.ceil(spec["dur"] / bar))
    chord = lambda k: chord_notes(root, spec["end"] if "end" in spec and k == bars - 1 else chords[k % len(chords)], mode)
    if spec.get("arr") == "chip":
        return chip(spec, n, beat, bars, chord, energy)
    pad, bass, arp, drums = (np.zeros(n) for _ in range(4))
    for k in range(bars):
        t0 = k * bar
        notes = chord(k)
        e = energy(t0)
        m = int(bar * SR)
        for note in notes:  # pad: soft, detuned, whole bar
            add(pad, (tone(hz(note + 12), m, (1, .3), .003) + tone(hz(note + 12), m, (1, .3), -.003)) * env(m, .4, bar * 2), t0, .08)
        if e >= .35:
            for b in range(4):  # bass on every beat, arpeggio on eighths
                add(bass, tone(hz(notes[0] - 12), int(beat * SR), (1, .5, .1)) * env(int(beat * SR), .005, beat * .8), t0 + b * beat, .22)
            for s in range(8):
                note = notes[s % 3] + 24 + (12 if s % 4 == 3 else 0)
                q = int(beat / 2 * SR)
                add(arp, tone(hz(note), q, (1, .45, .2, .1)) * env(q, .002, .18), t0 + s * beat / 2, .09)
        if e >= .7:
            for b in range(4):
                add(drums, SFX["thud"](), t0 + b * beat, .9)
                if b % 2:
                    add(drums, filt(noise(int(.18 * SR)), "bandpass", [900, 5000]) * env(int(.18 * SR), .001, .09), t0 + b * beat, .35)
                for h in range(2):
                    add(drums, filt(noise(int(.05 * SR)), "highpass", 7000) * env(int(.05 * SR), .001, .02), t0 + b * beat + h * beat / 2, .12)
    pad = filt(pad, "lowpass", 2500)
    left = pad + bass + arp * .7 + drums
    right = pad + bass + arp * 1.3 + drums
    return np.stack([left, right], 1)


def chip(spec, n, beat, bars, chord, energy):
    """NES arrangement on the legacy bar clock: triangle, Pulse 1 arpeggio, noise drums. Pulse 2 is for motifs."""
    duty, q, m = spec.get("arp_duty", .125), int(beat / 2 * SR), int(beat * 4 * SR)
    p1, low, drums = (np.zeros(n) for _ in range(3))
    k_t = np.arange(int(.22 * SR)) / SR
    kick = fade(tri(45 + 130 * np.exp(-k_t * 30), len(k_t)) * env(len(k_t), .001, .13))
    snare = lfsr(int(.18 * SR), 12000) * env(int(.18 * SR), .001, .08)
    hat = filt(lfsr(int(.04 * SR)), "highpass", 6000) * env(int(.04 * SR), .001, .012)
    for k in range(bars):
        t0, notes = k * beat * 4, chord(k)
        e = energy(t0)
        if e < .35:  # the tonic ringing: one soft triangle note under the whole bar
            add(low, fade(tri(hz(notes[0] - 12), m) * env(m, .02, beat * 8)), t0, .2)
            continue
        for b in range(4):  # triangle bass on every beat, Pulse 1 arpeggio on eighths
            add(low, fade(tri(hz(notes[0] - 12), int(beat * .85 * SR))), t0 + b * beat, .28)
        for s in range(8):
            add(p1, fade(pulse(hz(notes[s % 3] + 12 + (12 if s % 4 == 3 else 0)), q, duty) * env(q, .002, .15)), t0 + s * beat / 2, .4)
        if e >= .7:
            for b in range(4):
                add(drums, snare if b % 2 else kick, t0 + b * beat, .7 if b % 2 else 1.2)
                for h in range(2):
                    add(drums, hat, t0 + b * beat + h * beat / 2, .2)
    return np.stack([low + p1 * .8 + drums, low + p1 * 1.2 + drums], 1)


def load_song(path, offset, n):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(offset), "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2)[:n]
    if len(x) < n:
        raise SystemExit(f"song is shorter than the video: {len(x) / SR:.1f}s < {n / SR:.1f}s")
    return x.astype(np.float64)


def main(spec_path, out_path):
    spec = json.load(open(spec_path))
    n = int(spec["dur"] * SR)
    song = spec.get("song")
    mix = load_song(song["path"], song.get("offset", 0), n) * song.get("gain", 1.0) if song else music(spec, n)
    fx = np.zeros(n)
    root = 48 + NOTES[spec.get("key", "C")]
    for cue in spec.get("cues", []):
        c = cue if isinstance(cue, dict) else dict(zip(("t", "name", "gain"), cue))
        t, name, gain = c["t"], c["name"], c.get("gain", 1.0)
        if name.startswith("motif:"):
            x = motif(spec, c)
        elif name in PSFX:
            x = PSFX[name](c, root)
        elif name in SFX:
            x = SFX[name]()
        else:
            raise SystemExit(f"unknown sfx '{name}'. Available: {', '.join([*SFX, *PSFX])}, motif:<id>")
        add(fx, x, t, gain)
    mix = mix + fx[:, None] * .8
    mix = np.tanh(mix * 1.2)
    mix *= 0.89 / max(1e-6, np.abs(mix).max())
    wavfile.write(out_path, SR, (mix * 32767).astype(np.int16))
    print(f"{out_path}: {spec['dur']}s, {len(spec.get('cues', []))} cues, {'song' if song else 'synth @ %s bpm' % spec['bpm']}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
