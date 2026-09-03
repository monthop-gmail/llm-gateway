"""แยกให้ออกว่า error ที่ provider ตอบมาแปลว่าอะไร — ใช้ร่วมกันทุกสคริปต์

เดิมแต่ละสคริปต์มีรายการคำใบ้ของตัวเอง แล้วมันเพี้ยนออกจากกัน:
probe-context.py แปะป้าย Cloudflare ว่า "error 500" ทั้งที่ข้อความในนั้นเขียน
ชัดว่า "you have used up your daily free" — คนละเรื่องกับเพดาน context เลย

บทเรียนที่ได้จากการยิงจริง: **HTTP status code เชื่อไม่ได้** ต้องอ่านข้อความ
  - Cloudflare ส่ง 500 เมื่อโควต้าวันหมด
  - OKMD ส่ง 401 พร้อมข้อความ "This model reached daily limit."
    (ปลายทางอย่าเพิ่งคิดว่า key เสีย)
  - Groq ส่ง 413 "Request too large" ซึ่งคือ TPM limit ไม่ใช่เพดาน context
"""
from __future__ import annotations

# โควต้าหมด — รอ reset แล้วกลับมาเอง ไม่ต้องแก้อะไร
QUOTA_HINTS = (
    "depleted your monthly", "used up your daily", "rate limit", "ratelimiterror",
    "429", "too many requests", "quota", "insufficient", "payment required",
    "tokens per minute", "daily limit", "weekly usage limit", "request too large",
)
# โมเดลหายไปจริง — ต้องแก้ litellm/config.yaml
DEAD_HINTS = (
    "does not exist", "model_not_found", "not found for account", "no endpoints found",
    "unavailable for free", "archived", "requires a subscription",
    "not available on the workers free", "model_not_supported",
    "is not supported by any provider",
    # NVIDIA NIM ปลดโมเดลด้วย 410 Gone พร้อมวันหมดอายุ เจอสด 2026-08-26:
    # "has reached its end of life on 2026-08-26T09:00:00Z and is no longer available"
    "end of life", "no longer available",
    # NIM 404 เมื่อ function ถูกลบออกจากบัญชี
    "specified function in account",
    # OpenRouter ปิดโมเดล stealth เมื่อจบช่วงทดสอบ แล้วเฉลยว่าคือรุ่นอะไร
    # เจอจริง 2026-08-27 กับ or/ox-alpha: "Thank you for participating in the
    # Stealth Ox Alpha testing period. This model was ZAI's GLM-5.3 Flash."
    # ก่อนหน้านี้ข้อความนี้ถูกจัดเป็น "อื่นๆ" -> status unknown จึงไม่มีอะไรเตือน
    # ทั้งที่โมเดลหายถาวรแล้ว ซึ่งเงียบกว่าการรายงานว่าตายเสียอีก
    "testing period", "this model was",
)
# คำที่บอกว่า "ความสามารถ" ไม่รองรับ ไม่ใช่ "โมเดล" ไม่มีอยู่
#
# ต้องแยกให้ออก เพราะสองอย่างนี้ใช้ถ้อยคำเดียวกันแต่คนละความหมายสิ้นเชิง:
#   "Model hy3-free is not supported"                -> โมเดลหายไปแล้ว = ตายถาวร
#   "tool calling is not supported with this model"  -> แค่ทำ tool ไม่ได้ ยังใช้งานได้
#
# อันหลังคือ gq/compound กับ gq/compound-mini ที่ยังใช้ค้นเว็บได้ปกติ
# ถ้าเอา "not supported" ไปเป็นคำใบ้ตายทื่อ ๆ สองตัวนี้จะถูกมาร์คว่าตายทันที
CAPABILITY_WORDS = (
    "tool calling", "tool_calling", "function calling", "tool_choice", "tools",
    "image", "vision", "audio", "streaming", "json mode", "response_format",
    "system message", "parallel",
)

# ชนเพดาน context จริง — ยิงใหม่ก็เท่าเดิม
LIMIT_HINTS = (
    "context length", "maximum context", "context window exceeded", "too long",
    "too large", "token limit", "input length", "contextwindowexceeded",
)


# ข้อความที่ LiteLLM สร้างเอง ไม่ใช่คำตอบของ provider — สรุปอะไรไม่ได้
#
# พอโมเดลพังซ้ำ ๆ LiteLLM จะ cooldown แล้วหยุดยิงไป provider เลย คำตอบที่ได้
# จึงเป็นข้อความของ LiteLLM เอง ซึ่งบังข้อความจริงที่บอกว่าโมเดลตายหรือแค่โควต้าหมด
#
# เจอจริง 2026-08-27: or/ox-alpha ตรวจรอบแรกได้ "ตายถาวร" ถูกต้องจากข้อความ
# retirement ของ OpenRouter พอตรวจซ้ำอีกรอบกลายเป็น "อื่นๆ" เพราะ cooldown
# ถ้าเขียนทับก็จะเสียข้อสรุปที่ถูกไปเฉย ๆ
INCONCLUSIVE_HINTS = (
    "no deployments available",
    "no healthy deployment",
    "cooldown",
)


def is_inconclusive(msg: str) -> bool:
    """True = อย่าเอาผลรอบนี้ไปเขียนทับของเดิม เพราะยังไม่ได้คุยกับ provider จริง"""
    return any(h in msg.lower() for h in INCONCLUSIVE_HINTS)


def classify(msg: str) -> str:
    """คืน: โควต้าหมด | ตายถาวร | ชนเพดาน | timeout | อื่นๆ

    เรียงลำดับสำคัญ: เช็คโควต้าก่อนเพดาน เพราะ Groq เขียน "Request too large"
    ซึ่งเข้าเงื่อนไขทั้งสองแบบ แต่ความจริงคือ TPM limit
    """
    low = msg.lower()
    if any(h in low for h in QUOTA_HINTS):
        return "โควต้าหมด"
    if any(h in low for h in DEAD_HINTS):
        return "ตายถาวร"
    # "ไม่รองรับ" แปลว่าตาย เฉพาะตอนที่พูดถึงตัวโมเดล ไม่ใช่ความสามารถของมัน
    # เจอจริง 2026-09-03: zen/hy3 ตอบ 401 พร้อม "Model hy3-free is not supported"
    # ซึ่งเดิมตกเป็น "อื่นๆ" -> status unknown กฎ exit 1 ของ orphan จึงไม่ทำงาน
    if ("not supported" in low or "unsupported" in low) \
            and not any(w in low for w in CAPABILITY_WORDS):
        return "ตายถาวร"
    if any(h in low for h in LIMIT_HINTS):
        return "ชนเพดาน"
    if "timed out" in low or "timeout" in low:
        return "timeout"
    return "อื่นๆ"
