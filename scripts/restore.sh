#!/usr/bin/env bash
# กู้คืน Postgres จากไฟล์ที่ scripts/backup.sh สร้างไว้
#
#   ./scripts/restore.sh backups/litellm-20260814-203015.sql.gz
#
# ⚠️ เขียนทับข้อมูลปัจจุบันทั้งหมด — virtual key ที่ออกหลังจากวันที่ backup จะหายไป
set -euo pipefail
cd "$(dirname "$0")/.."

dump="${1:-}"
if [ -z "$dump" ] || [ ! -f "$dump" ]; then
	echo "ใช้: $0 <ไฟล์.sql.gz>" >&2
	echo >&2
	echo "ไฟล์ที่มี:" >&2
	find ./backups -maxdepth 1 -name 'litellm-*.sql.gz' 2>/dev/null | sort >&2 || echo "  (ไม่มี)" >&2
	exit 1
fi

set -a
# shellcheck source=/dev/null
source .env
set +a

# ------------------------------------------------ เตือนเรื่อง salt key ก่อน
salt_file="${dump%.sql.gz}.saltkey.txt"
if [ -f "$salt_file" ]; then
	saved_salt=$(grep -E '^LITELLM_SALT_KEY=' "$salt_file" | cut -d= -f2-)
	if [ "$saved_salt" != "${LITELLM_SALT_KEY:-}" ]; then
		echo "❌ LITELLM_SALT_KEY ใน .env ไม่ตรงกับตอนที่ backup" >&2
		echo "   provider key ที่เก็บใน DB จะถอดรหัสไม่ได้ และ virtual key ทั้งหมดใช้ไม่ได้" >&2
		echo >&2
		echo "   แก้ .env ให้เป็นค่าจาก $salt_file แล้วรันใหม่" >&2
		exit 1
	fi
	echo "==> salt key ตรงกับตอน backup ✅"
else
	echo "⚠️  ไม่เจอ $salt_file — ถ้า LITELLM_SALT_KEY ตอนนี้ไม่ใช่ค่าเดียวกับตอน backup"
	echo "    key ที่เก็บใน DB จะใช้ไม่ได้"
fi

# ------------------------------------------------------------ ยืนยันก่อนทับ
echo
echo "จะเขียนทับ database ${POSTGRES_DB:-litellm} ด้วย $dump"
printf 'พิมพ์ yes เพื่อยืนยัน: '
read -r answer
if [ "$answer" != "yes" ]; then
	echo "ยกเลิก"
	exit 1
fi

# ------------------------------------------------------------------ กู้คืน
echo "==> หยุด litellm ระหว่างกู้คืน"
docker compose stop litellm >/dev/null

echo "==> restore"
gunzip -c "$dump" | docker compose exec -T db psql \
	-U "${POSTGRES_USER:-litellm}" \
	-d "${POSTGRES_DB:-litellm}" \
	-v ON_ERROR_STOP=1 \
	--quiet

echo "==> เปิด litellm กลับ"
docker compose up -d litellm >/dev/null

printf '    รอ litellm พร้อม'
for _ in $(seq 1 40); do
	if [ "$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${LITELLM_PORT:-4000}/health/liveliness")" = "200" ]; then
		echo " — พร้อมแล้ว"
		break
	fi
	printf '.'
	sleep 5
done

echo
echo "==> ตรวจว่า virtual key กลับมา"
docker compose exec -T db psql -U "${POSTGRES_USER:-litellm}" -d "${POSTGRES_DB:-litellm}" \
	-tAc 'SELECT count(*) FROM "LiteLLM_VerificationToken";' 2>/dev/null |
	while read -r n; do echo "    virtual key ในระบบ: $n"; done

echo "✅ เสร็จ"
