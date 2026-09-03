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
#   ./scripts/pick-model.sh ocr             # อ่านข้อความจากภาพเอกสาร
#   ./scripts/pick-model.sh asr             # ถอดเสียงเป็นข้อความ
#   ./scripts/pick-model.sh agent           # เอาไปทำ agent ได้ (tool + 14K + โควต้าไหว)
#   ./scripts/pick-model.sh agent 60000     # ตั้งเพดาน prompt ที่ agent ใช้จริงเอง
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

echo "$raw" | QUERY="$query" FLOOR="${2:-}" python3 -c '
import json, os, sys
from datetime import date, datetime

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
    "ocr":       (["ocr"], "อ่านข้อความจากภาพเอกสาร"),
    "asr":       (["asr"], "ถอดเสียงเป็นข้อความ"),
    "tts":       (["tts"], "สังเคราะห์เสียงจากข้อความ"),
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
AGENT_FLOOR = int(os.environ.get("FLOOR") or 13_300)

def _agent_ready(r):
    mi = info(r)
    # โควต้าทั้งรอบต้องพอยิงอย่างน้อย 1 turn ไม่งั้นมันคือโมเดลที่ "รับ prompt
    # ขนาดนี้ได้" แต่ "ยิงได้ไม่ถึงครั้งเดียวต่อวัน" — okmd/deepseek-v4-pro มี
    # verified_max_prompt 127,824 แต่โควต้า 40,000/วัน ซึ่งเล็กกว่า turn เดียว
    # ของ hermes (59,497) hermes เกือบเอาไปวางเป็น fallback เพราะเลข prompt สวย
    #
    # เทียบเฉพาะเจ้าที่นับเป็น token — requests/neurons/tpm แปลงข้ามหน่วยไม่ได้
    # และการเดาอัตราแลกเปลี่ยนคือทางที่ผิดเงียบ ๆ (issue #5) จึงปล่อยผ่านแล้ว
    # ไปแสดงให้คนตัดสินใจเองในสรุปท้ายหมวดแทน
    quota_tokens = mi.get("quota_tokens_per_window")
    if quota_tokens is not None and quota_tokens < AGENT_FLOOR:
        return False
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
    q = mi.get("quota_tokens_per_window")
    if q:
        qw = mi.get("quota_window") or "?"
        bits.append("โควต้า " + str(q // 1000) + "K/" + qw)
    cap = mi.get("verified_max_prompt")
    if cap:
        # ≥ ไม่ใช่ ≤ — เลขนี้คือขนาดที่ยิงผ่านแล้ว เพดานจริงอยู่สูงกว่านี้
        # และบางตัวหยุดเพราะโควต้าหมดกลางคัน ไม่ใช่เพราะชนเพดาน
        bits.append(f"prompt ≥{cap//1000}K")
    fu = mi.get("free_until")
    if fu:
        # คิดจากฟิลด์ตรง ๆ ไม่พึ่งข้อความใน provider_quota — ไม่งั้นคนที่เพิ่มโมเดล
        # แล้วไม่เขียนซ้ำในคำอธิบาย จะไม่มีใครเห็นว่ามันมีวันหมดอายุ
        # ใช้เกณฑ์ 14 วันเท่ากับ validate.sh จะได้ไม่มีสองมาตรฐาน
        left = (date.fromisoformat(str(fu)) - datetime.now().date()).days
        if left < 0:
            bits.append("❌ หมดช่วงฟรีแล้ว " + str(fu))
        elif left <= 14:
            bits.append("⚠️ ฟรีอีก " + str(left) + " วัน (ถึง " + str(fu) + ")")
        else:
            bits.append("⏳ ฟรีอีก " + str(left) + " วัน")
    stab = mi.get("stability")
    if stab and stab != "stable":
        bits.append("⚠️ " + stab + " — มีวันหมดอายุ")
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
    def _agent_shape(r):
        """เข้าเกณฑ์ agent ทุกข้อ ยกเว้นเรื่อง status — ใช้แยกตัวที่แค่โควต้าหมด"""
        mi = info(r)
        q = mi.get("quota_tokens_per_window")
        # โควต้าเล็กเกินไม่ใช่ "หมดตอนนี้" — รอไปก็ไม่ดีขึ้น จึงไม่ควรอยู่ในลิสต์
        # ตัวสำรอง ต้องแยกไปอีกหมวดพร้อมเหตุผลของมันเอง
        if q is not None and q < AGENT_FLOOR:
            return False
        return (mi.get("supports_function_calling") is True
                and (mi.get("verified_max_prompt") or 0) >= AGENT_FLOOR
                and mi.get("quota_window") != "rpm-only"
                and not mi.get("answered_by"))

    def _too_small(r):
        """ผ่านทุกข้อ แต่โควต้าทั้งรอบเล็กกว่า 1 turn — ใช้ไม่ได้ทั้งเป็น main และ fallback"""
        mi = info(r)
        q = mi.get("quota_tokens_per_window")
        return (q is not None and q < AGENT_FLOOR
                and mi.get("supports_function_calling") is True
                and (mi.get("verified_max_prompt") or 0) >= AGENT_FLOOR
                and not mi.get("answered_by"))

    by_speed = lambda r: (info(r).get("latency_ms_14k")
                          or info(r).get("latency_ms") or 10 ** 9)
    hits = sorted((r for r in rows if _agent_ready(r)), key=by_speed)
    # ตัวสำรองที่ดีคือตัวที่ว่างตอนตัวหลักตาย ไม่ใช่ตัวที่ว่างตอนนี้ — จึงไม่ซ่อน
    # ตัวที่โควต้าหมด แค่ย้ายไปท้ายลิสต์ (เหมือนที่หมวดอื่นทำ)
    down = sorted((r for r in rows if _agent_shape(r) and not _agent_ready(r)),
                  key=by_speed)
    floor_note = f" · floor {AGENT_FLOOR:,} token"
    print(f"เอาไปทำ agent ได้ — {len(hits)} ตัวที่ใช้ได้ตอนนี้{floor_note}\n")
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
    if len(pools) <= 1:
        # ถ้าเหลือก้อนเดียว คำแนะนำ "เลือกตัวสำรองข้ามก้อน" ทำตามไม่ได้
        print("\n  ⚠️ ที่ floor นี้เหลือ quota_pool เดียว — สร้าง fallback chain")
        print("     ข้ามก้อนไม่ได้ ลอง floor ต่ำลง หรือดูรายชื่อที่โควต้าหมดข้างล่าง")
    else:
        print("\n  ตัวที่อยู่ก้อนเดียวกันหมดโควต้าพร้อมกัน — เลือกตัวสำรองข้ามก้อนเสมอ")
    # ตัวกรองข้างบนตัดออกได้เฉพาะตัวที่ "รู้แล้วว่าโควต้าเล็กเกิน" — ตัวที่ยังไม่มี
    # ตัวเลขจะผ่านมาโดยไม่มีใครรู้ว่าพอหรือไม่พอ ต้องบอกออกมาตรง ๆ ว่าเหลือกี่ตัว
    # ไม่งั้น "ผ่านเกณฑ์" จะถูกอ่านว่า "โควต้าพอ" ซึ่งยังไม่จริงสำหรับส่วนใหญ่
    unknown = [r for r in hits if info(r).get("quota_tokens_per_window") is None]
    if unknown:
        other_unit = [r for r in unknown
                      if any(info(r).get(k) for k in ("quota_requests_per_window",
                                                      "quota_tpm", "quota_neurons_per_window"))]
        n_blank = len(unknown) - len(other_unit)
        print(f"\n  ⚠️ {len(unknown)} ใน {len(hits)} ตัวยังตอบไม่ได้ว่าโควต้าพอไหม")
        if n_blank:
            print(f"     {n_blank} ตัวไม่มีตัวเลขโควต้าเลย — ตัวกรองจึงปล่อยผ่าน (issue #5)")
        if other_unit:
            names = ", ".join(r.get("model_name", "?") for r in other_unit[:4])
            print(f"     {len(other_unit)} ตัวนับคนละหน่วย (req/tpm/neuron) เทียบกับ token ไม่ได้: {names}")
        print("     ก่อนวางเป็น main หรือ fallback ให้อ่าน provider_quota ด้วยตาก่อน")
    shaky = [r for r in hits if info(r).get("stability") not in (None, "stable")]
    if shaky:
        # or/ox-alpha ถูกเลือกเป็น fallback อันดับ 1 เพราะ benchmark สวย
        # โดยไม่มีใครเห็นคำว่า stealth ที่ซ่อนอยู่ใน litellm_params แล้วมันหายไปเฉย ๆ
        print(f"\n⚠️ {len(shaky)} ตัวในรายการเป็น preview/stealth — มีวันหมดอายุในตัว")
        print("   อย่าเอาไปวางเป็นตัวสำรองถาวร:")
        for r in shaky:
            nm = r.get("model_name", "?")
            print(f"     {nm:<26} {info(r).get("stability")}")
    tiny = sorted((r for r in rows if _too_small(r)), key=by_speed)
    if tiny:
        print(f"\n{len(tiny)} ตัวถูกตัดออกเพราะโควต้าทั้งรอบเล็กกว่า 1 turn ที่ floor นี้")
        print("รอโควต้ารีเซ็ตก็ไม่ช่วย เพราะยิงได้ไม่ถึงครั้งเดียวต่อรอบ:\n")
        for r in tiny:
            mi = info(r)
            nm = r.get("model_name", "?")
            q = mi.get("quota_tokens_per_window")
            qw = mi.get("quota_window") or "?"
            print(f"  {nm:<26} {q:,}/{qw}  (ต้องการ {AGENT_FLOOR:,})")

    if down:
        print(f"\nอีก {len(down)} ตัวเข้าเกณฑ์ครบแต่โควต้าหมดตอนนี้ — ไม่ตัดทิ้ง")
        print("เพราะตัวสำรองที่ดีคือตัวที่ว่างตอนตัวหลักตาย ไม่ใช่ตัวที่ว่างตอนนี้:\n")
        for r in down:
            mi = info(r)
            name = r.get("model_name", "?")
            print(f"  {name:<26} {mi.get("status")}  pool={mi.get("quota_pool")}")
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
    # หมวดเหล่านี้ไม่ได้ยิงที่ /v1/chat/completions — บอกไว้ไม่งั้นลองแล้วงง
    ENDPOINT = {
        "asr": "POST /v1/audio/transcriptions (multipart · ต้องใส่ type=audio/wav)",
        "tts": "POST /v1/audio/speech",
        "embedding": "POST /v1/embeddings",
    }
    if q in ENDPOINT:
        print("  ยิงที่: " + ENDPOINT[q] + "\n")
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
