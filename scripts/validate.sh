#!/usr/bin/env bash
# ตรวจความถูกต้องของ config ทั้งหมด — รันเองก่อน push ได้ และ CI ก็เรียกตัวนี้
#
#   ./scripts/validate.sh
#
# ถ้ายังไม่มี .env จะสร้างชั่วคราวจาก .env.example ให้ (ค่า dummy) แล้วลบทิ้งเมื่อจบ
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
tmp_env=0

note() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
ok()   { printf '    \033[32mOK\033[0m %s\n' "$1"; }
err()  { printf '    \033[31mFAIL\033[0m %s\n' "$1"; fail=1; }
warn() { printf '    \033[33m--\033[0m %s\n' "$1"; }

cleanup() { [ "$tmp_env" -eq 1 ] && rm -f .env; return 0; }
trap cleanup EXIT

# ---------------------------------------------------------------- .env
if [ ! -f .env ]; then
	note "ไม่มี .env — สร้างชั่วคราวจาก .env.example"
	cp .env.example .env
	tmp_env=1
	python3 - <<-'PY'
		import pathlib, re
		p = pathlib.Path('.env'); s = p.read_text()
		fill = {
		    'POSTGRES_PASSWORD': 'ci-dummy-password',
		    'LITELLM_MASTER_KEY': 'sk-ci-dummy-master-key',
		    'LITELLM_SALT_KEY': 'ci-dummy-salt-key',
		    'LITELLM_UI_PASSWORD': 'ci-dummy-ui-password',
		    'WEBUI_SECRET_KEY': 'ci-dummy-webui-secret',
		    'OPENWEBUI_LITELLM_KEY': 'sk-ci-dummy-virtual-key',
		    'HF_TOKEN': 'hf_ciDummyToken',
		}
		for k, v in fill.items():
		    s = re.sub(rf'^{k}=.*$', f'{k}={v}', s, flags=re.M)
		p.write_text(s)
	PY
	ok "สร้าง .env ชั่วคราวแล้ว"
fi

# ---------------------------------------------------- docker compose version
note "docker compose version (ต้อง >= 2.24 เพราะ prod override ใช้ !reset)"
ver=$(docker compose version --short | sed 's/^v//')
major=${ver%%.*}
rest=${ver#*.}
minor=${rest%%.*}
if [ "$major" -lt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -lt 24 ]; }; then
	err "เจอ $ver — !reset จะไม่ทำงาน port จะหลุดออก host ตอน prod"
else
	ok "$ver"
fi

# ------------------------------------------------------------- compose config
note "docker compose config"
if docker compose config -q 2>/dev/null; then ok "dev"; else err "dev"; fi
if docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml config -q 2>/dev/null; then
	ok "prod override"
else
	err "prod override"
fi

# ----------------------------------------------- prod ต้องเปิดเฉพาะ 80/443
note "prod override ต้องไม่เปิด port 3000/4000 ออก host"
published=$(docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml config --format json |
	python3 -c '
import sys, json
cfg = json.load(sys.stdin)
out = []
for name, svc in cfg.get("services", {}).items():
    for p in svc.get("ports", []):
        out.append("%s:%s" % (name, p.get("published")))
print(" ".join(sorted(out)))
')
printf '    published: %s\n' "$published"
for bad in 3000 4000; do
	case "$published" in
	*":$bad"*) err "port $bad ยังเปิดออก host — !reset ไม่ทำงาน" ;;
	*) ok "ไม่มี port $bad" ;;
	esac
done
for need in 80 443; do
	case "$published" in
	*":$need"*) ok "เปิด port $need" ;;
	*) err "ไม่ได้เปิด port $need — Caddy ทำงานไม่ได้" ;;
	esac
done

# ------------------------------------------------------- litellm/config.yaml
note "litellm/config.yaml"
if python3 - <<-'PY'
	import sys, yaml
	cfg = yaml.safe_load(open('litellm/config.yaml'))
	models = cfg.get('model_list') or []
	if not models:
	    print('model_list ว่าง'); sys.exit(1)
	for m in models:
	    if 'model_name' not in m:
	        print('ไม่มี model_name:', m); sys.exit(1)
	    if 'model' not in (m.get('litellm_params') or {}):
	        print('ไม่มี litellm_params.model:', m['model_name']); sys.exit(1)
	names = [m['model_name'] for m in models]
	dup = {n for n in names if names.count(n) > 1}
	if dup:
	    print('model_name ซ้ำ:', dup); sys.exit(1)
	print(len(models))
PY
then ok "โมเดลครบถ้วน ไม่มีชื่อซ้ำ"; else err "config.yaml มีปัญหา"; fi

# ------------------------------ provider key ต้องถูกส่งเข้า container จริง
note "ตัวแปร provider ใน .env.example ต้องถูกส่งเข้า litellm"
missing=0
while read -r v; do
	case "$v" in
	CHAT_DOMAIN | API_DOMAIN | ACME_EMAIL | LITELLM_PORT | OPENWEBUI_PORT) continue ;;
	POSTGRES_* | LITELLM_* | WEBUI_* | OPENWEBUI_*) continue ;;
	esac
	if ! grep -q "^      $v:" docker-compose.yml; then
		err "$v อยู่ใน .env.example แต่ compose ไม่ได้ส่งเข้า container — key จะไม่ถึง litellm"
		missing=1
	fi
