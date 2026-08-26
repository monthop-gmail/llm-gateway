#!/usr/bin/env bash
# ช่วยเลือกโมเดลจาก gateway — 115 ตัวเลือกด้วยตาไม่ไหว
#
#   ./scripts/pick-model.sh                 # ดูหมวดทั้งหมด
#   ./scripts/pick-model.sh coding          # โมเดลที่เขียนโค้ดได้ดี
#   ./scripts/pick-model.sh thai            # โมเดลภาษาไทย
#   ./scripts/pick-model.sh web             # ค้นเว็บได้
#   ./scripts/pick-model.sh fast            # ตอบเร็ว
#   ./scripts/pick-model.sh no-key          # ใช้ได้โดยไม่ต้องมี API key
#   ./scripts/pick-model.sh quality         # คุณภาพสูงสุด
#   ./scripts/pick-model.sh long            # context ยาว
#   ./scripts/pick-model.sh embedding       # embeddings สำหรับ RAG
#   ./scripts/pick-model.sh agent           # เอาไปทำ agent ได้ (tool + 14K + โควต้าไหว)
#   ./scripts/pick-model.sh big-prompt      # รับ prompt 30K+ ได้จริง
#   ./scripts/pick-model.sh all             # ทุกตัวพร้อมรายละเอียด
#   ./scripts/pick-model.sh <คำค้น>          # ค้นจากชื่อหรือคำอธิบาย
#
# ข้อมูลอ่านจาก /model/info ของ gateway ที่รันอยู่ (ไม่ได้อ่านจาก config)
# จึงสะท้อนสิ่งที่ใช้ได้จริงตอนนี้
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
# shellcheck source=/dev/null
[ -f .env ] && source .env
set +a

URL="${LITELLM_URL:-http://localhost:4000}"
KEY="${LITELLM_MASTER_KEY:-}"

if [ -z "$KEY" ]; then
	echo "ต้องมี LITELLM_MASTER_KEY — ลอง: set -a; source .env; set +a" >&2
	exit 1
fi

raw=$(curl -sS --max-time 30 "$URL/model/info" -H "Authorization: Bearer $KEY") || {
	echo "ต่อ $URL ไม่ได้ — gateway รันอยู่ไหม (docker compose ps)" >&2
	exit 1
}

query="${1:-}"

echo "$raw" | QUERY="$query" python3 -c '
import json, os, sys

rows = json.load(sys.stdin).get("data", [])
q = os.environ.get("QUERY", "").strip().lower()

# แผนที่คำสั่งสั้น -> tag จริงใน model_info
GROUPS = {
    "coding":    (["coding-best"], "เขียนโค้ดได้ครบ 3/3 ในการทดสอบ"),
    "coding-ok": (["coding-ok"], "เขียนโค้ดได้ 2/3"),
    "thai":      (["thai"], "โมเดลภาษาไทย/อาเซียน"),
    "web":       (["web-access"], "ค้นเว็บหรือเปิด URL ได้"),
    "fast":      (["fast"], "ตอบเร็วกว่า 800ms"),
    "no-key":    (["no-api-key"], "ใช้ได้โดยไม่ต้องมี API key"),
    "quality":   (["quality-top"], "คุณภาพสูงสุด (frontier)"),
    "long":      (["long-context"], "context ยาว 512K ขึ้นไป"),
    "embedding": (["embedding"], "embeddings สำหรับ RAG"),
}

# หมวดที่ไม่ได้ดูจาก tag แต่ดูจากผลวัดจริง
#
# กัน answered_by ด้วย ไม่งั้นตัวที่ตัวสำรองตอบแทนจะยกเลขของตัวสำรองมาโชว์
# และเพราะหมวดนี้เรียงจาก vmp มากไปน้อย มันจะไปนั่งอยู่หัวตารางพอดี
def _big_prompt(r):
    return ((info(r).get("verified_max_prompt") or 0) >= 30_000
            and not info(r).get("answered_by"))

