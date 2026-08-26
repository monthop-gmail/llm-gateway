#!/usr/bin/env python3
"""วัดความสามารถเขียนโค้ดของโมเดลใน gateway — ตรวจผลอัตโนมัติ

    set -a; source .env; set +a
    python3 scripts/bench-coding.py cf/qwen2.5-coder-32b mi/codestral ...

โจทย์ 3 ข้อ: คำนวณนิพจน์ (parser + edge case), LRU cache แบบมี TTL (จัดการ state),
แก้บั๊กจากโค้ดที่ให้มา (งานที่ coding agent เจอบ่อยสุด)

โค้ดที่โมเดลเขียนถูกรันใน container แยก (--network none, จำกัด RAM 256MB)
ไม่ได้รันบนเครื่องโดยตรง ต้องมี image python:3.12-alpine
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

BASE = os.environ.get("LITELLM_URL", "http://localhost:4000") + "/v1/chat/completions"
KEY = os.environ["LITELLM_MASTER_KEY"]

ONLY_CODE = "\nตอบเฉพาะโค้ด Python ในบล็อก ```python ``` เท่านั้น ห้ามอธิบาย"

TASKS = [
    {
        "name": "expr",
        "prompt": (
            "เขียนฟังก์ชัน calc(s) ที่คำนวณนิพจน์คณิตศาสตร์จากสตริง "
            "รองรับ + - * / วงเล็บ เลขทศนิยม เลขติดลบ และลำดับความสำคัญที่ถูกต้อง "
            "หารด้วยศูนย์ให้ raise ValueError ห้ามใช้ eval หรือ exec" + ONLY_CODE
        ),
        "test": """
assert calc("1+2*3") == 7
assert calc("(1+2)*3") == 9
assert calc("2*(3+4)/7") == 2
assert calc("-5+3") == -2
assert calc("10/4") == 2.5
assert calc("2*(-3)") == -6
assert calc("((1+2)*(3+4))") == 21
try:
    calc("1/0"); raise SystemExit("ไม่ raise ValueError")
except ValueError: pass
""",
    },
    {
        "name": "lru_ttl",
        "prompt": (
            "เขียนคลาส LRUCacheTTL(capacity, ttl) ที่มีเมธอด get(key) กับ put(key, value) "
            "เก็บได้ไม่เกิน capacity ตัว เกินแล้วไล่ตัวที่ใช้ล่าสุดนานสุดออก "
            "และรายการที่เก่ากว่า ttl วินาทีถือว่าหมดอายุ get คืน None "
            "ใช้ time.monotonic() ในการจับเวลา" + ONLY_CODE
        ),
        "test": """
import time
c = LRUCacheTTL(2, 10)
c.put('a', 1); c.put('b', 2)
assert c.get('a') == 1
c.put('c', 3)          # 'b' ต้องถูกไล่ออก เพราะ 'a' เพิ่งถูกใช้
assert c.get('b') is None
assert c.get('a') == 1 and c.get('c') == 3
d = LRUCacheTTL(5, 0.05)
d.put('x', 9)
assert d.get('x') == 9
time.sleep(0.12)
assert d.get('x') is None
""",
    },
    {
        "name": "fixbug",
        "prompt": (
            "โค้ดนี้มีบั๊ก แก้ให้ถูกต้องแล้วส่งฟังก์ชันที่แก้แล้วกลับมา:\n\n"
            "```python\n"
            "def group_by_month(records):\n"
            "    # records: list ของ dict {'date': 'YYYY-MM-DD', 'amount': float}\n"
            "    # คืน dict {'YYYY-MM': ผลรวม amount} เรียง key จากน้อยไปมาก\n"
            "    out = {}\n"
            "    for r in records:\n"
            "        key = r['date'][:6]\n"
            "        out[key] = r['amount']\n"
            "    return out\n"
            "```" + ONLY_CODE
        ),
        "test": """
r = [{'date':'2026-01-15','amount':10.0},{'date':'2026-01-20','amount':5.5},
     {'date':'2026-02-01','amount':3.0},{'date':'2025-12-31','amount':1.0}]
got = group_by_month(r)
assert got == {'2025-12':1.0,'2026-01':15.5,'2026-02':3.0}, got
assert list(got.keys()) == ['2025-12','2026-01','2026-02'], list(got.keys())
assert group_by_month([]) == {}
""",
    },
]


def ask(model, prompt, timeout=300):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 3000, "temperature": 0,
        # วัดตัวจริง ไม่ใช่ตัวสำรอง — เคยได้คะแนน coding ของ mistral-code
        # ไปแปะให้ hf/qwen3-coder-next มาแล้ว
        "disable_fallbacks": True,
    }).encode()
    req = urllib.request.Request(BASE, data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return d["choices"][0]["message"].get("content") or "", time.time() - t0


def extract_code(text):
    m = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return max(m, key=len) if m else text


def sandbox(code, test):
    script = code + "\n\n" + test + "\nprint('PASS')\n"
    try:
        p = subprocess.run(
            ["docker", "run", "--rm", "-i", "--network", "none", "--memory", "256m",
             "python:3.12-alpine", "python", "-c", script],
            # check=False ตั้งใจ — โค้ดที่โมเดลเขียนแล้วรันไม่ผ่านคือผลการวัด
            # ไม่ใช่ข้อผิดพลาดของสคริปต์ เราดูที่ stdout ว่ามี PASS ไหม
            capture_output=True, text=True, timeout=90, check=False)
        return "PASS" in p.stdout
    except subprocess.TimeoutExpired:
        return False


def main():
    print(f"{'model':<24} {'expr':<6} {'lru':<6} {'fixbug':<8} {'คะแนน':<7} เวลา")
    print("-" * 66)
    rows = []
    for m in sys.argv[1:]:
        marks, tt = [], 0.0
        for task in TASKS:
            try:
                text, dt = ask(m, task["prompt"])
                tt += dt
                marks.append("✅" if sandbox(extract_code(text), task["test"]) else "❌")
            except Exception:
                marks.append("💥")
        score = marks.count("✅")
        rows.append((score, tt, m))
        print(f"{m:<24} {marks[0]:<6} {marks[1]:<6} {marks[2]:<8} {score}/3     {tt:.1f}s")
    print("-" * 66)
    for score, t, m in sorted(rows, key=lambda r: (-r[0], r[1])):
        print(f"  {score}/3  {t:6.1f}s  {m}")


if __name__ == "__main__":
    main()