done < <(grep -oE '^[A-Z_]+=' .env.example | tr -d '=')
[ "$missing" -eq 0 ] && ok "ส่งครบทุกตัว"

# ----------------------------------------------------------------- Caddyfile
note "deploy/Caddyfile"
if docker run --rm \
	-e CHAT_DOMAIN=llm.example.com \
	-e API_DOMAIN=llm-api.example.com \
	-e ACME_EMAIL=ci@example.com \
	-v "$PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" \
	caddy:latest caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
	ok "syntax ถูกต้อง"
else
	err "syntax ผิด"
fi

# caddy fmt --diff พิมพ์ทั้งไฟล์เสมอ ใช้เทียบไม่ได้ — เทียบผลลัพธ์ที่ format แล้วกับไฟล์จริงแทน
formatted=$(docker run --rm -v "$PWD/deploy:/w" caddy:latest caddy fmt /w/Caddyfile 2>/dev/null || true)
if [ "$formatted" != "$(cat deploy/Caddyfile)" ]; then
	err "ยังไม่ได้จัดรูปแบบ — แก้ด้วย: docker run --rm -v \$PWD/deploy:/w caddy:latest caddy fmt --overwrite /w/Caddyfile"
else
	ok "จัดรูปแบบแล้ว"
fi

# --------------------------------------------------------------- ชื่อฟิลด์
note "ตรวจว่าฟิลด์ที่เราตั้งเองไม่ชนกับของ LiteLLM"
if ! docker compose ps --status running litellm >/dev/null 2>&1; then
	warn "ข้าม — litellm ไม่ได้รัน"
elif out=$(docker compose exec -T litellm python -c "
import sys, yaml, litellm
keys = set()
for v in litellm.model_cost.values():
    if isinstance(v, dict):
        keys.update(v)
from litellm.proxy._types import ModelInfo
keys.update(ModelInfo.model_json_schema().get('properties', {}))
ours = set(sys.stdin.read().split())
# ฟิลด์ที่เราตั้งใจใช้ของ LiteLLM เอง ไม่นับว่าชน
expected = {'mode', 'supports_function_calling', 'max_input_tokens', 'max_tokens', 'id',
            'base_model', 'input_cost_per_token', 'output_cost_per_token'}
clash = sorted((ours & keys) - expected)
print(' '.join(clash))
sys.exit(1 if clash else 0)
" <<< "$(python3 -c "
import yaml
c = yaml.safe_load(open('litellm/config.yaml'))
k = set()
for m in c['model_list']:
    k.update(m.get('model_info') or {})
print(' '.join(sorted(k)))
")" 2>/dev/null); then
	ok "ไม่มีชื่อฟิลด์ชนกับ LiteLLM"
else
	echo "    ชนกัน: $out"
	err "LiteLLM จะเขียนทับค่าของเราตอน merge เข้า /model/info — ต้องเปลี่ยนชื่อ"
fi

# ------------------------------------------------------------------ fallback
note "ตรวจว่าตัวสำรองไม่ได้กินโควต้าก้อนเดียวกับตัวหลัก"
if out=$(python3 - <<'EOF'
import sys, yaml
c = yaml.safe_load(open("litellm/config.yaml"))
pool = {m["model_name"]: (m.get("model_info") or {}).get("quota_pool")
        for m in c["model_list"]}
bad = []
for entry in c.get("litellm_settings", {}).get("fallbacks", []):
    for src, chain in entry.items():
        seen = [pool.get(src)]
        for t in chain:
            if t not in pool:
                bad.append(f"{src} -> {t} (ไม่มีโมเดลนี้ใน config)")
            elif pool.get(t) in seen:
                bad.append(f"{src} -> {t} (pool {pool.get(t)} ซ้ำกับตัวก่อนหน้า)")
            seen.append(pool.get(t))
print("\n".join(bad))
sys.exit(1 if bad else 0)
EOF
); then
	ok "ทุก fallback ข้าม quota_pool จริง"
else
	echo "$out"
	err "มี fallback ที่ pool ซ้ำ — โควต้าหมดพร้อมกัน ตัวสำรองจะไม่ช่วยอะไร"
fi

# -------------------------------------------------------------------- secret
note "ตรวจว่าไม่มี secret หลุดเข้า git"
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
	err ".env ถูก track อยู่ใน git — ต้องอยู่ใน .gitignore เท่านั้น"
else
	ok ".env ไม่ถูก track"
fi

for pat in 'backups/x.sql.gz' 'backups/x.saltkey.txt' '.env.bak.1'; do
	if git check-ignore -q "$pat"; then
		ok "$pat ถูก ignore"
	else
		err "$pat ไม่ถูก ignore — ไฟล์ที่มี key อาจหลุดขึ้น git"
	fi
done

if git grep -nE 'hf_[A-Za-z0-9]{30,}|sk-[a-f0-9]{40,}' -- . >/dev/null 2>&1; then
	git grep -nE 'hf_[A-Za-z0-9]{30,}|sk-[a-f0-9]{40,}' -- . || true
	err "เจอ token/key ที่ดูเหมือนของจริงในไฟล์ที่ commit"
else
	ok "ไม่พบ token ของจริง"
fi

# --------------------------------------------------------------------- สรุป
if [ "$fail" -eq 0 ]; then
	printf '\n\033[32m✅ ผ่านทั้งหมด\033[0m\n'
else
	printf '\n\033[31m❌ มีข้อผิดพลาด\033[0m\n'
	exit 1
fi
