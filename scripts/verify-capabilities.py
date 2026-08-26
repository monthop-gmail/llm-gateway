#!/usr/bin/env python3
"""ยิง tool calling ทุกโมเดลแล้วเทียบกับที่บันทึกไว้ใน model_info

    set -a; source .env; set +a
    python3 scripts/verify-capabilities.py            # ตรวจทุกตัว
    python3 scripts/verify-capabilities.py gq/ cb/    # เฉพาะ prefix
    python3 scripts/verify-capabilities.py --fix      # แก้ config ให้ตรงเลย

ทำไมต้องมี: ข้อมูล "ใช้ tool ไม่ได้" มีอายุสั้นกว่าที่คิด — provider แก้ของ
ตัวเองแล้วเราไม่รู้ เจอมาแล้วเมื่อ 2026-08-26 ว่า nim/llama-3.3-70b และ
cf/qwen3-30b-a3b เปลี่ยนจากใช้ tool ไม่ได้เป็นใช้ได้ ภายในไม่กี่วัน
โดยรู้เพราะโปรเจกต์อื่นมาทัก ไม่ใช่เพราะเราตรวจเอง

รายงานเฉพาะตัวที่ "ไม่ตรง" กับ config — ตัวที่ตรงอยู่แล้วไม่ต้องสนใจ
คืน exit 1 เมื่อเจอความไม่ตรง เอาไปต่อ cron/CI ได้

⚠️ ขอบเขต: script นี้ยิง API ตรงด้วย prompt สั้น ๆ จึงเห็นแค่ "เรียก tool เป็นไหม"
คุณสมบัติที่โผล่เฉพาะในบริบทจริงของ agent มองไม่เห็น เช่น oc/gpt-oss-120b
ผ่าน script นี้สบาย ๆ แต่ hermes เจอว่าหลุดไปตอบภาษาจีน 2 ใน 3 ครั้งเมื่อรันใน
tool loop ที่มี system prompt อังกฤษ 15 KB — ของแบบนี้ต้องให้โปรเจกต์ปลายทาง
ทดสอบแล้วส่ง PR กลับ (ดู INTEGRATION.md หัวข้อ "gateway วัดอะไรให้ไม่ได้")
"""
from __future__ import annotations

import concurrent.futures as futures
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "litellm/config.yaml"
BASE = os.environ.get("LITELLM_URL", "http://localhost:4000")
KEY = os.environ.get("LITELLM_MASTER_KEY")

# โจทย์ที่บังคับให้ต้องเรียก tool ถ้าโมเดลทำเป็น
PROBE = {
    "messages": [{"role": "user", "content": "อากาศเชียงใหม่วันนี้เป็นยังไง"}],
    "tools": [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "ดูสภาพอากาศของเมือง",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }],
    "tool_choice": "auto",
    "max_tokens": 250,
}

# error ที่แปลว่า "ยังตัดสินไม่ได้" ไม่ใช่ "ทำไม่เป็น"
INCONCLUSIVE = (
    "rate limit", "ratelimiterror", "429", "quota", "too many requests",
    "depleted", "used up your daily", "payment required", "timed out", "timeout",
    # error ที่ไม่ได้บอกว่า "ทำไม่เป็น" — อาจแค่ล่มชั่วคราว อย่าเพิ่งสรุป
    "invalid response object", "apiconnectionerror", "connection error",
    "internal server error", "upstream request failed", "service unavailable",
    "temporarily busy", "502", "503", "504",
)