# เกณฑ์ "เอาไปทำ agent ได้" ตามที่ hermes ขอมาใน issue #3 ข้อ 5
#
# ใช้ 13,300 ไม่ใช่ 14,000 ตามที่ขอ เพราะ verified_max_prompt เป็นค่า
# "อย่างน้อยเท่านี้" ไม่ใช่เพดาน — ตัวที่ผ่านขั้น 14K แล้วไปพังที่ขั้น 32K
# จะได้เลข ~13,6xx-13,9xx เสมอ (นั่นคือ prompt_tokens จริงของขั้น 14K)
# ถ้าตัดที่ 14,000 ตรง ๆ จะตกหล่น 16 ตัวรวมทั้ง cb/* ที่เป็น tier เร็วสุด
AGENT_FLOOR = 13_300

def _agent_ready(r):
    mi = info(r)
    return (mi.get("supports_function_calling") is True
            and mi.get("status") in (None, "ok")
            and (mi.get("verified_max_prompt") or 0) >= AGENT_FLOOR
            # rpm-only = จำกัดต่อนาที agent ยิงถี่จะชนก่อนใคร
            and mi.get("quota_window") != "rpm-only"
            # answered_by = ชื่อนี้ไม่ได้ตอบเอง ตัวสำรองตอบแทน — ตัวเลขที่
            # วัดผ่านชื่อนี้จึงเป็นของตัวสำรอง ไม่ใช่ของโมเดลที่ขอ
            and not mi.get("answered_by"))

def info(r):
    return r.get("model_info") or {}

def fmt(r, show_all=False):
    mi = info(r)
    name = r.get("model_name", "?")
    bits = []
    if mi.get("benchmark_coding"):
        bits.append("coding " + mi["benchmark_coding"])
    if mi.get("latency_ms_14k"):
        bits.append(str(mi["latency_ms_14k"]) + "ms @14K")
    elif mi.get("latency_ms"):
        bits.append(str(mi["latency_ms"]) + "ms (prompt สั้น)")
    if mi.get("supports_function_calling") is False:
        bits.append("ไม่รองรับ tool")
    cap = mi.get("verified_max_prompt")
    if cap:
        # ≥ ไม่ใช่ ≤ — เลขนี้คือขนาดที่ยิงผ่านแล้ว เพดานจริงอยู่สูงกว่านี้
        # และบางตัวหยุดเพราะโควต้าหมดกลางคัน ไม่ใช่เพราะชนเพดาน
        bits.append(f"prompt ≥{cap//1000}K")
    ans = mi.get("answered_by")
    if ans:
        bits.append("จริง ๆ ตอบโดย " + ans)
    st = mi.get("status")
    if st and st != "ok":
        bits.append({"rate_limited": "โควต้าหมดตอนนี้", "dead": "ตายแล้ว"}.get(st, st))
    head = "  " + name.ljust(26)
    if bits:
        head += "(" + ", ".join(bits) + ")"
    out = [head]
    d = mi.get("description", "")
    if d:
        out.append("      " + d)
    if show_all and mi.get("provider_quota"):
        out.append("      โควต้า: " + mi["provider_quota"])
    if show_all and mi.get("max_prompt_detail"):
        out.append("      เพดาน prompt: " + mi["max_prompt_detail"])
    if show_all and mi.get("verified_by"):
        out.append("      ยืนยันโดย: " + mi["verified_by"])
    if show_all and mi.get("status_checked_at"):
        st = mi.get("status", "?")
        line = "      สถานะ: " + st + " (ตรวจ " + mi["status_checked_at"] + ")"
        if mi.get("status_detail"):
            line += " — " + mi["status_detail"][:70]
        out.append(line)
    return "\n".join(out)

if not q:
    print("เลือกหมวด:\n")
    for k, (tags, desc) in GROUPS.items():
        n = sum(1 for r in rows if set(tags) & set(info(r).get("tags", [])))
        print(f"  {k:<11} {n:>3} ตัว   {desc}")
    n = sum(1 for r in rows if _agent_ready(r))
    print(f"  agent       {n:>3} ตัว   ใช้ tool ได้ + ยังไม่ตาย + รับ 14K + โควต้าไม่จำกัดต่อนาที")
    n = sum(1 for r in rows if _big_prompt(r))
    print(f"  big-prompt  {n:>3} ตัว   ยิง prompt 30K+ ผ่านจริง (ไม่ใช่แค่สเปก)")
    print(f"\n  all         {len(rows):>3} ตัว   ทุกตัวพร้อมรายละเอียด")
    print("\nใช้: ./scripts/pick-model.sh <หมวด>  หรือใส่คำค้นอะไรก็ได้")
    sys.exit(0)

