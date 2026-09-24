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

## เสียง: วัดก่อน แล้วค่อยปรับ

ของเดิมยิง `loudnorm` รอบเดียวแบบ dynamic ซึ่งเดาค่าจากสิ่งที่ได้ยินระหว่างทาง
แล้วพลาดเป้าเมื่อคลิปมีช่วงเงียบยาว — ในคลิปแรกของโรงงานมีช่วงหยุดตรงคำว่า
"โดยไม่มีใครรู้" และเสียงตรงนั้นทำให้ทั้งไฟล์ดังเกินเป้า

ตอนนี้วัดด้วย `print_format=json` ก่อน แล้วส่งค่าที่วัดได้กลับเข้าไปรอบสอง
(`measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh`, `offset`)
พร้อม `alimiter` กันยอดแหลม

ผลที่วัดจากไฟล์ MP4 สุดท้าย ไม่ใช่จากตอนสังเคราะห์: −14.0 LUFS, true peak −1.8 dBFS

**และนี่คือบทเรียนที่ใหญ่กว่าเรื่องเสียง** — ตรวจจากไฟล์ที่เข้ารหัสแล้ว ไม่ใช่จากตอนวาด
การดูภาพนิ่งตอนเรนเดอร์พิสูจน์แค่ว่า canvas วาดถูก ไม่ได้พิสูจน์ว่าสิ่งที่คนเปิดดูถูก
ถ้า ffmpeg ทำสีเพี้ยนหรือเฟรมหล่น จะไม่มีทางรู้เลย · ดึงเฟรมกลับมาจาก MP4 แล้วดูอีกรอบ