def post(model: str, timeout: int = 180) -> dict:
    body = dict(PROBE, model=model)
    req = urllib.request.Request(
        BASE + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def probe(model: str) -> tuple[str, str, str]:
    """คืน (model, ผล, รายละเอียด) โดยผลเป็น yes / no / skip"""
    try:
        d = post(model)
        msg = d["choices"][0]["message"]
        return model, ("yes" if msg.get("tool_calls") else "no"), ""
    except Exception as exc:  # noqa: BLE001 — อยากได้ทุก error ไม่ใช่แค่ HTTP
        raw = ""
        if isinstance(exc, urllib.error.HTTPError):
            raw = exc.read().decode(errors="replace")
            try:
                raw = json.loads(raw)["error"]["message"]
            except Exception:
                pass
        else:
            raw = str(exc)
        raw = re.sub(r"\s+", " ", raw).split("No fallback")[0].strip()
        low = raw.lower()
        if any(h in low for h in INCONCLUSIVE):
            return model, "skip", raw[:80]
        return model, "no", raw[:80]


def main() -> int:
    if not KEY:
        print("ต้องตั้ง LITELLM_MASTER_KEY — ลอง: set -a; source .env; set +a", file=sys.stderr)
        return 1

    args = [a for a in sys.argv[1:] if a != "--fix"]
    do_fix = "--fix" in sys.argv

    cfg = yaml.safe_load(CFG.read_text())
    entries = {
        m["model_name"]: (m.get("model_info") or {}).get("supports_function_calling")
        for m in cfg["model_list"]
        if (m.get("model_info") or {}).get("mode") != "embedding"
    }
    models = list(entries)
    if args:
        models = [m for m in models if m.startswith(tuple(args))]
        if not models:
            print(f"ไม่มีโมเดลที่ขึ้นต้นด้วย {tuple(args)}", file=sys.stderr)
            return 1

    print(f"ตรวจ tool calling {len(models)} โมเดลผ่าน {BASE}\n")
    mismatch: list[tuple[str, bool, bool]] = []
    skipped: list[tuple[str, str]] = []

    with futures.ThreadPoolExecutor(max_workers=6) as pool:
        for model, verdict, detail in pool.map(probe, models):
            if verdict == "skip":
                print("?", end="", flush=True)
                skipped.append((model, detail))
                continue
            actual = verdict == "yes"
            recorded = entries.get(model)
            if recorded is None or actual == recorded:
                print(".", end="", flush=True)
            else:
                print("!", end="", flush=True)
                mismatch.append((model, bool(recorded), actual))

    checked = len(models) - len(skipped)
    print(f"\n\nตรวจได้ {checked} / ข้ามเพราะโควต้าหรือ timeout {len(skipped)}")

    if skipped:
        print(f"\nยังตัดสินไม่ได้ ({len(skipped)}) — ลองใหม่ทีหลัง")
        for model, detail in skipped:
            print(f"  {model:<26} {detail}")

    if not mismatch:
        print("\n✅ config ตรงกับความจริงทุกตัวที่ตรวจได้")
        return 0

    print(f"\n⚠️  ไม่ตรงกับ config {len(mismatch)} ตัว")
    for model, recorded, actual in mismatch:
        arrow = "ใช้ไม่ได้ -> ใช้ได้แล้ว" if actual else "ใช้ได้ -> ใช้ไม่ได้แล้ว"
        print(f"  {model:<26} config บอก {recorded} แต่จริง {actual}   ({arrow})")

    if not do_fix:
        print("\nรันซ้ำด้วย --fix เพื่อแก้ litellm/config.yaml ให้ตรง")
        return 1

    text = CFG.read_text()
    for model, _, actual in mismatch:
        pat = re.compile(
            r"(- model_name: " + re.escape(model) + r"\n(?:.*?\n)*?      supports_function_calling: )(true|false)"
        )
        new = "true" if actual else "false"
        text, n = pat.subn(lambda m: m.group(1) + new, text, count=1)
        if not n:
            print(f"  แก้ไม่ได้: {model}", file=sys.stderr)
    CFG.write_text(text)
    print(f"\nแก้ config แล้ว {len(mismatch)} ตัว — restart litellm เพื่อให้มีผล")
    print("อย่าลืมอัปเดต tags/description ที่เกี่ยวข้องด้วยถ้ามี")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
