#!/usr/bin/env python3
"""วัดเวลาตอบจริงด้วย prompt ขนาดที่ agent ใช้ ไม่ใช่ prompt สั้น ๆ

    set -a; source .env; set +a
    python3 scripts/probe-latency-14k.py              # ทุกตัวที่ผ่านเกณฑ์
    python3 scripts/probe-latency-14k.py mi/ cb/      # เฉพาะ prefix
    python3 scripts/probe-latency-14k.py --write      # เขียนผลกลับเข้า model_info

ทำไมต้องมี: `latency_ms` ที่มีอยู่วัดจาก call เดี่ยวด้วย prompt สั้น ซึ่งใช้
ตัดสินใจแทน agent ไม่ได้ — hermes รายงานใน issue #3 ว่าต่างจากของจริง 35-180 เท่า
และ **เรียงลำดับไม่ตรงกันด้วย**:

    mi/magistral-medium   latency_ms 1,282  แต่ช้ากว่า mi/large ในสภาพจริง

เพราะ reasoning model ยิ่ง prompt ใหญ่ยิ่งคิดนาน — ความต่างนี้โผล่เฉพาะตอน
prompt ใหญ่ ซึ่งเป็นสภาพปกติของ agent ที่ยัด system prompt + tool schemas
เข้าไปทุก call

วิธีวัด: ยิง prompt ~14K tokens แล้วจับเวลาจนได้คำตอบครบ ทำ RUNS ครั้ง
เอาค่า **ต่ำสุด** (ไม่ใช่ค่าเฉลี่ย) เพราะเราต้องการ "เร็วสุดที่ทำได้"
ไม่ใช่ค่าที่ถูกรบกวนด้วยคิวของ provider ณ นาทีนั้น

⚠️ กินโควต้า — แต่ละ call กิน ~14K tokens เท่ากับการคุยปกติหลายครั้ง
ค่า default วัดเฉพาะตัวที่ `status=ok` และ `verified_max_prompt >= 14000`
เพื่อไม่ยิงตัวที่รู้อยู่แล้วว่าจะพัง ให้เลือก prefix เอาถ้าจะรันซ้ำบ่อย
อย่าตั้ง cron

⚠️ ค่าที่ได้ยังเป็น "call เดียว" อยู่ — turn จริงของ agent มีหลาย call ต่อกัน
และ context โตขึ้นเรื่อย ๆ เลขนี้จึงเป็น "พื้น" ที่เปรียบเทียบข้ามโมเดลได้
ไม่ใช่เวลาที่ผู้ใช้จะรอจริง
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from failure_hints import classify  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "litellm/config.yaml"
BASE = os.environ.get("LITELLM_URL", "http://localhost:4000")
KEY = os.environ.get("LITELLM_MASTER_KEY")

TARGET_TOKENS = 14_000
RUNS = int(os.environ.get("LATENCY_RUNS", "2"))
MAX_OUTPUT = 200          # ให้ยาวพอที่ reasoning model จะได้พ้นช่วงคิดก่อนตอบ
TIMEOUT = 300             # เผื่อ reasoning model ที่ช้ามาก
# วัดจากของจริง: filler อังกฤษชุดนี้ได้ ~5.9 ตัวอักษรต่อ token
# (ยิงครั้งแรกด้วย 4.0 แล้วได้ prompt_tokens 9,428 จากเป้า 14,000 — ปรับตามผลจริง)
# สคริปต์รายงาน prompt_tokens ที่ provider นับเองทุกครั้ง จะได้ตรวจได้ว่าตรงเป้าไหม
CHARS_PER_TOKEN = 5.9

FILLER = (
    "The deployment pipeline validates each service before promoting it to the "
    "next environment, and the audit log records every change with a timestamp. "
)
ASK = "ตอบสั้น ๆ ว่า 'รับทราบ' ถ้าคุณอ่านข้อความข้างบนแล้ว"


def _post(body: dict, timeout: int = TIMEOUT) -> dict:
    req = urllib.request.Request(
        BASE + "/v1/chat/completions",
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


def _filler(target_tokens: int) -> str:
    n = int(target_tokens * CHARS_PER_TOKEN)
    return (FILLER * (n // len(FILLER) + 1))[:n]


def probe(model: str) -> tuple[str, int | None, str, int | None]:
    """คืน (model, ms ต่ำสุด, note, prompt_tokens ที่ provider นับ)"""
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": _filler(TARGET_TOKENS)},
            {"role": "user", "content": ASK},
        ],
        "max_tokens": MAX_OUTPUT,
    }
    best: int | None = None
    ptok: int | None = None
    for i in range(RUNS):
        t0 = time.monotonic()
        try:
            data = _post(body)
        except Exception as exc:                      # noqa: BLE001
            msg = _error_text(exc)
            kind = classify(msg)
            # โควต้าหมด = วัดไม่ได้ตอนนี้ ไม่ใช่คุณสมบัติของโมเดล — อย่าบันทึกเลข
            return model, None, kind, None
        ms = int((time.monotonic() - t0) * 1000)
        best = ms if best is None else min(best, ms)
        ptok = ptok or (data.get("usage") or {}).get("prompt_tokens")
        # ตอบว่างแต่ไม่ error เจอกับ reasoning model ที่ max_tokens หมดไปกับการคิด
        choice = (data.get("choices") or [{}])[0]
        if not (choice.get("message") or {}).get("content"):
            return model, best, "content ว่าง (finish=%s)" % choice.get("finish_reason"), ptok
        if i + 1 < RUNS:
            time.sleep(1.0)                            # กันชน rate limit ระหว่างรอบ
    return model, best, "", ptok


def _candidates(prefixes: list[str]) -> list[str]:
    cfg = yaml.safe_load(CFG.read_text())
    out = []
    for entry in cfg["model_list"]:
        name = entry["model_name"]
        mi = entry.get("model_info") or {}
        if prefixes and not any(name.startswith(p) for p in prefixes):
            continue
        if not prefixes:
            # ชุด default: เฉพาะตัวที่รู้แล้วว่ายังไม่ตายและรับ 14K ไหว
            if mi.get("status") not in (None, "ok"):
                continue
            vmp = mi.get("verified_max_prompt")
            if not isinstance(vmp, int) or vmp < TARGET_TOKENS:
                continue
            if str(mi.get("max_prompt_detail", "")).startswith("โควต้า"):
                continue      # เลขวัดไม่จบ เชื่อไม่ได้ (ดู probe-context.py)
        out.append(name)
    return out


def _write_back(results: list[tuple[str, int | None, str, int | None]]) -> None:
    lines = CFG.read_text().split("\n")
    wrote = 0
    for model, ms, note, _ in results:
        if ms is None or note:
            continue
        for i, line in enumerate(lines):
            if line.strip() == f"- model_name: {model}":
                for j in range(i, min(i + 40, len(lines))):
                    if lines[j].strip() == "model_info:":
                        ind = len(lines[j + 1]) - len(lines[j + 1].lstrip())
                        k = j + 1
                        while k < len(lines) and lines[k].strip() and (
                            len(lines[k]) - len(lines[k].lstrip())
                        ) >= ind:
                            k += 1
                        new = f"{' ' * ind}latency_ms_14k: {ms}"
                        hit = next(
                            (x for x in range(j + 1, k)
                             if lines[x].strip().startswith("latency_ms_14k:")), None)
                        if hit is not None:
                            lines[hit] = new
                        else:
                            lines.insert(k, new)
                        wrote += 1
                        break
                break
    CFG.write_text("\n".join(lines))
    print(f"\nเขียนกลับ {wrote} โมเดล → {CFG.relative_to(ROOT)}")


def main() -> int:
    if not KEY:
        print("ต้องมี LITELLM_MASTER_KEY (set -a; source .env; set +a)", file=sys.stderr)
        return 2
    prefixes = [a for a in sys.argv[1:] if not a.startswith("--")]
    models = _candidates(prefixes)
    print(f"วัด {len(models)} โมเดล · prompt ~{TARGET_TOKENS:,} tokens · {RUNS} รอบ เอาค่าต่ำสุด\n")
    print(f"{'model':<26}{'ms (14K)':>10}  {'prompt_tokens':>13}  note")
    print("-" * 74)
    results = []
    for m in models:
        r = probe(m)
        results.append(r)
        _, ms, note, ptok = r
        print(f"{m:<26}{(ms if ms is not None else '-'):>10}  "
              f"{(f'{ptok:,}' if ptok else '-'):>13}  {note}")
        time.sleep(1.0)
    ok = [r for r in results if r[1] is not None and not r[2]]
    print(f"\nวัดได้ {len(ok)}/{len(results)} ตัว")
    if ok:
        slow = max(ok, key=lambda r: r[1])
        fast = min(ok, key=lambda r: r[1])
        print(f"เร็วสุด {fast[0]} ({fast[1]:,} ms) · ช้าสุด {slow[0]} ({slow[1]:,} ms) "
              f"— ต่างกัน {slow[1] / max(fast[1], 1):.0f} เท่า")
    if "--write" in sys.argv:
        _write_back(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
