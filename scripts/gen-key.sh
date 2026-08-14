#!/usr/bin/env bash
# ออก virtual key จาก LiteLLM (ใช้ master key เป็นตัวออก)
#
#   ./scripts/gen-key.sh                            # key เต็มสิทธิ์ ไม่มี budget
#   ./scripts/gen-key.sh --alias openwebui          # ตั้งชื่อ key
#   ./scripts/gen-key.sh --alias somchai --budget 5 --models hf/qwen2.5-7b,hf/llama-3.1-8b
#
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
# shellcheck source=/dev/null
source .env
set +a

HOST="http://localhost:${LITELLM_PORT:-4000}"
ALIAS=""; BUDGET=""; MODELS=""; DURATION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alias)    ALIAS="$2"; shift 2 ;;
    --budget)   BUDGET="$2"; shift 2 ;;   # USD ต่อเดือน
    --models)   MODELS="$2"; shift 2 ;;   # คั่นด้วย comma; ไม่ใส่ = ทุกโมเดล
    --duration) DURATION="$2"; shift 2 ;; # เช่น 30d, 24h
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

payload=$(ALIAS="$ALIAS" BUDGET="$BUDGET" MODELS="$MODELS" DURATION="$DURATION" python3 - <<'PY'
import json, os
d = {}
if os.environ.get("ALIAS"):    d["key_alias"] = os.environ["ALIAS"]
if os.environ.get("BUDGET"):   d["max_budget"] = float(os.environ["BUDGET"]); d["budget_duration"] = "30d"
if os.environ.get("MODELS"):   d["models"] = os.environ["MODELS"].split(",")
if os.environ.get("DURATION"): d["duration"] = os.environ["DURATION"]
print(json.dumps(d))
PY
)

curl -sS "$HOST/key/generate" \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d "$payload" | python3 -m json.tool
