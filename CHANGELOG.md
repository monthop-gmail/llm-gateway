# CHANGELOG

รูปแบบตาม [Keep a Changelog](https://keepachangelog.com/) · เวอร์ชันตาม [SemVer](https://semver.org/lang/th/)

สิ่งที่ถือว่าเป็น **breaking** ของ repo นี้คือการเปลี่ยนสัญญาของ `/model/info` —
ลบฟิลด์ ตัดความหมายเดิม หรือเปลี่ยนชนิดค่า เพราะโปรเจกต์อื่นดึงไปตัดสินใจเลือกโมเดล
ส่วนการเพิ่มโมเดลหรือเพิ่มฟิลด์ใหม่ไม่ถือว่า breaking

## [0.1.0] — 2026-08-26

เวอร์ชันแรกที่ติดป้าย ก่อนหน้านี้ทีมอื่นอ้างอิงด้วย commit SHA

### เพิ่ม

- **`model_info` ที่เครื่องอ่านได้** — `status` `status_checked_at` `status_detail`
  `answered_by` `quota_pool` `quota_window` `verified_max_prompt`
  `max_prompt_detail` `latency_ms_14k` ดึงผ่าน `/model/info` ได้ทั้งหมด
- **`./scripts/pick-model.sh agent [floor]`** — หมวดสำหรับเลือกโมเดลไปทำ agent
  รับเพดาน prompt ที่ agent ใช้จริงเป็น argument
- **เครื่องมือวัด** — `probe-context.py` (เพดาน prompt จริง)
  `probe-latency-14k.py` (เวลาตอบที่ขนาดที่ agent ใช้)
  `verify-capabilities.py` (tool calling) `health-check.py` (สถานะ + alias)
- **`tests/`** — 42 เคสของ `config_edit` กับ `failure_hints` CI รันทุก push
- **`CONTRIBUTING.md` + issue/PR template** — กติกาการส่งผลวัดกลับ

### แก้

- **ค่าที่วัดผ่าน fallback ปนเปื้อน metadata** — สคริปต์วัดทุกตัวไม่ได้ปิด
  `fallbacks` จึงวัดโมเดลที่ตัวสำรองตอบแทน แล้วบันทึกผลใส่ชื่อโมเดลที่ขอ
  ตอนนี้ทุกตัวส่ง `"disable_fallbacks": true` และ `validate.sh` ตรวจให้ว่าไม่มี
  ค่าวัดผลติดกับโมเดลที่มี `answered_by`
- **ตัวเขียน config สร้าง key ซ้ำ** — ตัวเขียนรุ่น regex สมมติว่าฟิลด์เป้าหมาย
  อยู่ติดกับ `tags:` เสมอ พอมีฟิลด์แทรกคั่นก็เขียนเพิ่มอีกชุด YAML เลือกอันท้าย
  ซึ่งเป็นค่าเก่า ทำให้การวัดทั้งรอบไม่มีผลโดยไม่มีอะไรฟ้อง แทนด้วย
  `config_edit.set_fields` ที่หาขอบเขตบล็อกจาก indent จริง
- **`fallback` ที่ตัวสำรองกินโควต้าก้อนเดียวกับตัวหลัก** 3 เส้น — หมดพร้อมกัน
  จึงไม่ได้ช่วยอะไร `validate.sh` ตรวจให้แล้ว
- **`health-check.py` คืน exit 1 ตลอดไป** เมื่อมีโมเดลตายที่ตั้งใจเก็บไว้เป็น alias
  ตอนนี้แดงเฉพาะตอนที่ชื่อชี้ไปไม่ถึงอะไรเลย

### ลบ

- `verified_max_prompt` และ `latency_ms_14k` ของโมเดลที่วัดผ่านตัวสำรอง
  (`hf/*` เป็นหลัก) — ค่าที่ไม่มีดีกว่าค่าที่ผิด เพราะตัวกรองจะมองว่า
  "ยังไม่ได้วัด" แทนที่จะเชื่อ วัดใหม่ได้เมื่อโควต้าคืน

### รู้ไว้

- `status` เป็นภาพ ณ วินาทีที่ตรวจ ไม่ใช่คุณสมบัติถาวร — ดู `status_checked_at`
  ประกอบเสมอ และอย่าใช้ตัดสินตอน runtime
- `verified_max_prompt` เป็นค่า **"อย่างน้อยเท่านี้"** ไม่ใช่เพดาน
- อัปเดต `status` แบบ real-time ไม่ได้ — LiteLLM ไม่ยอมให้แก้โมเดลที่มาจาก config
  ผ่าน API ต้องเขียนไฟล์แล้ว restart
