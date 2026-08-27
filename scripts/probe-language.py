#!/usr/bin/env python3
"""วัดว่าโมเดล "อยู่กับภาษาของผู้ใช้" ไหม เมื่อบริบทเต็มไปด้วยภาษาอังกฤษ

    set -a; source .env; set +a
    python3 scripts/probe-language.py                 # ตรวจตัวที่ยังไม่มีผล
    python3 scripts/probe-language.py oc/ cb/         # เฉพาะ prefix
    python3 scripts/probe-language.py --write         # เขียนผลกลับเข้า model_info
    python3 scripts/probe-language.py --sizes 15000   # ระบุขนาดบริบท

ทำไม gateway ควรวัดข้อนี้เอง
------------------------------
เดิมเราเขียนไว้ว่าเป็นเรื่องที่ปลายทางต้องวัดเอง เพราะมันโผล่เฉพาะใน agent loop
แต่พอดูจริง ๆ สิ่งที่ทำให้ดริฟต์มี 4 อย่าง — โมเดล · ปริมาณบริบทอังกฤษ ·
ผล tool ที่เป็นอังกฤษ · คำสั่งภาษาใน system prompt — **ไม่มีข้อไหนผูกกับ
client รายใดรายหนึ่ง** จำลองได้ทั้งหมด

ถ้าปล่อยให้แต่ละ client วัดเอง ทุกทีมจะเผาโควต้าก้อนเดียวกันซ้ำ ๆ เพื่อคำตอบ
เดียวกัน — ซึ่งเป็นสิ่งที่ gateway นี้มีไว้ป้องกันตั้งแต่แรก

โจทย์ที่ใช้ — มาจากเคสจริงที่ทำให้หลุด
------------------------------------
hermes-line-bot เจอว่า `oc/gpt-oss-120b` ตอบไทยปกติกับโจทย์ธรรมดา แต่หลุดไป
**ตอบภาษาจีน 2 ใน 3 ครั้ง** กับโจทย์ที่ **มีหลายคำถามในประโยคเดียว + สั่งให้
ตอบสั้น** (2026-08-26) โจทย์ง่าย ๆ จับไม่เจอ จึงใช้รูปแบบที่หลุดจริงเป็นตัวตั้ง

⚠️ ยิงด้วย disable_fallbacks เสมอ ไม่งั้นวัดภาษาของตัวสำรองแล้วแปะชื่อตัวที่ขอ
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = (os.environ.get("LITELLM_URL") or "http://localhost:4000").rstrip("/")
KEY = os.environ.get("LITELLM_MASTER_KEY") or ""
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ขนาดบริบทที่วัด — client แต่ละตัวมี turn ไม่เท่ากัน จึงเก็บหลายระดับ
# แล้วให้ปลายทางอ่านช่องที่ตรงกับของตัวเอง แทนที่จะได้ตัวเลขเดียวที่ใช้ไม่ตรงใคร
DEFAULT_SIZES = [15_000, 60_000]
ROUNDS = 3
CHARS_PER_TOKEN = 5.9

FILLER = (
    "The deployment pipeline validates each service before promoting it to the "
    "next environment, and the audit log records every change with a timestamp. "
)

# system prompt แบบ agent ทั่วไป — สั่งเรื่องภาษาไว้ชัดเหมือนที่ client จริงทำ
SYSTEM = (
    "You are a helpful assistant operating inside an automated agent loop. "
    "You have access to shell and file tools. Always answer in the SAME language "
    "the user writes in. Keep responses plain text without markdown.\n\n"
    "Reference material follows.\n\n"
)

# ผล tool ปลอมเป็นอังกฤษล้วน — นี่คือตัวที่ดึงโมเดลออกจากภาษาผู้ใช้
TOOL_RESULT = (
    "total 48\ndrwxr-xr-x 2 root root 4096 Aug 26 11:20 agent.log\n"
    "-rw-r--r-- 1 root root 8192 Aug 26 11:20 gateway.log\n"
    "-rw-r--r-- 1 root root 2048 Aug 26 11:20 errors.log\n"
)

# โจทย์ที่ทำให้หลุดจริง: หลายคำถามในประโยคเดียว + สั่งให้ตอบสั้น
STRESS_TH = (
    "ดูหน่อยว่าในโฟลเดอร์นั้นมีไฟล์อะไรบ้าง แล้วบอกด้วยว่าแต่ละอันน่าจะเก็บอะไร "
    "และอันไหนควรดูก่อนถ้าระบบมีปัญหา ตอบสั้นๆ"
)


def detect(text: str) -> str:
    """เหมือน _lang.py ของ hermes-line-bot — นับตัวอักษรตามช่วง unicode"""
    thai = len(re.findall(r"[฀-๿]", text))
    cjk = len(re.findall(r"[一-鿿]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if not text.strip():
        return "err"
    if thai > 40:
        return "th"
    if cjk > 10:
        return "zh"
    if latin > 40:
        return "en"
    return "err"


def _filler(target_tokens: int) -> str:
    n = int(target_tokens * CHARS_PER_TOKEN)
    return (FILLER * (n // len(FILLER) + 1))[:n]


def ask(model: str, size: int, timeout: int = 180) -> tuple[str, str]:
    """คืน (ภาษาที่ตอบ, ข้อความ/เหตุผล)"""
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM + _filler(size)},
            {"role": "user", "content": STRESS_TH},
            {"role": "assistant", "content": "", "tool_calls": [{
                "id": "call_1", "type": "function",
                "function": {"name": "shell", "arguments": json.dumps({"cmd": "ls -la"})},
            }]},
            {"role": "tool", "tool_call_id": "call_1", "content": TOOL_RESULT},
        ],
        "max_tokens": 400,
        # 🔴 ไม่ปิด = วัดภาษาของตัวสำรองแล้วแปะชื่อตัวที่ขอ
        "disable_fallbacks": True,
    }
    req = urllib.request.Request(
        BASE + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return "err", e.read().decode()[:120]
    except Exception as e:  # timeout / network
        return "err", str(e)[:120]

    choices = d.get("choices") or []
    if not choices:
        return "err", str(d)[:120]
    # gateway บอกตรง ๆ ว่าใครตอบ — ถ้าไม่ใช่ตัวที่ขอ ผลนี้ใช้ไม่ได้
    answered = d.get("model") or ""
    if answered and model.split("/")[-1] not in answered:
        return "err", "ตอบโดย " + answered + " ไม่ใช่ตัวที่ขอ"
    msg = choices[0].get("message") or {}
    text = msg.get("content") or msg.get("reasoning_content") or ""
    return detect(text), text[:80]


def verdict(langs: list[str]) -> str:
    """สรุปผลหลายรอบเป็นค่าเดียวที่ปลายทางเอาไปกรองได้"""
    good = langs.count("th")
    if good == len(langs):
        return "ok"
    if good == 0 and langs.count("err") == len(langs):
        return "unknown"
    other = [x for x in langs if x not in ("th", "err")]
    if other:
        return "drift-" + max(set(other), key=other.count)
    return "unknown"


def main() -> int:
    if not KEY:
        print("ต้องมี LITELLM_MASTER_KEY — ลอง: set -a; source .env; set +a", file=sys.stderr)
        return 2
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    sizes = DEFAULT_SIZES
    if "--sizes" in sys.argv:
        sizes = [int(x) for x in sys.argv[sys.argv.index("--sizes") + 1].split(",")]

    import yaml
    cfg = yaml.safe_load(open(os.path.join(ROOT, "litellm/config.yaml")))
    models = []
    for m in cfg["model_list"]:
        name = m["model_name"]
        mi = m.get("model_info") or {}
        if args and not any(name.startswith(a) for a in args):
            continue
        # ไม่ยิงตัวที่รู้อยู่แล้วว่าใช้ไม่ได้ — เปลืองโควต้าเปล่า
        if mi.get("status") in ("dead", "rate_limited"):
            continue
        if mi.get("answered_by"):
            continue
        if mi.get("supports_function_calling") is not True:
            continue
        models.append(name)

    print(f"วัด {len(models)} โมเดล {len(sizes)} ขนาด รอบละ {ROUNDS} ครั้ง")
    print("โจทย์: หลายคำถามในประโยคเดียว + สั่งตอบสั้น (รูปแบบที่ทำให้หลุดจริง)\n")

    results: dict[str, dict[int, str]] = {}
    for name in models:
        row = []
        results[name] = {}
        for size in sizes:
            langs = [ask(name, size)[0] for _ in range(ROUNDS)]
            v = verdict(langs)
            results[name][size] = v
            row.append(f"{size // 1000}K={v}")
        print(f"  {name:<26} " + "  ".join(row))

    if write:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        from datetime import datetime, timezone

        from config_edit import set_fields

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = os.path.join(ROOT, "litellm/config.yaml")
        text = open(path).read()
        n = 0
        for name, by_size in results.items():
            fields = {f"language_th_{s // 1000}k": v for s, v in by_size.items()}
            fields["language_checked_at"] = stamp
            fields["language_verified_by"] = "gateway probe-language.py"
            text, ok = set_fields(text, name, fields)
            n += ok
        open(path, "w").write(text)
        print(f"\nเขียนกลับเข้า config แล้ว {n} ตัว — ต้อง restart litellm ถึงจะเห็นใน /model/info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
