"""ทดสอบตัวจำแนก error — ทุกเคสในนี้เป็นข้อความจริงที่ provider ตอบมา

ที่ต้องมี test เพราะการจำแนกผิดทำให้ตัดสินใจผิดคนละทาง:
  โควต้าหมด  -> รอแล้วกลับมาเอง ไม่ต้องแก้อะไร
  ตายถาวร    -> ต้องแก้ config
  ชนเพดาน    -> ยิงใหม่ก็เท่าเดิม

และเพราะ HTTP status code ของ provider เชื่อไม่ได้ ต้องอ่านข้อความอย่างเดียว
— เคยแปะป้าย Cloudflare ว่า "error 500" ทั้งที่ข้อความบอกว่าโควต้าหมด
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from failure_hints import classify

# ข้อความจริงที่เก็บมาจากการยิง ไม่ใช่ที่แต่งขึ้น
REAL = [
    # --- โควต้าหมด: รอแล้วกลับมาเอง ---
    ("โควต้าหมด", 'HuggingfaceException - {"error":"You have depleted your monthly included credits."}'),
    ("โควต้าหมด", "CloudflareException - AiError: you have used up your daily free allocation"),
    ("โควต้าหมด", "OpenAIException - Error code: 401 - {'error': 'This model reached daily limit.'}"),
    ("โควต้าหมด", "RateLimitError: OpenAIException - you (monthop) have reached your weekly usage limit"),
    ("โควต้าหมด", "GroqException - Request too large for model"),
    ("โควต้าหมด", "RateLimitError: Nvidia_nimException - Error code: 429 - {'title': 'Too Many Requests'}"),
    ("โควต้าหมด", "MistralException - Service tier capacity exceeded, insufficient quota"),
    # --- ตายถาวร: ต้องแก้ config ---
    ("ตายถาวร", ("The model 'nvidia/llama-3.3-nemotron-super-49b-v1.5' has reached its end of life "
                 "on 2026-08-26T09:00:00Z and is no longer available.")),
    ("ตายถาวร", "Specified function in account 'wCbTyD0' is not found"),
    ("ตายถาวร", ("The requested model 'Qwen/Qwen2.5-7B-Instruct' is not supported by any provider "
                 "you have enabled. code: model_not_supported")),
    ("ตายถาวร", "OpenrouterException - No endpoints found for model"),
    ("ตายถาวร", "CerebrasException - this model has been archived"),
    ("ตายถาวร", "CloudflareException - model not available on the workers free plan"),
    # --- ชนเพดาน: ยิงใหม่ก็เท่าเดิม ---
    ("ชนเพดาน", "ContextWindowExceededError: litellm.BadRequestError: prompt is too long"),
    ("ชนเพดาน", "OpenAIException - Context window exceeded for this model"),
    ("ชนเพดาน", "This model's maximum context length is 8192 tokens"),
    # --- timeout ---
    ("timeout", "timed out"),
    ("timeout", "Request timeout after 300s"),
    # --- แยกไม่ออก ---
    ("อื่นๆ", "Error code: 404 - {'status': 404, 'title': 'Not Found'}"),
    ("อื่นๆ", "Provider returned error"),
]


@pytest.mark.parametrize("expect,msg", REAL, ids=[m[:38] for _, m in REAL])
def test_ข้อความจริงจาก_provider(expect, msg):
    assert classify(msg) == expect


def test_ไม่สนใจตัวพิมพ์เล็กใหญ่():
    assert classify("YOU HAVE DEPLETED YOUR MONTHLY CREDITS") == "โควต้าหมด"


def test_โควต้าชนะเพดานเมื่อเข้าได้ทั้งคู่():
    """Groq เขียนว่า Request too large ซึ่งเข้าเงื่อนไข 'too large' ของเพดานด้วย
    แต่ความจริงคือ TPM limit — พรุ่งนี้ยิง prompt เท่าเดิมผ่าน จึงต้องเป็นโควต้า"""
    assert classify("GroqException - Request too large") == "โควต้าหมด"


def test_ตายถาวรชนะเพดาน():
    """ข้อความที่มีทั้งคำว่า end of life และ context length — ตายสำคัญกว่า"""
    msg = "model reached its end of life; maximum context length is 8192"
    assert classify(msg) == "ตายถาวร"


def test_ข้อความว่างไม่พัง():
    assert classify("") == "อื่นๆ"


def test_ทุกกลุ่มมีเคสทดสอบครบ():
    """กันการเพิ่มกลุ่มใหม่แล้วลืมเขียน test"""
    covered = {e for e, _ in REAL}
    assert covered == {"โควต้าหมด", "ตายถาวร", "ชนเพดาน", "timeout", "อื่นๆ"}
