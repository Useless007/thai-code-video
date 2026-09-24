# thai-code-video

An agent skill (Claude Code, Codex) that renders a short promo video as an MP4 **drawn entirely in code** — no footage, no After Effects. Every frame is canvas, rendered through headless Chrome, muxed by ffmpeg, with music synthesized in code too.

A fork of [Changroro/code-video](https://github.com/Changroro/code-video) (MIT), **retuned for Thai**.

The skill itself is written in English so an agent loads it cheaply (measured: the English `SKILL.md` is ~2.8k tokens; the same file in Thai was ~8k). The videos it makes are in Thai.

---

## Why fork — the original could not do Thai at all

Not a font problem. The engine had this line:

```js
const words = s.split(' ')
```

**Thai puts no spaces between words.** A whole sentence came back as one "word", and kinetic type — the effect this engine is built around — simply did not work.

| Original | This fork |
|---|---|
| `split(' ')` → a Thai sentence is 1 piece | `Intl.Segmenter('th')` → real word boundaries, using the ICU already inside Chrome; no dictionary shipped |
| Typewriter splits by code point → `"น้ำ"` is 3, a vowel mark floats for a frame | Splits by grapheme → `"น้ำ"` is 1 |
| Layout spacing follows segmentation → `โรงงาน น้ำ แข็ง` reads as a spelling mistake | Spaces appear only where the writer typed one |
| Korean fonts (Pretendard, Galmuri) | Kanit · IBM Plex Sans Thai · Charmonman · Noto Thai — all OFL |
| Single-pass `loudnorm`, overshoots on quiet stretches | Measure first, then normalize; −14 LUFS verified from the final file |
| One face per character for the whole story | `face()` — worried · shocked · tired · relieved |

Every change and the reasoning behind it is in [`references/thai.md`](references/thai.md).

---

## Install

Requires `node`, `ffmpeg` (with libx264), Google Chrome, and `uv`.

```bash
# Claude Code
git clone https://github.com/Useless007/thai-code-video ~/.agents/skills/thai-code-video
ln -s ~/.agents/skills/thai-code-video ~/.claude/skills/thai-code-video

# Codex already reads ~/.agents/skills — no symlink needed
```

Fetch the Thai fonts once (binaries are not in the repo):

```bash
cd ~/.agents/skills/thai-code-video
bash scripts/fetch_fonts.sh assets/fonts
```

---

## Use

Tell the agent *"make a promo video…"* or invoke the skill. It asks for a look and a story format, then shows a storyboard before rendering.

By hand:

```bash
cp -r template/ my-video/ && cd my-video
cp -r ../assets .            # fonts
npm install
# edit main.js (scenes) and audio.json (cues)
node render.mjs stills 3 9 15         # look at stills first — never skip this
uv run --with numpy --with scipy python ../scripts/audio.py audio.json audio.wav
node render.mjs video                 # → video.mp4
```

**Always inspect stills of every scene before the full render.** Thai bugs — words fused wrongly, a floating vowel mark, a brow that reads angry instead of worried — are visible only on a rendered frame, never in code.

---

## What this fork cannot do, and will not pretend to

**There is no OFL Thai pixel font with tone-mark coverage.** Stacked marks need vertical room an 8×8 cell does not have. The arcade / terminal / thermal looks therefore set Thai in Kanit and keep the pixel face for Latin and numerals only.

If a Thai clip must be wholly pixel, the honest answer is a different look, not broken Thai.

---

## Layout

```
SKILL.md              ← the agent reads this
template/             ← engine (kit.js), look modules, render.mjs
scripts/              ← audio.py (music), fetch_fonts.sh, contact_sheet.py
references/thai.md    ← everything Thai-specific; read before writing a storyboard
references/           ← storyboard · looks · formats · kit-api · qa-checklist
```

## License

MIT, same as upstream. The original author's copyright is kept in [LICENSE](LICENSE).
