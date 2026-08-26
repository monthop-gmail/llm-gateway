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
)
# ชนเพดาน context จริง — ยิงใหม่ก็เท่าเดิม
LIMIT_HINTS = (
    "context length", "maximum context", "context window exceeded", "too long",
    "too large", "token limit", "input length", "contextwindowexceeded",
)


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
    if any(h in low for h in LIMIT_HINTS):
        return "ชนเพดาน"
    if "timed out" in low or "timeout" in low:
        return "timeout"
    return "อื่นๆ"
