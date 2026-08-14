#!/usr/bin/env bash
# สำรอง Postgres ของ LiteLLM (virtual key, budget, spend log)
#
#   ./scripts/backup.sh                 # เก็บลง ./backups/
#   ./scripts/backup.sh /path/to/dir    # เก็บที่อื่น
#
# ⚠️ ไฟล์ backup มี virtual key ทั้งหมดของผู้ใช้ — เก็บให้ปลอดภัยเท่ากับ .env
#
# กู้คืน: ./scripts/restore.sh <ไฟล์.sql.gz>
set -euo pipefail
cd "$(dirname "$0")/.."

set -a
# shellcheck source=/dev/null
source .env
set +a

dest="${1:-./backups}"
mkdir -p "$dest"

stamp=$(date +%Y%m%d-%H%M%S)
out="$dest/litellm-$stamp.sql.gz"

if ! docker compose ps --status running --services 2>/dev/null | grep -qx db; then
	echo "container llm-db ไม่ได้รันอยู่ — สั่ง docker compose up -d db ก่อน" >&2
	exit 1
fi

echo "==> dump database"
docker compose exec -T db pg_dump \
	-U "${POSTGRES_USER:-litellm}" \
	-d "${POSTGRES_DB:-litellm}" \
	--clean --if-exists |
	gzip >"$out"

size=$(du -h "$out" | cut -f1)
echo "    $out ($size)"

# LITELLM_SALT_KEY คือกุญแจถอดรหัส provider key ที่เก็บใน DB
# ถ้า restore ด้วย salt คนละตัว ข้อมูลที่เข้ารหัสไว้จะอ่านไม่ออก
echo "==> บันทึก salt key คู่กับ dump"
salt_file="$dest/litellm-$stamp.saltkey.txt"
{
	echo "# ต้องใช้ค่านี้ใน .env ตอน restore ไม่งั้น key ที่เก็บใน DB จะถอดรหัสไม่ได้"
	echo "LITELLM_SALT_KEY=${LITELLM_SALT_KEY}"
} >"$salt_file"
chmod 600 "$salt_file" "$out"
echo "    $salt_file"

echo
echo "✅ เสร็จ — เก็บไฟล์ทั้งสองไว้ด้วยกัน"
echo "   ไฟล์นี้มี virtual key ของทุกคน อย่าเอาขึ้น git หรือส่งผ่านช่องทางที่ไม่ปลอดภัย"

# ลบ backup เก่าเกิน 14 ไฟล์
count=$(find "$dest" -maxdepth 1 -name 'litellm-*.sql.gz' | wc -l)
if [ "$count" -gt 14 ]; then
	echo "==> ลบ backup เก่า (เก็บไว้ 14 ชุดล่าสุด)"
	find "$dest" -maxdepth 1 -name 'litellm-*.sql.gz' -printf '%T@ %p\n' |
		sort -n | head -n "-14" | cut -d' ' -f2- |
		while read -r old; do
			rm -f "$old" "${old%.sql.gz}.saltkey.txt"
			echo "    ลบ $old"
		done
fi
