# Thai, and what it costs

This fork exists because of one line in the original engine:

```js
const words = s.split(' ')
```

Thai does not put spaces between words. That call handed back the whole
sentence as a single element, so the kinetic type — the effect this engine is
built around — arrived as one blob. Nothing about fonts fixes that.

## What the fix is

`Intl.Segmenter` with `granularity: 'word'`, locale `th`. ICU's Thai dictionary
is already inside the renderer, because the renderer is headless Chrome. No
dictionary ships here and none needs to.

Measured on the sentence a promo would actually use:

```
'โรงงานน้ำแข็งสยามอาร์กติก เสียเวลาไปกับกระดาษ'
  split(' ')        -> 2 pieces
  segmentWords()    -> 11 words
```

The same call is correct for Latin, so there is one path rather than a language
flag somebody has to remember to set. `LANG` at the top of `kit.js` is the only
thing to change for another language.

## Segmentation decides order, never spacing

This one only showed up on a rendered frame, and it looked like a spelling
mistake rather than a layout bug.

`kwords` laid each segment out with a uniform gap — correct for English, where
the segments were separated by spaces in the source anyway. In Thai it turned

```
โรงงานน้ำแข็งสยามอาร์กติก  ->  โรงงาน น้ำ แข็ง สยาม อาร์กติก
```

Thai words run together. A gap between them is not emphasis; it is wrong
spelling. Worse, ICU had split a proper noun it does not know — which was
invisible until the layout put the split on screen.

Space now appears where the writer put a space and nowhere else. The segments
still arrive one at a time, which is the whole effect; they just sit flush.

**Rule: use segmentation to decide what animates when. Never to decide where
things sit.**

## The typewriter

`typed()` used `[...s]`, which splits by code point. `'น้ำ'` is three code
points and one syllable; revealing the first of them puts a tone mark on screen
with no consonant under it for a frame. `segmentGraphemes()` splits by
user-perceived character instead.

```
'น้ำ'  [...s] -> 3    segmentGraphemes -> 1
```

## Lines do not wrap, and that is deliberate

The engine never wrapped: `maxW` scales a line down rather than breaking it.
Keep it that way. Thai line breaking is a dictionary problem too, and a wrong
break in Thai does not look like a wrong break in English — it reads as a
different word. Write short lines in the storyboard instead.

## Fonts

Every face here carries Thai and Latin in one file, so a Thai sentence with a
Latin product name in it does not switch typeface mid-line.

| Role | Face |
|---|---|
| Display | Kanit ExtraBold / Bold |
| Body, UI | IBM Plex Sans Thai, Noto Sans Thai |
| Handwriting | Charmonman Bold, Sriracha |
| Serif | Noto Serif Thai |
| Mono | Space Mono — **Latin only** |
| Pixel | Press Start 2P — **Latin and numerals only** |

## The gap this fork cannot close

**There is no OFL Thai bitmap font with tone-mark coverage.** The Korean
original had Galmuri; Thai has no equivalent that renders สระ and วรรณยุกต์
correctly at pixel sizes. Stacked marks need vertical room a 8×8 cell does not
have.

So the arcade, terminal and thermal looks set their Thai in Kanit and keep the
pixel face for Latin and numerals. **Do not set a Thai string in Press Start
2P** — the marks vanish or collide, and it will not be obvious in a still.

If a Thai promo needs to be wholly pixel, the honest answer is to pick a
different look rather than to ship broken Thai.

## What to check before calling a render finished

- Play it at full size and read every Thai line aloud. Marks that collided will
  be obvious in motion and invisible in a contact sheet.
- Check a line that mixes Thai with a Latin name or a number.
- Check the longest line in the storyboard: it scales down rather than wrapping,
  so the failure mode is "too small to read", not "overflows".

## Audio: measure first, then normalize

The original ran `loudnorm` once in dynamic mode, which guesses from what it
hears along the way and overshoots when the clip has a long quiet stretch. The
first factory clip paused on the line "โดยไม่มีใครรู้", and that pause pushed
the whole file past target.

Now it measures with `print_format=json` first, then feeds the measured values
back for a second linear pass (`measured_I`, `measured_TP`, `measured_LRA`,
`measured_thresh`, `offset`) with `alimiter` on the peaks.

Result measured from the final MP4, not from the synth: −14.0 LUFS, true peak
−1.8 dBFS.

**The larger lesson is not about audio.** Check the encoded file, not the canvas.
A still grabbed at render time proves the canvas drew correctly; it says nothing
about what a viewer actually receives. If ffmpeg shifted colours or dropped a
frame you would never know. Pull frames back out of the MP4 and look again.

## Faces on 8-bit characters

A character with one expression for the whole story keeps the viewer at arm's
length. `face(x, y, s, mood)` draws over the eye row of a `PERSON`-style 16-row
sprite: `worried`, `shocked`, `tired`, `relieved`. `sweat(x, y, s, t)` adds a
falling drop for worried/shocked.

The trap that only shows on a rendered frame: a worried brow must have its
**inner end raised**. Inner end lowered is an angry brow, and the two are one
sign flip apart in code.

### The synth is already loud

`audio.py` outputs sit around −13 LUFS with true peak near −1 dBTP and an LRA
of ~1.3. There is almost no headroom, so a *linear* second-pass `loudnorm`
cannot bring true peak down to −2 — it reports success and leaves the peak
where it was. Measured on a real render: −14.16 LUFS / −0.34 dBTP after the
"correct" two-pass.

What works: limit first, then let `loudnorm` run in dynamic mode so it enforces
the ceiling — `alimiter=limit=0.5,loudnorm=I=-14:TP=-2:LRA=9`. Always read the
numbers back from the final MP4; the filter's own log describes what it
intended, not what it delivered.