if q == "agent":
    hits = sorted((r for r in rows if _agent_ready(r)),
                  key=lambda r: info(r).get("latency_ms_14k")
                  or info(r).get("latency_ms") or 10 ** 9)
    print(f"เอาไปทำ agent ได้ — {len(hits)} ตัว (เรียงตามเวลาตอบที่ prompt 14K)\n")
    for r in hits:
        print(fmt(r, show_all=True))
        print()
    # เกณฑ์ 4 ข้อบอกไม่ได้ว่าโควต้า "ใหญ่พอให้ agent ยิงทั้งวัน" ไหม
    # เพราะ quota_window เป็นแค่หน่วยเวลา ไม่ใช่ขนาด — okmd ที่มี ~40K/วัน
    # กับ cerebras ที่มี ~1M/วัน เขียนว่า daily เหมือนกัน จึงสรุปโควต้าให้ดูเอง
    pools = {}
    for r in hits:
        m = info(r)
        key = m.get("quota_pool") or "?"
        pools.setdefault(key, [0, m.get("provider_quota") or ""])
        pools[key][0] += 1
    print("โควต้าของแต่ละก้อน — agent ยิงถี่ ให้ดูข้อนี้ก่อนตัดสินใจ:\n")
    for key, (n, quota) in sorted(pools.items(), key=lambda kv: -kv[1][0]):
        print(f"  {key:<16} {n:>2} ตัว   {quota[:78]}")
    print("\n  ตัวที่อยู่ก้อนเดียวกันหมดโควต้าพร้อมกัน — เลือกตัวสำรองข้ามก้อนเสมอ")
    sys.exit(0)

if q == "big-prompt":
    hits = sorted((r for r in rows if _big_prompt(r)),
                  key=lambda r: -info(r)["verified_max_prompt"])
    print(f"ยิง prompt 30K+ ผ่านจริง — {len(hits)} ตัว\n")
    for r in hits:
        print(fmt(r, show_all=True))
        print()
    sys.exit(0)

if q == "all":
    for r in sorted(rows, key=lambda x: x.get("model_name", "")):
        print(fmt(r, show_all=True))
    sys.exit(0)

if q in GROUPS:
    tags, desc = GROUPS[q]
    hits = [r for r in rows if set(tags) & set(info(r).get("tags", []))]
    # ตัวที่ตรวจแล้วว่าใช้ไม่ได้ตอนนี้ เอาลงไปท้ายสุด ไม่ซ่อน เพราะโควต้าเดี๋ยวก็คืน
    down = [r for r in hits if info(r).get("status") in ("dead", "rate_limited")]
    hits = [r for r in hits if r not in down]
    # เรียงตามเวลาที่วัดได้ เร็วก่อน
    hits.sort(key=lambda r: info(r).get("benchmark_seconds") or info(r).get("latency_ms", 0) / 1000 or 999)
    print(f"{desc} — {len(hits)} ตัวที่ใช้ได้ตอนนี้\n")
    for r in hits:
        print(fmt(r, show_all=True))
        print()
    if down:
        print(f"อีก {len(down)} ตัวในหมวดนี้ตรวจแล้วใช้ไม่ได้ตอนนี้:")
        for r in down:
            mi = info(r)
            name = r.get("model_name", "?")
            det = (mi.get("status_detail") or "")[:60]
            print(f"  {name:<26} {mi.get("status")} — {det}")
    sys.exit(0)

# ค้นอิสระจากชื่อ + คำอธิบาย + tag
hits = [r for r in rows
        if q in r.get("model_name", "").lower()
        or q in info(r).get("description", "").lower()
        or any(q in t for t in info(r).get("tags", []))]
if not hits:
    print(f"ไม่เจอโมเดลที่ตรงกับ \"{q}\" — ลองรันโดยไม่ใส่อะไรเพื่อดูหมวดทั้งหมด")
    sys.exit(1)
print(f"ตรงกับ \"{q}\" — {len(hits)} ตัว\n")
for r in sorted(hits, key=lambda x: x.get("model_name", "")):
    print(fmt(r, show_all=True))
    print()
'
