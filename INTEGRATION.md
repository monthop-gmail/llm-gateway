# ต่อโปรเจกต์เข้ากับ LLM Gateway — ใครรับผิดชอบอะไร

เอกสารนี้มีไว้เพราะตอนนี้มีหลายโปรเจกต์มาใช้ gateway เดียวกัน
(botforge v1/v2 ที่มีทั้ง opencode, hermes และ engine อื่น) แล้วเริ่มเห็นปัญหา
ที่ต่างคนต่างทำ

## ปัญหาที่เกิดขึ้นจริงแล้ว

**1. ข้อมูลไม่ไหลกลับ** — โปรเจกต์ hermes ทดสอบเจอเมื่อ 2026-08-25 ว่า
`nim/minimax-m3` เรียก tool ได้ แต่ README ของ gateway ยังเขียนว่า "ใส่ tools แล้ว 404"
อยู่จนถึง 2026-08-26 ที่เขามาทัก — คนอื่นที่อ่าน README ระหว่างนั้นก็เข้าใจผิดตาม

**2. ข้อมูลผิดไหลออก** — `gq/compound` เคยถูกบันทึกว่ารองรับ tool calling ทั้งที่
Groq ตอบตรงๆ ว่า `tool calling is not supported with this model` ถ้าใครเอาไป
ทำ agent ก็พังโดยไม่รู้สาเหตุ

**3. เผาโควต้าร่วมกัน** — ทุกโปรเจกต์ยิงผ่าน API key ชุดเดียวกัน
การที่ต่างคนต่างยิงทดสอบโมเดลเดิมซ้ำ ๆ ทำให้ชนเพดานเร็วขึ้นโดยไม่จำเป็น
(Cloudflare 10,000 neurons/วัน และ OpenRouter ตันมาแล้วจากการ benchmark)

## กติกา

### gateway เป็นแหล่งความจริงเรื่องความสามารถของโมเดล

อะไรที่เป็น "โมเดลตัวนี้ทำอะไรได้ / เร็วแค่ไหน / โควต้าเท่าไหร่"
ให้ถือว่า **`litellm/config.yaml` ของ repo นี้เป็นต้นทาง** ไม่ใช่ README ของโปรเจกต์ตัวเอง

ดึงไปใช้ได้ 2 ทาง — ไม่ต้อง hardcode รายชื่อโมเดลไว้ในโปรเจกต์:

```bash
# คน
./scripts/pick-model.sh coding      # thai | web | fast | no-key | quality | long
./scripts/pick-model.sh <คำค้น>

# เครื่อง
curl -s $GATEWAY/model/info -H "Authorization: Bearer $KEY" \
  | jq '.data[] | select(.model_info.tags[]? == "coding-best")'
```

field ที่มีให้: `description` `tags` `benchmark_coding` `benchmark_seconds`
`latency_ms` `supports_function_calling` `provider_label` `provider_quota`
`context_window` `verified_by`

> ⚠️ `/v1/models` คืนแค่ `id` เพราะเป็นสเปคของ OpenAI — ต้องเรียก `/model/info` แยก

### อยากใช้โมเดลที่ยังไม่มีใน gateway

**มาบอกเรา** — เปิด issue ที่ repo นี้ บอกว่าอยากได้โมเดลอะไร ใช้ทำอะไร
เราจะทดสอบ (chat / tool calling / โควต้า) แล้วเพิ่มให้พร้อม `model_info`

ที่ไม่อยากให้ทำคือไปเรียก provider ตรงจากโปรเจกต์ตัวเอง เพราะ
key จะกระจายหลายที่ และผลทดสอบจะไม่มีใครเห็นนอกจากคนทำ

### ทดสอบเองแล้ว — ส่ง PR กลับมาด้วย

ถ้าโปรเจกต์มีเกณฑ์เฉพาะที่ gateway วัดให้ไม่ได้ (เช่น hermes ต้องการ
prompt 14K tokens + tool loop 2 รอบ) ทดสอบเองได้เลย **แต่ขอผลกลับมา**
เป็น PR ที่แก้ `model_info` ของโมเดลนั้น:

