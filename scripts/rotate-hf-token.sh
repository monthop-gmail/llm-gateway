#!/usr/bin/env bash
# เปลี่ยน HF token ใหม่ — ตรวจสิทธิ์ ใส่ .env รีสตาร์ท แล้วยิงทดสอบให้ครบ
#
#   ./scripts/rotate-hf-token.sh hf_xxxxxxxxxxxxxxxxxxxx
#
# ออก token ใหม่ที่ https://huggingface.co/settings/tokens
# เลือกแบบ Fine-grained แล้วติ๊ก "Make calls to Inference Providers"
set -euo pipefail
cd "$(dirname "$0")/.."

new_token="${1:-}"
if [ -z "$new_token" ]; then
	echo "ใช้: $0 <hf_token ใหม่>" >&2
	exit 1
fi
case "$new_token" in
hf_*) ;;
*)
	echo "token ต้องขึ้นต้นด้วย hf_" >&2
	exit 1
	;;
esac

# ---------------------------------------------- 1) ตรวจ token ก่อนเอาไปใช้
echo "==> ตรวจ token กับ HuggingFace"
who=$(curl -sS --max-time 30 https://huggingface.co/api/whoami-v2 \
	-H "Authorization: Bearer $new_token")

echo "$who" | python3 -c '
import sys, json
d = json.load(sys.stdin)
if d.get("error"):
    print("token ใช้ไม่ได้:", d["error"]); sys.exit(1)
perms = []
for s in d.get("auth", {}).get("accessToken", {}).get("fineGrained", {}).get("scoped", []):
    perms += s.get("permissions", [])
perms += d.get("auth", {}).get("accessToken", {}).get("fineGrained", {}).get("global", [])
print("    user:", d.get("name"))
print("    perms:", ", ".join(perms) or "(ไม่มี)")
if not any("inference" in p for p in perms) and d.get("auth", {}).get("accessToken", {}).get("role") != "write":
    print("    ⚠️  ไม่เจอสิทธิ์ inference — ต้องติ๊ก \"Make calls to Inference Providers\" ตอนสร้าง token")
    sys.exit(1)
'

# ---------------------------------------------------------- 2) เขียนลง .env
echo "==> เขียนลง .env"
cp .env ".env.bak.$(date +%Y%m%d-%H%M%S)"
NEW_TOKEN="$new_token" python3 - <<-'PY'
	import os, pathlib, re
	p = pathlib.Path('.env')
	s = re.sub(r'^HF_TOKEN=.*$', 'HF_TOKEN=' + os.environ['NEW_TOKEN'], p.read_text(), flags=re.M)
	p.write_text(s)
PY
echo "    สำรอง .env เดิมไว้แล้ว (.env.bak.*)"

# ------------------------------------------------------- 3) รีสตาร์ท litellm
echo "==> รีสตาร์ท litellm"
docker compose up -d litellm >/dev/null

printf '    รอ litellm พร้อม'
for _ in $(seq 1 40); do
	if [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:4000/health/liveliness)" = "200" ]; then
		echo " — พร้อมแล้ว"
		break
	fi
	printf '.'
	sleep 5
done

# --------------------------------------------------------- 4) ยิงทดสอบจริง
echo "==> ทดสอบยิงทุกโมเดล"
set -a
# shellcheck source=/dev/null
source .env
set +a

models=$(curl -s http://localhost:4000/v1/models -H "Authorization: Bearer $LITELLM_MASTER_KEY" |
	python3 -c 'import sys, json; print(" ".join(m["id"] for m in json.load(sys.stdin)["data"]))')

pass=0
total=0
for m in $models; do
	total=$((total + 1))
	printf '    %-22s ' "$m"
	result=$(curl -s --max-time 120 http://localhost:4000/v1/chat/completions \
		-H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
		-d "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":20}" |
		python3 -c '
import sys, json, re
try:
    d = json.load(sys.stdin)
except Exception:
    print("FAIL อ่าน response ไม่ได้"); raise SystemExit
if "choices" in d:
    print("OK")
else:
    msg = re.sub(r"<[^>]+>", "", str(d.get("error", {}).get("message", d)))
    print("FAIL " + " ".join(msg.split())[:90])
')
	echo "$result"
	case "$result" in
	OK*) pass=$((pass + 1)) ;;
	esac
done

echo
echo "==> ผ่าน $pass/$total โมเดล"
if [ "$pass" -eq 0 ]; then
	echo "    ไม่มีโมเดลไหนใช้ได้เลย — เช็คสิทธิ์ token อีกครั้ง"
	exit 1
fi
echo "    เสร็จแล้ว — token เดิม revoke ได้เลยถ้ายังไม่ได้ทำ"
