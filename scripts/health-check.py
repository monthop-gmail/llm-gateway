#!/usr/bin/env python3
"""ยิงทุกโมเดลใน gateway เพื่อหาว่าตัวไหนใช้ไม่ได้ และเพราะอะไร

    set -a; source .env; set +a
    python3 scripts/health-check.py              # ตรวจทุกตัว
    python3 scripts/health-check.py gq/ cb/      # ตรวจเฉพาะ prefix ที่ระบุ
    python3 scripts/health-check.py --write      # เขียนผลกลับเข้า model_info

วัดด้วย "disable_fallbacks": true เพื่อให้เห็นสุขภาพของโมเดลตัวนั้นจริง ๆ
ไม่ใช่ของตัวสำรอง — ถ้าไม่ปิด LiteLLM จะเงียบ ๆ ส่งไป provider อื่นแล้วเรารายงาน
ว่า "ok" ทั้งที่โมเดลนั้นตายไปแล้ว (เจอจริงกับ hf/* ทั้ง 21 ตัวที่เครดิตหมด
แต่ยังขึ้นว่า ok เพราะ fallback ทำงาน)

ตัวที่ตายแล้วจะถูกยิงซ้ำอีกครั้งแบบเปิด fallback เพื่อบันทึก answered_by
= โมเดลที่ตอบให้จริงตอนนี้ ปลายทางจะได้รู้ว่าขอ A แล้วได้ B

แยกสาเหตุที่ล้มเหลวออกเป็น 2 กลุ่ม เพราะวิธีแก้ต่างกันสิ้นเชิง:

  ตายถาวร  — โมเดลถูกปลด/เปลี่ยนเป็นเสียเงิน ตัวที่ยังมี fallback รับอยู่ให้เก็บไว้
             เป็น alias ได้ ตัวที่ไม่มีอะไรรับต้องแก้ litellm/config.yaml
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
from config_edit import set_fields
from failure_hints import classify

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


def check(model: str, allow_fallback: bool = False) -> tuple[str, str, str, str]:
    """คืน (model, ผลตรวจ, ข้อความ error, ชื่อโมเดลที่ตอบจริง)"""
    is_embedding = model.startswith("emb/")
    try:
        if is_embedding:
            data = _post("/v1/embeddings", {"model": model, "input": ["hi"]})
        else:
            body = {
                "model": model,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 10,
            }
            if not allow_fallback:
                # ไม่งั้นวัดสุขภาพของตัวสำรอง ไม่ใช่ของโมเดลที่ขอ
                body["disable_fallbacks"] = True
            data = _post("/v1/chat/completions", body)
        return model, "OK", "", str(data.get("model") or "")
    except Exception as exc:
        msg = _error_text(exc)
        return model, classify(msg), msg[:110], ""


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

    print(f"ตรวจ {len(models)} โมเดลผ่าน {BASE} (ปิด fallback เพื่อวัดตัวจริง)\n")
    results: list[tuple[str, str, str, str]] = []
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        for model, status, msg, _ in pool.map(check, models):
            print("." if status == "OK" else "X", end="", flush=True)
            results.append((model, status, msg, ""))

    # รอบสอง: ตัวที่ตัวเองใช้ไม่ได้ อาจยังตอบได้ผ่าน fallback — ปลายทางควรรู้ว่าได้ใครแทน
    broken = [i for i, r in enumerate(results) if r[1] != "OK"]
    if broken:
        print(f"\n\nตรวจซ้ำ {len(broken)} ตัวแบบเปิด fallback เพื่อดูว่าใครตอบแทน")
        with futures.ThreadPoolExecutor(max_workers=8) as pool:
            # strict=True: สองลิสต์ต้องยาวเท่ากันเสมอ ถ้าไม่เท่าแปลว่ามีบั๊ก
            # อยากให้ระเบิดดังกว่าจับคู่ผิดเงียบ ๆ แล้วเขียน answered_by ผิดตัว
            for idx, out in zip(broken, pool.map(
                    lambda m: check(m, allow_fallback=True),
                    [results[i][0] for i in broken]), strict=True):
                _, st, _, answered = out
                print("." if st == "OK" else "X", end="", flush=True)
                # ตอบด้วยชื่อเดิม = รอบแรกพังชั่วคราว (timeout/สะดุด) ไม่ใช่ถูกสลับตัว
                if st == "OK" and answered and answered != results[idx][0]:
                    m, s_, d_, _ = results[idx]
                    results[idx] = (m, s_, d_, answered)

    ok = [r for r in results if r[1] == "OK"]
    print(f"\n\nใช้ได้ {len(ok)} / ทั้งหมด {len(results)}")

    aliased = [r for r in results if r[3]]
    if aliased:
        print(f"\n{len(aliased)} ตัวใช้ไม่ได้ด้วยตัวเอง แต่ fallback ตอบแทนอยู่"
              "  ← ปลายทางขอ A ได้ B")
        for model, _, _, answered in aliased:
            print(f"  {model:<24} → {answered}")

    for group in ("ตายถาวร", "โควต้าหมด", "timeout", "อื่นๆ"):
        rows = [r for r in results if r[1] == group]
        if not rows:
            continue
        note = {
            "ตายถาวร": "  ← ดูข้างล่างว่าต้องแก้ config หรือเก็บเป็น alias ได้",
            "โควต้าหมด": "  ← รอ reset แล้วกลับมาเอง",
            "timeout": "  ← provider ช้าหรือล่ม ลองใหม่ทีหลัง",
        }.get(group, "")
        print(f"\n{group} ({len(rows)}){note}")
        for model, _, msg, _ in rows:
            print(f"  {model:<24} {msg}")

    if "--write" in sys.argv:
        _write_back(results)

    # exit 1 = "มีของตายที่ไม่มีอะไรรองรับ" ไม่ใช่แค่ "มีของตาย"
    #
    # โมเดลที่ตายแล้วยังอยู่ใน config โดยตั้งใจ (ดู INTEGRATION.md) ถ้าให้ exit 1
    # ทุกครั้งที่เจอของตาย สัญญาณจะแดงค้างถาวรแล้วไม่มีใครสนใจอีก พอมีตัวใหม่
    # ตายจริงก็จะไม่มีใครเห็น จึงแดงเฉพาะตอนที่ชื่อนั้นชี้ไปไม่ถึงอะไรเลย
    orphan = [r for r in results if r[1] == "ตายถาวร" and not r[3]]
    if orphan:
        print(f"\n❌ {len(orphan)} ตัวตายแล้วและไม่มีตัวสำรองรับ — ยิงแล้วพังทันที")
        for model, _, _, _ in orphan:
            print(f"  {model}")
        print("  แก้ litellm/config.yaml: เพิ่ม fallback ให้ หรือเอาออกจากลิสต์")
        return 1

    dead_ok = [r for r in results if r[1] == "ตายถาวร"]
    if dead_ok:
        print(f"\n{len(dead_ok)} ตัวตายแล้วแต่ตัวสำรองยังรับอยู่ — เก็บไว้เป็น alias ได้")
    return 0


# แปลงผลตรวจเป็นค่า status ที่ consumer ใช้กรองได้
_STATUS = {
    "OK": "ok",
    "โควต้าหมด": "rate_limited",
    "ตายถาวร": "dead",
    "ชนเพดาน": "ok",   # ตอบ error เรื่องความยาวได้ = โมเดลยังมีชีวิต
    "timeout": "unknown",
    "อื่นๆ": "unknown",
}


def _write_back(results: list[tuple[str, str, str, str]]) -> None:
    """เขียน status กลับเข้า model_info ของ config.yaml"""
    from datetime import datetime, timezone

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = ROOT / "litellm/config.yaml"
    text = path.read_text()
    written = 0

    for model, verdict, detail, answered in results:
        text, ok = set_fields(text, model, {
            "status": _STATUS.get(verdict, "unknown"),
            "status_checked_at": stamp,
            "status_detail": detail[:120] if detail else None,
            "answered_by": answered or None,
        })
        written += ok

    path.write_text(text)
    print(f"\nเขียน status กลับเข้า config แล้ว {written} ตัว (เวลา {stamp})")
    print("⚠️  ต้อง restart litellm ถึงจะเห็นใน /model/info:")
    print("    docker compose restart litellm")


if __name__ == "__main__":
    raise SystemExit(main())