```yaml
  - model_name: nim/minimax-m3
    litellm_params:
      model: nvidia_nim/minimaxai/minimax-m3
      api_key: os.environ/NVIDIA_NIM_API_KEY
    model_info:
      supports_function_calling: true
      description: "... — ผ่าน tool calling และ prompt 14K"
      verified_by: "hermes 2026-08-25"
```

`verified_by` บอกว่าใครยืนยัน เมื่อไหร่ — เวลาข้อมูลขัดกันจะได้รู้ว่าอันไหนใหม่กว่า
และรู้ว่าไปถามใครต่อได้

### ⚠️ ห้ามใส่ API key ลงใน PR หรือ issue

`.env` อยู่ใน `.gitignore` และ CI มี job สแกนหา token ที่หลุด
ถ้าจะยกตัวอย่างให้ใช้ `sk-...` หรือชื่อ env var แทนค่าจริงเสมอ

## gateway วัดอะไรให้ไม่ได้ — ตรงนี้ต้องพึ่งโปรเจกต์ปลายทาง

เครื่องมือของ gateway (`verify-capabilities.py`, `bench-coding.py`, `health-check.py`)
**ยิง API ตรงด้วย prompt สั้น ๆ** จึงเห็นได้แค่บางอย่าง มีคุณสมบัติที่โผล่เฉพาะตอนรัน
ในบริบทจริงของ agent ซึ่งเครื่องมือพวกนี้มองไม่เห็นเลย

### ตัวอย่างจริง — language drift

`oc/gpt-oss-120b` ผ่าน `verify-capabilities.py` แบบสบาย ๆ แต่ hermes เจอว่า:

```
ยิง API ตรง 2 turn        → ตอบไทย 100%
รันใน agent loop จริง      → ตอบภาษาจีน 2 ใน 3 ครั้ง (ผู้ใช้พิมพ์ไทย)
```

สาเหตุอยู่ที่**บริบท** ไม่ใช่ตัวโมเดล — ใน hermes มี system prompt อังกฤษ 15 KB
บวกผล tool ที่เป็นอังกฤษล้วน โมเดลเลย "ไหล" ไปตอบภาษาอื่น
prompt สั้น ๆ ของ `verify-capabilities.py` ไม่มีบริบทแบบนั้นจึงไม่มีทางเห็น

### สิ่งที่ gateway วัดได้ / วัดไม่ได้

| วัดได้ (gateway ทำให้) | วัดไม่ได้ (ต้องทดสอบในบริบทจริง) |
|---|---|
| ยิงติดไหม / ตายหรือยัง | อยู่กับภาษาที่ผู้ใช้ใช้ตลอด session ไหม |
| คืน `tool_calls` เป็น field จริงไหม | tool loop หลายรอบยังคุมทิศทางได้ไหม |
| เขียนโค้ดโจทย์มาตรฐานได้ไหม | รับ prompt ใหญ่ระดับที่โปรเจกต์ใช้จริงไหม |
| latency ของ call เดี่ยว | latency ต่อ turn จริง (หลาย call + context สะสม) |
| โควต้าที่ provider ประกาศ | โควต้าพอสำหรับ workload จริงไหม |

> **ถ้าเจออะไรในคอลัมน์ขวา ส่ง PR กลับมาใส่ `description` + `verified_by`**
> ไม่ต้องแก้ `supports_function_calling` ถ้าข้อนั้นยังจริง — อย่างกรณี
> `oc/gpt-oss-120b` ที่ยังเรียก tool ได้จริง แค่เพิ่มคำเตือนเรื่องภาษา

### อย่าเชื่อตัวเลขในเอกสารโดยไม่ดูวันที่

`INTEGRATION.md` เคยเขียนว่า hermes กิน "~35-40K tokens/turn" ซึ่งยกมาจาก
`MODEL-PROBE.md` — แต่นั่นเป็นตัวเลข**ก่อน**ที่ hermes จะตัด skills 71→4
และ toolsets 27→14 พอวัดใหม่จาก log จริง 78 call ได้พื้น 13K/call
และ 26–60K/turn ต่างกันมากพอที่จะกรองโมเดลผิดตัว

