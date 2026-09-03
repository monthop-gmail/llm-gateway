# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

เอกสารในโปรเจกต์นี้เป็นภาษาไทย รวมถึงคอมเมนต์ในโค้ดและข้อความ commit — เขียนต่อด้วยภาษาไทย

## กติกาข้อเดียวที่ต้องจำให้ได้ก่อนแตะอะไร

> **ทุกอย่างที่วัดค่า ต้องส่ง `"disable_fallbacks": true` · ทุกอย่างที่อ่านค่า ต้องเช็ค `answered_by`**

LiteLLM มี `fallbacks` ที่สลับไป provider อื่นให้เงียบ ๆ เมื่อตัวหลักพัง ขอ A แล้วได้
คำตอบเสมอ — **แต่คำตอบนั้นอาจมาจาก B** สคริปต์วัดที่ไม่ปิด fallback จึงวัด B แล้ว
บันทึกผลใส่ชื่อ A โดยไม่มี error ไม่มีอะไรฟ้อง

รากเดียวกันนี้ทำให้พลาดมาแล้ว **5 ครั้ง** ใน `probe-context.py` · `probe-latency-14k.py` ·
ตัวกรองใน `pick-model.sh` · `bench-coding.py` · `verify-capabilities.py`
ตอนนี้ `validate.sh` ตรวจให้แล้วว่าโมเดลที่มี `answered_by` ต้องไม่มีค่าวัดผลติดอยู่

ถ้าเขียนสคริปต์ที่ยิง API ใหม่ ต้องส่ง `disable_fallbacks` ตั้งแต่บรรทัดแรก

## ทำไม repo นี้ถึงมีอยู่

gateway รวม LLM ฟรี 115 ตัวจาก 12 provider ไว้หลัง endpoint เดียวแบบ OpenAI-compatible
โดยที่ **`model_info` ของแต่ละตัวเป็นข้อมูลที่วัดจริง ไม่ใช่ที่ provider โฆษณา**

โปรเจกต์อื่น (hermes-line-bot, botforge) ดึง `/model/info` ไปตัดสินใจเลือกโมเดล
ตัวเลขที่ผิดจึงไม่ได้ทำให้แค่ repo นี้เสีย แต่ทำให้ agent ของคนอื่นพังกลางบทสนทนา

**ทุกโมเดลต้องฟรี** — เช็คราคาที่ `/api/v1/models` ของ provider ก่อนใส่เสมอ
อย่าเชื่อว่าตัวสืบทอดของโมเดลฟรีจะฟรีด้วย (`or/ox-alpha` ฟรีเพราะเป็น stealth
พอหมดอายุ ตัวสืบทอดกลับเป็นแบบเสียเงิน)

## คำสั่งที่ใช้บ่อย

```bash
set -a; source .env; set +a          # สคริปต์ทุกตัวต้องการ LITELLM_MASTER_KEY

./scripts/validate.sh                # CI เรียกตัวนี้ ต้องผ่านก่อน push เสมอ
pytest tests/ -q                     # 48 เคส รันทั้งหมดใน ~1 วินาที
pytest tests/test_config_edit.py -q  # ทีละไฟล์
ruff check scripts/ tests/           # ไม่มีในเครื่อง: docker run --rm -v "$PWD:/w" -w /w ghcr.io/astral-sh/ruff:latest check scripts/ tests/
shellcheck scripts/*.sh              # ไม่มีในเครื่อง: docker run --rm -v "$PWD:/w" -w /w koalaman/shellcheck:stable scripts/*.sh

./scripts/pick-model.sh              # ดูหมวดทั้งหมด
./scripts/pick-model.sh agent 60000  # เลือกโมเดลทำ agent ที่ prompt 60K
```

สคริปต์วัดผลทุกตัวใช้ `--write` เหมือนกัน และรับ prefix เป็น argument:

```bash
python3 scripts/health-check.py cb/ --write        # status + answered_by
python3 scripts/probe-context.py --write           # verified_max_prompt (กินโควต้าหนัก)
python3 scripts/probe-latency-14k.py mi/ --write   # latency_ms_14k
python3 scripts/verify-capabilities.py --write     # supports_function_calling
python3 scripts/bench-coding.py                    # ต้อง up stack ก่อน
```

**`probe-context.py` เผาโควต้าวันของ Cloudflare หมดทั้ง 13 ตัวในการรันครั้งเดียวมาแล้ว**
เลือก prefix เสมอถ้าจะรันซ้ำ อย่าตั้ง cron

⚠️ **ชื่อ test เป็นภาษาไทย เลือกรันทีละตัวด้วยการ copy ชื่อไม่ได้** — pytest แตก `ำ`
เป็น `ํ` + `า` ใน node id ทำให้ไม่ตรงกับที่เขียนในซอร์ส ถ้าต้องรันตัวเดียวจริง ๆ:

