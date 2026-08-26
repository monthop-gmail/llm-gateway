#!/usr/bin/env python3
"""ยิงทุกโมเดลใน gateway เพื่อหาว่าตัวไหนใช้ไม่ได้ และเพราะอะไร

    set -a; source .env; set +a
    python3 scripts/health-check.py              # ตรวจทุกตัว
    python3 scripts/health-check.py gq/ cb/      # ตรวจเฉพาะ prefix ที่ระบุ
    python3 scripts/health-check.py --write      # เขียนผลกลับเข้า model_info

แยกสาเหตุที่ล้มเหลวออกเป็น 2 กลุ่ม เพราะวิธีแก้ต่างกันสิ้นเชิง:

  ตายถาวร  — โมเดลถูกปลด/เปลี่ยนเป็นเสียเงิน ต้องแก้ litellm/config.yaml
  โควต้าหมด — ยิงเยอะเกินโควต้าวัน/เดือน รอ reset แล้วกลับมาเอง

ตัวอย่างที่เคยเจอจริง: Groq ปลด llama-3.1-8b-instant ออกจาก free tier
ระหว่างวัน (2026-08-23) config จึงมีโมเดลที่ตายอยู่โดยไม่มีใครรู้

--write เขียน status / status_checked_at / status_detail กลับเข้า model_info
ของ litellm/config.yaml เพื่อให้ consumer กรองด้วย status == "ok" ได้
(ขอมาใน issue #3)

⚠️ ต้อง restart litellm ถึงจะเห็นผลใน /model/info — LiteLLM ไม่ยอมให้แก้
โมเดลที่มาจาก config ผ่าน API ("Cannot edit config-based model") จึงตั้ง cron
ถี่ ๆ ไม่ได้ แนะนำวันละครั้งหรือตอนสงสัยว่าโควต้าหมด แล้ว commit ผลเข้า git
ไปด้วยจะได้มีประวัติว่าโมเดลไหนตายตอนไหน
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from failure_hints import classify  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = os.environ.get("LITELLM_URL", "http://localhost:4000")
KEY = os.environ.get("LITELLM_MASTER_KEY")

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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        wanted = tuple(args)
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

    if "--write" in sys.argv:
        _write_back(results)

    # ให้ CI/สคริปต์อื่นเช็คได้ว่ามีของตายไหม
    return 1 if any(r[1] == "ตายถาวร" for r in results) else 0


# แปลงผลตรวจเป็นค่า status ที่ consumer ใช้กรองได้
_STATUS = {
    "OK": "ok",
    "โควต้าหมด": "rate_limited",
    "ตายถาวร": "dead",
    "ชนเพดาน": "ok",   # ตอบ error เรื่องความยาวได้ = โมเดลยังมีชีวิต
    "timeout": "unknown",
    "อื่นๆ": "unknown",
}


def _write_back(results: list[tuple[str, str, str]]) -> None:
    """เขียน status กลับเข้า model_info ของ config.yaml"""
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = ROOT / "litellm/config.yaml"
    text = path.read_text()
    written = 0

    for model, verdict, detail in results:
        status = _STATUS.get(verdict, "unknown")
        block = f'      status: "{status}"\n      status_checked_at: "{stamp}"\n'
        if detail:
            safe = re.sub(r"\s+", " ", detail).replace('"', "'")[:120]
            block += f'      status_detail: "{safe}"\n'

        # ลบของเดิมก่อน แล้วแทรกใหม่ต่อจาก tags
        pat_old = re.compile(
            r"(- model_name: " + re.escape(model) + r"\n(?:.*?\n)*?)"
            r"(?:      status: \"[^\"]*\"\n)?"
            r"(?:      status_checked_at: \"[^\"]*\"\n)?"
            r"(?:      status_detail: \"[^\"]*\"\n)?"
            r"(      tags: \[[^\]]*\]\n)"
        )
        new, n = pat_old.subn(lambda m: m.group(1) + m.group(2) + block, text, count=1)
        if n:
            text = new
            written += 1

    path.write_text(text)
    print(f"\nเขียน status กลับเข้า config แล้ว {written} ตัว (เวลา {stamp})")
    print("⚠️  ต้อง restart litellm ถึงจะเห็นใน /model/info:")
    print("    docker compose restart litellm")


if __name__ == "__main__":
    raise SystemExit(main())