ตัวเลขที่อ้างอิงข้ามโปรเจกต์ควรมีวันที่กำกับเสมอ และเมื่อโปรเจกต์ต้นทางเปลี่ยน
สถาปัตยกรรม ให้ถือว่าตัวเลขเก่าใช้ไม่ได้จนกว่าจะวัดใหม่

## เครื่องมือที่มีให้ใช้

| script | ทำอะไร | ควรรันเมื่อไหร่ |
|---|---|---|
| `scripts/pick-model.sh` | เลือกโมเดลตามงาน | ก่อนตัดสินใจใช้โมเดล |
| `scripts/health-check.py` | หาโมเดลที่ตายแล้ว แยกจากโควต้าหมด | เจอ error แปลก ๆ |
| `scripts/verify-capabilities.py` | ตรวจ tool calling ซ้ำเทียบกับ config — **ยิง API ตรง เห็นได้แค่บางอย่าง** | เดือนละครั้ง หรือก่อนเชื่อข้อมูลเก่า |
| `scripts/bench-coding.py` | วัดความสามารถเขียนโค้ด | มีโมเดลใหม่เข้ามา |
| `scripts/gen-key.sh` | ออก virtual key ต่อโปรเจกต์ | ตอนเริ่มต่อ gateway |

### ⏱️ latency ของ call เดี่ยว ≠ latency ต่อ turn

`latency_ms` ใน metadata คือ call เดี่ยวด้วย prompt สั้น — ต่างจากเวลาจริงใน
agent loop มาก เพราะ agent ยิงหลาย call ต่อ turn และ prompt ใหญ่กว่ามาก
วัดจริงเมื่อ 2026-08-26:

| model | `latency_ms` | เวลาจริงต่อ turn ใน hermes |
|---|---|---|
| `mi/ministral-14b` | 512 ms | **18s** |
| `mi/devstral-medium` | 595 ms | **51s** |
| `mi/magistral-medium` | 1,282 ms | **146–227s** |
| `mi/large` | — | **90–180s** |

ต่างกัน 35–180 เท่า และเรียงลำดับไม่ตรงกันด้วย — `mi/magistral-medium` มี
`latency_ms` ดีกว่า `mi/large` แต่ช้ากว่าในสภาพจริง เพราะเป็น reasoning model
ที่ยิ่ง prompt ใหญ่ยิ่งคิดนาน

**ถ้าโปรเจกต์มีเพดานเวลา (เช่น reply token ของ LINE ~60s) ต้องวัดต่อ turn เอง**
`latency_ms` ใช้เรียงลำดับคร่าว ๆ ได้ แต่ตัดสินใจไม่ได้

## ออก key แยกต่อโปรเจกต์

อย่าใช้ master key ร่วมกัน — ออก virtual key แยกจะได้ดู spend แยกและ revoke
ทีละตัวได้:

```bash
./scripts/gen-key.sh --alias hermes --budget 5
./scripts/gen-key.sh --alias opencode --models cb/gemma-4-31b,mi/large
```

## ข้อมูลที่รู้แล้วว่าโปรเจกต์ไหนต้องการอะไร

| โปรเจกต์ | เกณฑ์ | หมายเหตุ |
|---|---|---|
| **hermes** | tool_calls เป็น field จริง + รับ prompt 14K + สรุป turn 2 ได้ + **อยู่กับภาษาที่ผู้ใช้ใช้ตอนวิ่ง tool loop** + **ตอบทันภายใน ~60s** (reply token ของ LINE) | กิน **26–60K tokens/turn** (พื้น 13K/call · call ถัดไปโตตามบทสนทนา) → กรอง `provider_quota` ด้วยช่วงนี้ ไม่ใช่ตัวเลขเดียว |
| **opencode** | — | ยังไม่ได้บันทึกเกณฑ์ |

> hermes บันทึกผลของตัวเองไว้ที่
> https://github.com/monthop-gmail/hermes-line-bot/blob/main/docs/MODEL-PROBE.md
> ถ้าเกณฑ์เปลี่ยนหรือมีผลใหม่ ส่ง PR มาอัปเดต `model_info` ที่นี่ด้วย
