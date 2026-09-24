# thai-code-video

สกิลสำหรับ AI agent (Claude Code, Codex) ที่ทำให้มัน**ทำคลิปโปรโมทสั้น ๆ เป็น MP4 ได้ด้วยโค้ดล้วน** — ไม่มีฟุตเทจ ไม่มี After Effects วาดทุกเฟรมด้วย canvas เรนเดอร์ผ่าน Chrome แล้ว ffmpeg ต่อเป็นวิดีโอ พร้อมดนตรีที่สังเคราะห์ด้วยโค้ดเช่นกัน

Fork มาจาก [Changroro/code-video](https://github.com/Changroro/code-video) (MIT) แล้ว**จูนมาเพื่อภาษาไทยโดยเฉพาะ**

ตัวอย่างที่ทำจริง: คลิปเล่าปัญหาของโรงงานน้ำแข็งก่อนมีระบบ 41 วินาที ตัวละครพิกเซล 8-bit มีสีหน้า มีเสียง

---

## ทำไมต้อง fork — ของเดิมใช้กับไทยไม่ได้เลย

ไม่ใช่เรื่องฟอนต์ เครื่องยนต์เดิมมีบรรทัดนี้:

```js
const words = s.split(' ')
```

**ภาษาไทยไม่เว้นวรรคระหว่างคำ** ประโยคทั้งประโยคเลยกลายเป็น "คำเดียว" เอฟเฟกต์ตัวอักษรเด้งทีละคำ — ซึ่งเป็นลายเซ็นของเครื่องยนต์นี้ — จึงพังสนิท

| เดิม | fork นี้ |
|---|---|
| `split(' ')` → ประโยคไทยได้ 1 ชิ้น | `Intl.Segmenter('th')` → ตัดคำได้จริง ใช้ ICU ที่มีใน Chrome อยู่แล้ว ไม่ต้องขนพจนานุกรม |
| พิมพ์ดีดแยกตาม code point → `"น้ำ"` = 3 ตัว สระลอยหนึ่งเฟรม | แยกตามพยางค์ (grapheme) → `"น้ำ"` = 1 |
| ระยะห่างตามผลตัดคำ → `โรงงาน น้ำ แข็ง` อ่านเหมือนสะกดผิด | ช่องว่างตามที่ผู้เขียนเว้นเท่านั้น |
| ฟอนต์เกาหลี (Pretendard, Galmuri) | Kanit · IBM Plex Sans Thai · Charmonman · Noto Thai ทั้งหมด OFL |
| loudnorm รอบเดียว พลาดเป้าถ้ามีช่วงเงียบ | วัดก่อนแล้วปรับ ได้ −14 LUFS จากไฟล์จริง |
| ตัวละครหน้าเดียวทั้งเรื่อง | `face()` — กังวล · ตกใจ · เหนื่อย · โล่งใจ |

รายละเอียดทุกข้อและเหตุผลอยู่ใน [`references/thai.md`](references/thai.md)

---

## ติดตั้ง

ต้องมี: `node` · `ffmpeg` (ที่มี libx264) · Google Chrome · `uv`

```bash
# Claude Code
git clone https://github.com/Useless007/thai-code-video ~/.agents/skills/thai-code-video
ln -s ~/.agents/skills/thai-code-video ~/.claude/skills/thai-code-video

# Codex ใช้ ~/.agents/skills อยู่แล้ว ไม่ต้อง symlink
```

โหลดฟอนต์ไทยครั้งเดียว (ไม่ได้อยู่ใน repo เพราะเป็นไบนารี):

```bash
cd ~/.agents/skills/thai-code-video
bash scripts/fetch_fonts.sh assets/fonts
```

---

## ใช้ยังไง

บอก agent ว่า *"ทำคลิปโปรโมท…"* หรือเรียกสกิลตรง ๆ มันจะถามลุคกับรูปแบบเรื่อง แล้วเสนอ storyboard ให้ดูก่อนเรนเดอร์

ถ้าจะทำมือ:

```bash
cp -r template/ งานของฉัน/ && cd งานของฉัน
cp -r ../assets .            # ฟอนต์
npm install
# แก้ main.js เขียนฉาก · แก้ audio.json วางเสียง
node render.mjs stills 3 9 15         # ดูภาพนิ่งก่อน ห้ามข้าม
uv run --with numpy --with scipy python ../scripts/audio.py audio.json audio.wav
node render.mjs video                 # ได้ video.mp4
```

**ตรวจภาพนิ่งทุกฉากก่อนเรนเดอร์เต็มเสมอ** บั๊กภาษาไทย (คำติดกันผิด สระลอย คิ้วผิดอารมณ์) เห็นได้จากภาพเท่านั้น อ่านโค้ดไม่ออก

---

## สิ่งที่ยังทำไม่ได้ และจะไม่แกล้งทำเป็นว่าทำได้

**ไม่มีฟอนต์ pixel ภาษาไทยที่รองรับวรรณยุกต์** — สระซ้อนต้องการที่แนวตั้งที่ช่อง 8×8 ไม่มีให้ ลุค arcade / terminal / thermal จึงตั้งข้อความไทยด้วย Kanit และเก็บฟอนต์ pixel ไว้ใช้กับตัวละตินและตัวเลขเท่านั้น

ถ้าอยากได้คลิปไทยที่เป็น pixel ล้วน คำตอบที่ซื่อสัตย์คือเปลี่ยนลุค ไม่ใช่ส่งภาษาไทยที่พังออกไป

---

## โครงสร้าง

```
SKILL.md              ← agent อ่านไฟล์นี้
template/             ← เครื่องยนต์ (kit.js) + ลุคต่าง ๆ + render.mjs
scripts/              ← audio.py (ดนตรี) · fetch_fonts.sh · contact_sheet.py
references/thai.md    ← ทุกอย่างที่เกี่ยวกับภาษาไทย อ่านก่อนเขียนบท
references/           ← storyboard · looks · formats · kit-api · qa-checklist
```

## สัญญาอนุญาต

MIT — เหมือนต้นทาง เก็บชื่อผู้เขียนเดิมไว้ใน [LICENSE](LICENSE)