```bash
pytest "$(pytest tests/test_config_edit.py --collect-only -q | grep 'เขียนซ')" -q
```

ปกติรันทั้งชุดเร็วกว่าจะหา node id เจอ

## สถาปัตยกรรมที่ต้องเข้าใจก่อนแก้

### `litellm/config.yaml` เป็นแหล่งความจริงเดียว — 2,700 บรรทัด

มีทั้งค่าที่คนเขียน (`description`, `tags`, `provider_quota`) และค่าที่สคริปต์เขียน
(`status`, `verified_max_prompt`, `latency_ms_14k`, `answered_by`, `quota_*`) ปนกัน

**ห้ามแก้ฟิลด์ที่สคริปต์เป็นเจ้าของด้วยมือ** ใช้ `scripts/config_edit.py` ผ่านสคริปต์วัดผล
เหตุผล: ตัวเขียนรุ่นก่อนใช้ regex ที่สมมติว่าฟิลด์อยู่ติดกับ `tags:` เสมอ พอมีฟิลด์แทรกคั่น
มันเขียนเพิ่มอีกชุดแทนที่จะทับ — `status` ซ้ำทั้ง 115 โมเดล YAML เลือกอันท้ายซึ่งเป็นค่าเก่า
**การวัดทั้งรอบจึงไม่มีผลโดยไม่มีอะไรฟ้อง**

`config_edit.set_fields()` หาขอบเขตบล็อกจาก indent จริง ลบ key เดิมทุกตำแหน่งก่อนเขียนใหม่
รองรับ str / ตัวเลข / bool / list และเก็บคอมเมนต์ไว้ครบ (จึงไม่ใช้ `yaml.dump`)

### ตรรกะที่ใช้ร่วมกัน แยกเป็นโมดูล — อย่าลอกไปวาง

- **`scripts/failure_hints.py`** — แปล error ของ provider เป็นสาเหตุ
  (`โควต้าหมด` / `ตายถาวร` / `ชนเพดาน` / `timeout` / `อื่นๆ`) เกิดขึ้นเพราะโค้ดที่ลอกกันไป
  แล้วเพี้ยนจนสรุปผิด **HTTP status code เชื่อไม่ได้ ต้องอ่านข้อความอย่างเดียว**
  Cloudflare ส่ง 500 ตอนโควต้าหมด · OKMD ส่ง 401 · Groq ส่ง 413 ที่จริงคือ TPM limit
- **`is_inconclusive()`** ในไฟล์เดียวกัน — `No deployments available` คือ circuit breaker
  ของ LiteLLM ไม่ใช่คำตัดสิน ห้ามเอาไปเขียนทับ `status` เดิม
- **`scripts/config_edit.py`** — ตัวเขียน config ตัวเดียวในระบบ ไม่มี regex writer เหลือแล้ว

### `validate.sh` ไม่ได้ตรวจแค่ syntax

มันบังคับกติกาที่ตกลงกับทีมอื่นไว้ ทุกข้อเกิดจากบั๊กที่เคยเกิดจริง:

- fallback ทุก hop ต้องคนละ `quota_pool` (ตัวสำรองที่กินโควต้าก้อนเดียวกันตายพร้อมกัน)
- โมเดลที่มี `answered_by` ต้องไม่มีค่าวัดผลติดอยู่ — ตัวตรวจระบุฝั่ง **คนเขียน**
  แล้วเตือนทุกอย่างที่เหลือ ฟิลด์วัดใหม่จึงถูกจับอัตโนมัติ ไม่ต้องมาเติมลิสต์
- `quota_source: observed` ต้องมี `quota_observed_*` ครบ
- `free_until` ที่เลยกำหนดแล้ว = fail (ทุกโมเดลต้องฟรี บางเจ้าฟรีแค่ช่วงโปรโมชัน)
- `status_checked_at` เก่าเกิน 3 วัน = เตือน (ไม่ fail — คนส่ง PR เรื่องอื่นแก้ไม่ได้)
- โมเดลที่ชื่อมีคำว่า `stealth`/`preview` ต้องไม่ถูกทำเครื่องหมายว่า `stability: stable`
- ชื่อฟิลด์ที่เราตั้งต้องไม่ชนกับ LiteLLM (ตรวจกับ container ที่รันอยู่ ข้ามถ้าไม่มี)
- **บล็อก Python ใน `pick-model.sh` ห้ามมีอัญประกาศเดี่ยว**

ข้อสุดท้ายสำคัญกว่าที่ดู — บล็อกนั้นอยู่ใน `python3 -c '...'` ของ shell อัญประกาศเดี่ยว
ตัวเดียวจะปิด string แล้วโค้ดที่เหลือกลายเป็นคำสั่ง shell พลาดมาแล้ว 2 ครั้ง
ครั้งหลัง `bash -n` ไม่จับ `pytest` ไม่แตะ เพราะบรรทัดที่พังอยู่ใน branch ที่ยังไม่เคยถูกเรียก

