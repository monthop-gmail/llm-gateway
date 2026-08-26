#!/usr/bin/env python3
"""หาว่าแต่ละโมเดลรับ prompt ได้ยาวจริงเท่าไหร่ ไม่ใช่ตามสเปกที่ provider โฆษณา

    set -a; source .env; set +a
    python3 scripts/probe-context.py              # ตรวจทุกตัวที่ status=ok
    python3 scripts/probe-context.py cf/ gq/      # เฉพาะ prefix
    python3 scripts/probe-context.py --write      # เขียนผลกลับเข้า model_info

ทำไมต้องมี: hermes รายงานมาใน issue #3 ว่าเลขที่โฆษณาไว้เชื่อไม่ได้ —
บาง provider โฆษณา 128K แต่พอยิงจริงที่ 32K ก็ 500 แล้ว ส่วน coding agent
ยัด context ทั้งโปรเจกต์เข้าไปทุก turn จึงชนเพดานนี้เป็นเรื่องปกติ

วิธีวัด: ไต่ขนาดขึ้นทีละขั้น หยุดที่ขั้นแรกที่พัง แล้วบันทึกขั้นสุดท้ายที่ผ่าน
ค่าที่ได้เป็น prompt_tokens ที่ provider นับเองจาก usage ในคำตอบ ไม่ใช่ที่เราเดา

⚠️ สคริปต์นี้กินโควต้าหนักมาก — prompt ขนาด 128K หนึ่งครั้งเท่ากับการคุยปกติ
หลายสิบครั้ง ตอนรันเต็มชุดครั้งแรก (2026-08-26) มันใช้โควต้าวันของ Cloudflare
จนหมดเกลี้ยงทั้ง 13 โมเดล ให้รันเฉพาะเวลาที่ต้องการจริง ๆ และเลือก prefix เอา
อย่าตั้ง cron

วัดด้วย `disable_fallbacks: true` เสมอ — ไม่งั้นได้เพดานของตัวสำรองมาแทน

ที่สำคัญกว่าตัวเลขคือ "พังยังไง" — 429 แปลว่าโควต้าหมด รอแล้วยิงใหม่ได้
ส่วน 400/500 แปลว่าชนเพดานจริง เก็บไว้ใน max_prompt_detail ทั้งคู่
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
from config_edit import set_fields
from failure_hints import classify

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "litellm/config.yaml"
BASE = os.environ.get("LITELLM_URL", "http://localhost:4000")
KEY = os.environ.get("LITELLM_MASTER_KEY")

# ขั้นที่ไต่ — 14K คือขนาดที่ hermes บอกว่า turn จริงของเขาใช้
LADDER = [4_000, 14_000, 32_000, 64_000, 128_000]

# ข้อความถมให้ยาว ใช้คำอังกฤษธรรมดาเพื่อให้อัตรา token ต่อคำใกล้เคียงของจริง
FILLER = (
    "The deployment pipeline validates each service before promoting it to the "
    "next environment, and the audit log records every change with a timestamp. "
)


def _post(path: str, body: dict, timeout: int = 180) -> dict:
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
    for cut in ("No fallback", "Received Model Group", "Available Model Group"):
        raw = raw.split(cut)[0]
    return raw.strip()


def _why(exc: Exception, msg: str) -> str:
    """แยกให้ชัดว่าพังเพราะยาวเกิน หรือเพราะเหตุอื่นที่ไม่เกี่ยวกับความยาว

    ห้ามตัดสินจาก HTTP code — Cloudflare ส่ง 500 ตอนโควต้าหมด และ OKMD ส่ง 401
    ต้องอ่านข้อความเท่านั้น (ดู scripts/failure_hints.py)
    """
    kind = classify(msg)
    if kind == "โควต้าหมด":
        return "โควต้า"      # ยังไม่รู้เพดาน ต้องมาวัดใหม่ตอนโควต้าคืน
    if kind in ("ชนเพดาน", "timeout"):
        return kind
    code = exc.code if isinstance(exc, urllib.error.HTTPError) else None
    return f"error {code or '?'}"


def _prompt(target_tokens: int, chars_per_token: float) -> str:
    n = int(target_tokens * chars_per_token)
    return (FILLER * (n // len(FILLER) + 1))[:n]


def probe(model: str, ceiling: int | None) -> tuple[str, int, str, int]:
    """คืน (model, token ที่ผ่านมากที่สุด, คำอธิบายว่าหยุดเพราะอะไร, ขั้นที่ผ่าน)"""
    best, detail, rung = 0, "", 0
    # เริ่มด้วยการเดา แล้วปรับจากที่ provider นับจริง — tokenizer แต่ละเจ้าไม่เท่ากัน
    # ถ้าไม่ปรับ ขั้น "14K" จะยิงจริงแค่ ~9K แล้วเราจะสรุปผิดว่าโมเดลรับไม่ไหว
    cpt = 4.0
    for size in LADDER:
        # ไม่ต้องยิงเกินที่ provider โฆษณาไว้ เปลืองโควต้าเปล่า
        if ceiling and size > ceiling:
            detail = detail or f"ไม่ได้ลองเกิน {best:,} เพราะสเปกบอกแค่ {ceiling:,}"
            break
        try:
            r = _post("/v1/chat/completions", {
                "model": model,
                # ไม่งั้นพอโมเดลตัวจริงพัง LiteLLM จะสลับไปตัวสำรองเงียบ ๆ
                # แล้วเราบันทึกเพดานของตัวสำรองใส่ชื่อโมเดลนี้
                "disable_fallbacks": True,
                "messages": [
                    {"role": "user", "content": _prompt(size, cpt)},
                    {"role": "user", "content": "ตอบสั้น ๆ ว่าข้อความข้างบนพูดถึงอะไร"},
                ],
                "max_tokens": 20,
            })
            # เอาเลขที่ provider นับเอง ไม่ใช่ที่เราเดา
            got = (r.get("usage") or {}).get("prompt_tokens")
            if got:
                best = got
                cpt = max(1.0, min(8.0, cpt * size / got))  # ปรับให้ขั้นถัดไปตรงขึ้น
            else:
                best = size  # provider ไม่ส่ง usage มา ใช้ค่าที่ตั้งใจยิงไปแทน
            rung = size
        except Exception as exc:
            msg = _error_text(exc)
            detail = f"{_why(exc, msg)} ที่ ~{size:,} — {msg[:80]}"
            break
    else:
        detail = f"ผ่านทุกขั้นถึง {best:,} (ไม่ได้ลองมากกว่านี้)"
    return model, best, detail, rung


def main() -> int:
    if not KEY:
        print("ต้องตั้ง LITELLM_MASTER_KEY ก่อน — ลอง: set -a; source .env; set +a", file=sys.stderr)
        return 1

    cfg = yaml.safe_load(CFG.read_text())
    targets = []
    for m in cfg["model_list"]:
        name, mi = m["model_name"], m.get("model_info") or {}
        if mi.get("mode") == "embedding" or name.startswith("emb/"):
            continue
        # ตัวที่รู้อยู่แล้วว่าโควต้าหมด/ตาย ยิงไปก็ได้แค่ 429 เปลืองเวลา
        if mi.get("status") in ("dead", "rate_limited"):
            continue
        targets.append((name, mi.get("max_input_tokens")))

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        targets = [t for t in targets if t[0].startswith(tuple(args))]
    if not targets:
        print("ไม่มีโมเดลให้ตรวจ (อาจถูกกรองออกหมดเพราะ status ไม่ ok)", file=sys.stderr)
        return 1

    print(f"ไต่ขนาด prompt {LADDER[0]:,}→{LADDER[-1]:,} token กับ {len(targets)} โมเดล\n")
    results: list[tuple[str, int, str, int]] = []
    # ยิงพร้อมกันไม่เยอะ เพราะ prompt ใหญ่กินโควต้าเร็วกว่าปกติมาก
    with futures.ThreadPoolExecutor(max_workers=4) as pool:
        for res in pool.map(lambda t: probe(*t), targets):
            print("." if res[3] >= 14_000 else "x", end="", flush=True)
            results.append(res)

    results.sort(key=lambda r: -r[1])
    print("\n\nเรียงจากรับได้มากไปน้อย:\n")
    for model, best, detail, rung in results:
        mark = " " if rung >= 14_000 else "!"
        print(f"{mark} {model:<24} {best:>8,}  {detail}")

    thin = [r for r in results if r[3] < 14_000]
    if thin:
        print(f"\n! {len(thin)} ตัวรับไม่ถึง 14K token — coding agent ที่ยัดทั้งโปรเจกต์เข้าไปจะพัง")

    if "--write" in sys.argv:
        _write_back(results)
    return 0


def _write_back(results: list[tuple[str, int, str, int]]) -> None:
    text = CFG.read_text()
    written = 0
    for model, best, detail, _rung in results:
        if not best:
            continue  # ยังไม่รู้อะไรเลย อย่าเขียนเลขหลอก
        text, ok = set_fields(text, model, {
            "verified_max_prompt": best,
            "max_prompt_detail": detail[:120] if detail else None,
        })
        written += ok
    CFG.write_text(text)
    print(f"\nเขียน verified_max_prompt กลับเข้า config แล้ว {written} ตัว")
    print("⚠️  ต้อง restart litellm ถึงจะเห็นใน /model/info:")
    print("    docker compose restart litellm")


if __name__ == "__main__":
    raise SystemExit(main())
