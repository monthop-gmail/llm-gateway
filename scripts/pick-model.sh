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

def info(r):
    return r.get("model_info") or {}

def fmt(r, show_all=False):
    mi = info(r)
    name = r.get("model_name", "?")
    bits = []
    if mi.get("benchmark_coding"):
        bits.append("coding " + mi["benchmark_coding"])
    if mi.get("latency_ms"):
        bits.append(str(mi["latency_ms"]) + "ms")
    if mi.get("supports_function_calling") is False:
        bits.append("ไม่รองรับ tool")
    head = "  " + name.ljust(26)
    if bits:
        head += "(" + ", ".join(bits) + ")"
    out = [head]
    d = mi.get("description", "")
    if d:
        out.append("      " + d)
    if show_all and mi.get("provider_quota"):
        out.append("      โควต้า: " + mi["provider_quota"])
    return "\n".join(out)

if not q:
    print("เลือกหมวด:\n")
    for k, (tags, desc) in GROUPS.items():
        n = sum(1 for r in rows if set(tags) & set(info(r).get("tags", [])))
        print(f"  {k:<11} {n:>3} ตัว   {desc}")
    print(f"\n  all         {len(rows):>3} ตัว   ทุกตัวพร้อมรายละเอียด")
    print("\nใช้: ./scripts/pick-model.sh <หมวด>  หรือใส่คำค้นอะไรก็ได้")
    sys.exit(0)

if q == "all":
    for r in sorted(rows, key=lambda x: x.get("model_name", "")):
        print(fmt(r, show_all=True))
    sys.exit(0)

if q in GROUPS:
    tags, desc = GROUPS[q]
    hits = [r for r in rows if set(tags) & set(info(r).get("tags", []))]
    # เรียงตามเวลาที่วัดได้ เร็วก่อน
    hits.sort(key=lambda r: info(r).get("benchmark_seconds") or info(r).get("latency_ms", 0) / 1000 or 999)
    print(f"{desc} — {len(hits)} ตัว\n")
    for r in hits:
        print(fmt(r, show_all=True))
        print()
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
