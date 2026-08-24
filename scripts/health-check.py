#!/usr/bin/env python3
"""ยิงทุกโมเดลใน gateway เพื่อหาว่าตัวไหนใช้ไม่ได้ และเพราะอะไร

    set -a; source .env; set +a
    python3 scripts/health-check.py              # ตรวจทุกตัว
    python3 scripts/health-check.py gq/ cb/      # ตรวจเฉพาะ prefix ที่ระบุ

แยกสาเหตุที่ล้มเหลวออกเป็น 2 กลุ่ม เพราะวิธีแก้ต่างกันสิ้นเชิง:

  ตายถาวร  — โมเดลถูกปลด/เปลี่ยนเป็นเสียเงิน ต้องแก้ litellm/config.yaml
  โควต้าหมด — ยิงเยอะเกินโควต้าวัน/เดือน รอ reset แล้วกลับมาเอง

ตัวอย่างที่เคยเจอจริง: Groq ปลด llama-3.1-8b-instant ออกจาก free tier
ระหว่างวัน (2026-08-23) config จึงมีโมเดลที่ตายอยู่โดยไม่มีใครรู้
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
BASE = os.environ.get("LITELLM_URL", "http://localhost:4000")
KEY = os.environ.get("LITELLM_MASTER_KEY")

# ข้อความที่บอกว่าเป็นโควต้าหมด ไม่ใช่โมเดลตาย
QUOTA_HINTS = (
    "depleted your monthly", "used up your daily", "rate limit",
    "ratelimiterror", "429", "too many requests", "quota", "insufficient",
    "payment required", "tokens per minute",
)
# ข้อความที่บอกว่าโมเดลหายไปจริง
DEAD_HINTS = (
    "does not exist", "model_not_found", "not found for account", "no endpoints found",
    "unavailable for free", "archived", "requires a subscription", "not available on the workers free",
)


def _post(path: str, body: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _error_text(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        raw = exc.read().decode(errors="replace")
        try:
            raw = json.loads(raw)["error"]["message"]
        except Exception:
            pass
    else:
        raw = str(exc)
    raw = re.sub(r"\s+", " ", raw)
    # ตัดหางที่ LiteLLM ต่อท้ายมา ยาวและไม่ช่วยอ่าน
    for cut in ("No fallback", "Received Model Group", "Available Model Group"):
        raw = raw.split(cut)[0]
    return raw.strip()


def classify(msg: str) -> str:
    low = msg.lower()
    if any(h in low for h in DEAD_HINTS):
        return "ตายถาวร"
    if any(h in low for h in QUOTA_HINTS):
        return "โควต้าหมด"
    if "timed out" in low or "timeout" in low:
        return "timeout"
    return "อื่นๆ"


def check(model: str) -> tuple[str, str, str]:
    is_embedding = model.startswith("emb/")
    try:
        if is_embedding:
            _post("/v1/embeddings", {"model": model, "input": ["hi"]})
        else:
            _post("/v1/chat/completions", {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 10,
            })
        return model, "OK", ""
    except Exception as exc:  # noqa: BLE001 — อยากได้ทุก error ไม่ใช่แค่ HTTP
        msg = _error_text(exc)
        return model, classify(msg), msg[:110]


def main() -> int:
    if not KEY:
        print("ต้องตั้ง LITELLM_MASTER_KEY ก่อน — ลอง: set -a; source .env; set +a", file=sys.stderr)
        return 1

    cfg = yaml.safe_load((ROOT / "litellm/config.yaml").read_text())
    models = [m["model_name"] for m in cfg["model_list"]]
    if len(sys.argv) > 1:
        wanted = tuple(sys.argv[1:])
        models = [m for m in models if m.startswith(wanted)]
        if not models:
            print(f"ไม่มีโมเดลที่ขึ้นต้นด้วย {wanted}", file=sys.stderr)
            return 1

    print(f"ตรวจ {len(models)} โมเดลผ่าน {BASE}\n")
    results: list[tuple[str, str, str]] = []
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        for model, status, msg in pool.map(check, models):
            print("." if status == "OK" else "X", end="", flush=True)
            results.append((model, status, msg))

    ok = [r for r in results if r[1] == "OK"]
    print(f"\n\nใช้ได้ {len(ok)} / ทั้งหมด {len(results)}")

    for group in ("ตายถาวร", "โควต้าหมด", "timeout", "อื่นๆ"):
        rows = [r for r in results if r[1] == group]
        if not rows:
            continue
        note = {
            "ตายถาวร": "  ← ต้องแก้ litellm/config.yaml",
            "โควต้าหมด": "  ← รอ reset แล้วกลับมาเอง",
            "timeout": "  ← provider ช้าหรือล่ม ลองใหม่ทีหลัง",
        }.get(group, "")
        print(f"\n{group} ({len(rows)}){note}")
        for model, _, msg in rows:
            print(f"  {model:<24} {msg}")

    # ให้ CI/สคริปต์อื่นเช็คได้ว่ามีของตายไหม
    return 1 if any(r[1] == "ตายถาวร" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