### `status` ไม่ใช่ของที่ใช้ตัดสินตอน runtime

LiteLLM **ไม่ยอมให้แก้โมเดลที่มาจาก config ผ่าน API** (`Cannot edit config-based model`)
ทางเดียวคือเขียนไฟล์แล้ว `docker compose restart litellm` จึงตั้ง cron ถี่ ๆ ไม่ได้

`status` เป็นภาพ ณ วินาทีที่ตรวจ ดู `status_checked_at` ประกอบเสมอ
ตอนยิงจริงยังต้องดัก error แล้ว fallback เหมือนเดิม

### ค่าที่มีความหมายเฉพาะตัว

- `verified_max_prompt` = **"อย่างน้อยเท่านี้"** ไม่ใช่เพดาน ตัวที่ผ่านขั้น 14K แล้วพังที่ 32K
  จะได้เลข ~13,6xx–13,9xx เสมอ **กรองด้วย `>= 14000` ตรง ๆ จะตกหล่น 16 ตัว**
  (หมวด `agent` จึงใช้ 13,300)
- `max_prompt_detail` ขึ้นต้นว่า `โควต้า` = วัดไม่จบ **อย่าเอาเลขไปใช้**
- `latency_ms_14k` ยังเป็น call เดียว ไม่ใช่เวลาต่อ turn (ต่างกันได้ 35–180 เท่า)
- `answered_by` มีค่า = ชื่อนั้นเป็น alias แล้ว `quota_pool` ก็ไม่ตรงกับที่กินจริงด้วย

### fallback มี 3 โหมด ไม่ใช่ 2

```jsonc
{"model": "A"}                              // ใช้ chain ของ gateway
{"model": "A", "fallbacks": ["B", "C"]}     // ใช้ chain ของ client — ทับของ gateway
{"model": "A", "fallbacks": []}             // ไม่มี fallback (= disable_fallbacks)
```

โหมดกลางสำคัญสำหรับ platform ที่ให้ผู้ใช้ประกาศ chain เอง — **ไม่ต้องปิด fallback
ที่ gateway** และ **"ไม่ประกาศ" กับ "ประกาศว่าไม่เอา" ต้องส่งไม่เหมือนกัน**

⚠️ ชื่อผิดใน `fallbacks` ไม่มีใครบอก — LiteLLM คืน error ของตัวหลักมาเฉย ๆ
อาการเหมือนไม่ได้ตั้ง fallback เลย ต้องตรวจชื่อกับ `/model/info` ตอนบันทึก config

## ข้อตกลงกับทีมอื่น

- **restart `llm-litellm` ต้องแจ้งใน issue ก่อนเสมอ** — มี `nst-hermes-line-bot`,
  `nst-opencode-server`, `llm-openwebui` ต่ออยู่ บอท LINE จะสะดุดตอนมีคนคุย
- อยากใช้โมเดลใหม่ → มาขอให้ gateway ทดสอบก่อน หรือทดสอบเองแล้วส่ง PR กลับมาพร้อม
  `verified_by` บอกว่าใครวัด วัดเมื่อไหร่ วัดยังไง
- ผลจากการใช้งานจริงมีน้ำหนักกว่าผลที่เรายิง API ตรงเสมอ — มีของที่ gateway วัดให้ไม่ได้
  เช่นโมเดลที่ตอบผิดภาษาเฉพาะตอนอยู่ใน tool loop ที่มี system prompt ยาว
- ค่า `quota_source: observed` ชนะ `provider-docs` เสมอเวลาขัดกัน

## เอกสาร

`INTEGRATION.md` คือที่ที่บันทึกว่า **ฟิลด์ไหนเชื่อได้แค่ไหนและทำไม** — ยาวแต่เป็นที่แรก
ที่ควรอ่านเมื่อสงสัยว่าตัวเลขบางตัวมาจากไหน · `CONTRIBUTING.md` กติกาการส่งผลวัดกลับ ·
`docs/providers.md` โควต้าและวิธีขอ key รายเจ้า · `docs/benchmarks.md` ผลวัด ·
`CLIENTS.md` วิธีต่อ agent เข้ากับ gateway

## เขียนโค้ดในนี้

- คอมเมนต์บอก **ทำไม** ไม่ใช่ **ทำอะไร** และเมื่อแก้บั๊ก ให้เขียนไว้ด้วยว่าเดิมพังยังไง
- ทดสอบก่อนเขียนลงเอกสาร — เคยใส่คำสั่งใน README ที่รันแล้ว SyntaxError
- อย่าเชื่อผลจากเอกสารของ provider ให้ยิงจริงแล้วดู เจอมาแล้วหลายครั้งว่าโมเดลถูกปลด
  หรือเปลี่ยนความสามารถภายในวันเดียว
