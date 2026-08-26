# LLM Gateway — LiteLLM + Open WebUI

[![validate](https://github.com/monthop-gmail/llm-gateway/actions/workflows/validate.yml/badge.svg)](https://github.com/monthop-gmail/llm-gateway/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Gateway กลางสำหรับ **ออก API token ให้ผู้ใช้/แอป** แล้วยิงไปหลังบ้านได้หลายเจ้า
เริ่มจาก HuggingFace Inference แล้วขยายไป vLLM / Ollama / cloud providers ภายหลัง
โดยที่ฝั่ง client **ไม่ต้องแก้อะไรเลย** — เห็นเป็น OpenAI-compatible API ตัวเดียว

```
                        ┌──────────────┐
  Open WebUI (chat UI) ─┤              ├─► HuggingFace Inference Providers
                        │              │   (together / novita / sambanova / ...)
  curl / SDK / n8n ────►│   LiteLLM    ├─► Groq / Cerebras / Mistral / Cloudflare
  Cline / Aider / ...   │  :4000 /v1   ├─► NVIDIA NIM / OpenRouter / Ollama Cloud
  (sk-... virtual key)  │              ├─► OKMD / ThaiLLM (ไทย 🇹🇭)
                        │              ├─► vLLM / Ollama ที่รันเอง (ถ้ามี GPU)
                        └──────┬───────┘
                               │
                          Postgres  (virtual keys, budget, spend log)
```

## จุดสำคัญ

- **ออก token ได้เอง** — LiteLLM สร้าง virtual key (`sk-...`) ต่อคน/ต่อแอป กำหนด budget,
  โมเดลที่เข้าถึงได้, วันหมดอายุ และดู spend ย้อนหลังได้
- **key จริงของ provider อยู่ที่ server เดียว** — ผู้ใช้ไม่เคยเห็น key ของเจ้าไหนเลย
- **เพิ่ม backend ทีหลังไม่กระทบ client** — แก้ `litellm/config.yaml` (หรือเพิ่มผ่าน UI)
  แล้ว key เดิมยิงโมเดลใหม่ได้เลย
- **ทดสอบแล้วว่ารองรับ tool calling / streaming / Anthropic format / embeddings**
  ใช้กับ AI agent และ coding agent ได้จริง ดู [CLIENTS.md](CLIENTS.md)
- **มีหลายโปรเจกต์ใช้ร่วมกัน** — กติกาว่าใครทำอะไร ส่งผลทดสอบกลับยังไง
  อยู่ที่ [INTEGRATION.md](INTEGRATION.md)
- **provider เจ้าไหนล่มก็ยังใช้ได้** — ตั้ง `fallbacks` ไว้ทุกสาย ถ้าปลายทางหลักตาย
  LiteLLM จะสลับไปเจ้าอื่นให้เองโดย client ไม่รู้ตัว

## ติดตั้ง (dev)

ต้องมี Docker + Docker Compose v2.24 ขึ้นไป (ใช้ `!reset` ใน override file)

```bash
git clone <repo-url> llm-gateway && cd llm-gateway
cp .env.example .env
```

เติมค่าใน `.env` — ตัวที่ **ต้อง** ใส่:

```bash
# สุ่ม secret ทั้งหมดในคำสั่งเดียว
python3 - <<'PY'
import re, secrets, pathlib
p = pathlib.Path('.env'); s = p.read_text()
def put(k, v): 
    global s
    s = re.sub(rf'^{k}=.*$', f'{k}={v}', s, flags=re.M)
master = 'sk-' + secrets.token_hex(24)
put('POSTGRES_PASSWORD', secrets.token_hex(24))
put('LITELLM_MASTER_KEY', master)
put('LITELLM_SALT_KEY', secrets.token_hex(32))
put('LITELLM_UI_PASSWORD', secrets.token_hex(12))
put('WEBUI_SECRET_KEY', secrets.token_hex(32))
put('OPENWEBUI_LITELLM_KEY', master)   # เปลี่ยนเป็น virtual key ทีหลัง
p.write_text(s); print('secrets generated')
PY
```

แล้วใส่ **API key ของ provider อย่างน้อย 1 เจ้า** ลง `.env`

แนะนำเริ่มที่ **Groq** — ฟรี ไม่ต้องใช้บัตร สมัครเสร็จใช้ได้ทันที และเป็นเจ้าเดียว
ที่มีโมเดลค้นเว็บได้ (`gq/compound-mini`) สมัครที่ https://console.groq.com
แล้วใส่ `GROQ_API_KEY=`

| provider | ตัวแปร | สมัครที่ | หมายเหตุ |
|---|---|---|---|
| **OpenCode Zen** | — **ไม่ต้องมี key** | — | ⭐ ยิงได้ทันที ไม่ต้องสมัครอะไรเลย |
| **LLM7.io** | — **ไม่ต้องมี key** (2 โมเดล) | llm7.io | ขอ key ฟรีเพื่อปลดล็อกอีก 44 โมเดล |
| **Groq** | `GROQ_API_KEY` | console.groq.com | เริ่มที่นี่ถ้าต้องการโควต้าเยอะ — ฟรี ไม่ต้องใช้บัตร |
| Cerebras | `CEREBRAS_API_KEY` | cloud.cerebras.ai | เร็วสุดสำหรับ coding |
| Cloudflare | `CLOUDFLARE_API_KEY` + `CLOUDFLARE_ACCOUNT_ID` | dash.cloudflare.com | 10,000 neurons/วัน |
| Mistral | `MISTRAL_API_KEY` | console.mistral.ai | 1B token/เดือน |
| OpenRouter | `OPENROUTER_API_KEY` | openrouter.ai/keys | โมเดลฟรีหลายสิบตัว |
| Ollama Cloud | `OLLAMA_API_KEY` | ollama.com/settings/keys | 7 โมเดลฟรี |
| NVIDIA NIM | `NVIDIA_NIM_API_KEY` | build.nvidia.com | มี embeddings ด้วย |
| **OKMD (ไทย)** | `OKMD_API_KEY` | playground.okmd.or.th | Claude Sonnet 5 / GPT-5.4 / Grok 4.3 — แต่โควต้าแค่ ~40K token/วัน |
| ThaiLLM (ไทย) | `THAILLM_API_KEY` | thaillm.or.th | โมเดลภาษาไทยที่พัฒนาในไทย |
| HuggingFace | `HF_TOKEN` | huggingface.co/settings/tokens | ⚠️ ดูหมายเหตุด้านล่าง |
| Typhoon (ไทย) | `TYPHOON_API_KEY` | playground.opentyphoon.ai | ยังไม่เปิด — config รอไว้แล้ว |
| SEA-LION | `SEALION_API_KEY` | playground.sea-lion.ai | ยังไม่เปิด — config รอไว้แล้ว |
| Chinda (ไทย) | `IAPP_API_KEY` | iapp.co.th | ยังไม่เปิด — config รอไว้แล้ว |
| KNPLabs (ไทย) | `KNPLAB_API_KEY` | play.knplabai.com | ยังไม่เปิด — config รอไว้แล้ว |
| Float16 (ไทย) | `FLOAT16_API_KEY` + `FLOAT16_BASE_URL` | float16.cloud | ยังไม่เปิด — ต้องตั้ง base URL เอง |

> **HuggingFace ไม่ใช่ตัวเลือกแรกอีกแล้ว** — โปรเจกต์นี้เริ่มจาก HF แต่เครดิต
> รายเดือนของบัญชีที่ใช้ทดสอบหมดตั้งแต่ 2026-08-23 (`"You have depleted your
> monthly included credits"`) ถ้าจะใช้ `hf/*` ต้องเติมเครดิตเอง
> หรือปล่อยไว้ก็ได้ — `fallbacks` ใน config จะพา `hf/*` ไป provider อื่นให้อยู่แล้ว
>
> ตอนสร้าง HF token เลือกแบบ **Fine-grained** ติ๊ก **"Make calls to Inference
> Providers"** ไม่ติ๊กจะได้ 401 ทุก request

```bash
docker compose up -d
```

| บริการ | URL | login |
|---|---|---|
| Open WebUI | http://localhost:3000 | สมัครเอง — **คนแรก = admin** |
| LiteLLM Admin UI | http://localhost:4000/ui | `LITELLM_UI_USERNAME` / `LITELLM_UI_PASSWORD` ใน `.env` |
| LiteLLM API | http://localhost:4000/v1 | Bearer `sk-...` |
| API docs | http://localhost:4000/docs | |

### เช็คว่าใช้ได้

```bash
set -a; source .env; set +a
curl -s http://localhost:4000/v1/models -H "Authorization: Bearer $LITELLM_MASTER_KEY" | python3 -m json.tool

curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d '{"model":"gq/gpt-oss-120b","messages":[{"role":"user","content":"สวัสดี"}]}'
```

## ออก token ให้ผู้ใช้

```bash
./scripts/gen-key.sh --alias somchai --budget 5 --models cb/gemma-4-31b,mi/ministral-8b
./scripts/gen-key.sh --alias n8n-bot --duration 90d
./scripts/gen-key.sh --alias cline                # เต็มสิทธิ์ ไม่มี budget
```

หรือกดออกจากหน้า **Virtual Keys** ใน `/ui`

ผู้ใช้เอา key ไปใช้กับอะไรก็ได้ที่คุยภาษา OpenAI ได้:

```python
from openai import OpenAI
client = OpenAI(base_url="http://<host>:4000/v1", api_key="sk-....")
client.chat.completions.create(model="cb/gemma-4-31b", messages=[...])
```

**แนะนำ:** เปลี่ยน `OPENWEBUI_LITELLM_KEY` ใน `.env` จาก master key เป็น virtual key
แล้ว `docker compose up -d openwebui` — จะได้แยก spend ของหน้าแชทออกจาก key อื่น

## เลือกโมเดลยังไงเมื่อมีตั้ง 115 ตัว

**ถามสคริปต์เอา** — ไม่ต้องไล่อ่านตารางทั้งหมด

```bash
set -a; source .env; set +a
./scripts/pick-model.sh              # ดูหมวดทั้งหมด
./scripts/pick-model.sh coding       # เขียนโค้ดได้ครบ 3/3
./scripts/pick-model.sh thai         # ภาษาไทย
./scripts/pick-model.sh web          # ค้นเว็บได้
./scripts/pick-model.sh no-key       # ไม่ต้องมี API key
./scripts/pick-model.sh fast         # ตอบเร็วกว่า 800ms
./scripts/pick-model.sh quality      # frontier model
./scripts/pick-model.sh sea-lion     # ค้นอิสระจากชื่อ/คำอธิบาย
```

ตัวอย่างผลลัพธ์:

```
เขียนโค้ดได้ครบ 3/3 ในการทดสอบ — 9 ตัว

  cb/gemma-4-31b            (coding 3/3, 359ms)
      เขียนโค้ดได้ครบทั้ง 3 ข้อในการทดสอบ ตอบเร็ว (359ms)
      โควต้า: ~1M token/วัน แต่เป็นโควต้าสะสมต่อนาที (TPM) ยิงงานใหญ่ติดกันจะชน
```

**ฝั่งโปรแกรมเรียก API เอาได้** — ทุกโมเดลมี `model_info` แนบไว้ใน `/model/info`

```bash
curl -s http://localhost:4000/model/info -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  | jq '.data[] | select(.model_info.tags[]? == "coding-best")
        | {model_name, desc: .model_info.description, sec: .model_info.benchmark_seconds}'
```

field ที่ใส่ไว้: `description` `tags` `benchmark_coding` `benchmark_seconds`
`latency_ms` `supports_function_calling` `provider_label` `provider_quota` `context_window`
`verified_by` (ใครยืนยันผลนี้ เมื่อไหร่ — ดู [INTEGRATION.md](INTEGRATION.md))

tag ที่ใช้ได้: `coding-best` `coding-ok` `coding-weak` `thai` `web-access` `fast`
`no-api-key` `quality-top` `long-context` `no-tools` `embedding` `general`

> ⚠️ **`/v1/models` ไม่มีข้อมูลพวกนี้** — เป็นสเปคของ OpenAI ที่คืนแค่ `id`
> client อย่าง Open WebUI / Cline / Aider จะเห็นแค่ชื่อ ต้องเรียก `/model/info` แยก

## รายละเอียดโมเดลและ provider

ย้ายออกไปคนละไฟล์เพราะยาวกว่าตัว README เอง:

| ไฟล์ | มีอะไร |
|---|---|
| [docs/providers.md](docs/providers.md) | provider ทั้ง 12 เจ้า — โควต้า วิธีขอ key ข้อควรระวังรายเจ้า |
| [docs/benchmarks.md](docs/benchmarks.md) | ผลวัดจริง — โมเดลไหนเข้าเว็บได้ ตัวไหนเขียนโค้ดได้ดี |
| [INTEGRATION.md](INTEGRATION.md) | ฟิลด์ใน `model_info` เชื่อได้แค่ไหน + กติกาสำหรับโปรเจกต์ที่มาใช้ |
| [CLIENTS.md](CLIENTS.md) | ต่อ Cline / Aider / n8n / LangChain เข้ากับ gateway |

ไม่อยากอ่านเอง ใช้ `./scripts/pick-model.sh` ให้มันเลือกให้

## Deploy production (โดเมน + HTTPS)

ตั้งโดเมนใน `.env`:

```bash
CHAT_DOMAIN=llm.example.com          # หน้าแชท
API_DOMAIN=llm-api.example.com       # API + admin UI
ACME_EMAIL=you@example.com
```

```bash
# 1. ชี้ DNS A record ทั้งสองชื่อมาที่ IP เครื่องนี้ก่อน
#    (Caddy ขอ cert ไม่ได้ถ้า DNS ยังไม่มา)

# 2. เปิด firewall เฉพาะ 80 + 443
sudo ufw allow 80,443/tcp

# 3. up ด้วย override
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d

# 4. ดู Caddy ขอ cert
docker compose logs -f caddy
```

`deploy/docker-compose.prod.yml` จะ **ถอด port 3000/4000 ออกจาก host ทั้งหมด** (`!reset []`)
เข้าได้ทาง Caddy ทางเดียว และเปิด HTTPS อัตโนมัติจาก Let's Encrypt

**ถ้าเครื่องมี reverse proxy อยู่แล้ว** — ตัด service `caddy` ออกจาก override
เอา 2 block ใน `deploy/Caddyfile` ไปแปะใน proxy ตัวนั้น แล้วต่อ network `llm-net` เข้าด้วยกัน

### ควรทำก่อนเปิดใช้จริง

- [ ] จำกัด IP เข้าหน้า `/ui` admin — มี block ตัวอย่างคอมเมนต์ไว้ใน `deploy/Caddyfile`
- [ ] ตั้ง `ENABLE_SIGNUP: "False"` หลังสมัคร admin ของ Open WebUI เสร็จ
- [ ] ออก virtual key แบบมี `--budget` ให้ทุก client — coding agent กิน token มหาศาล
- [ ] อย่าเปิด port 3000/4000 ตรงสู่อินเทอร์เน็ตโดยไม่มี firewall

### ย้ายเครื่อง

```bash
docker compose down
tar czf llm-gateway.tgz docker-compose.yml .env litellm/ scripts/ deploy/ *.md

# ถ้าอยากยก virtual key + spend log ไปด้วย
docker run --rm -v <project>_db_data:/v -v $PWD:/b alpine tar czf /b/db_data.tgz -C /v .
```

> ⚠️ **`LITELLM_SALT_KEY` ต้องเป็นค่าเดิม** ถ้ายก volume Postgres ไปด้วย —
> มันคือกุญแจถอดรหัส provider key ที่เก็บใน DB เปลี่ยนแล้ว key ที่ออกไปแล้วใช้ไม่ได้ทั้งหมด
> ถ้าเริ่ม DB ใหม่ virtual key เดิมหายหมด ต้องออกใหม่ให้ทุก client

## ทรัพยากรที่ต้องใช้

Gateway อย่างเดียว (ไม่รันโมเดลเอง) — เบามาก:

| service | RAM ที่ใช้จริง | limit ที่ตั้งไว้ | ขนาด image |
|---|---|---|---|
| postgres | ~50MB | — | 294MB |
| litellm | ~1.2GB | 2GB | 1.2GB |
| open-webui | ~1GB | 3GB | **5.1GB** |
| caddy (เฉพาะ prod) | ~20MB | — | 49MB |

รวม RAM ~2.3GB และ **disk ~6.6GB** สำหรับ image (Open WebUI ตัวใหญ่สุด)
ปรับ `mem_limit` ใน `docker-compose.yml` ได้ตามเครื่อง
Open WebUI โหลด embedding model ในตัวสำหรับ RAG (~500MB) ถ้าไม่ใช้ปิดได้ที่
Admin → Settings → Documents

**ถ้าจะรันโมเดลเองด้วย** (vLLM/Ollama) ต้องการ GPU + RAM แยกต่างหาก แนะนำแยกเครื่อง

## คำสั่งที่ใช้บ่อย

```bash
docker compose ps
docker compose logs -f litellm
docker compose restart litellm       # หลังแก้ config.yaml
docker compose up -d litellm         # หลังแก้ .env
docker compose down                  # หยุด (data ยังอยู่ใน volume)
docker compose down -v               # ลบ data ทั้งหมด
```

## ไฟล์

```
docker-compose.yml              stack: postgres + litellm + open-webui
deploy/docker-compose.prod.yml  override สำหรับ prod (โดเมน + HTTPS + ปิด port)
deploy/Caddyfile                reverse proxy (โดเมนมาจาก .env)
litellm/config.yaml             รายชื่อโมเดล + routing
scripts/gen-key.sh              ออก virtual key ให้ผู้ใช้/แอป
scripts/rotate-hf-token.sh      เปลี่ยน HF token ใหม่ + ทดสอบทุกโมเดลให้
scripts/backup.sh               สำรอง virtual key + spend log
scripts/restore.sh              กู้คืนจาก backup
scripts/validate.sh             ตรวจ config ทั้งหมด (CI เรียกตัวนี้)
scripts/health-check.py         ยิงทุกโมเดลหาว่าตัวไหนตาย แยกจากตัวที่แค่โควต้าหมด
scripts/verify-capabilities.py  ตรวจ tool calling ซ้ำเทียบกับ config (ยิง API ตรง — ดูขอบเขตใน INTEGRATION.md)
scripts/pick-model.sh           ช่วยเลือกโมเดลตามงาน (อ่านจาก /model/info)
scripts/bench-coding.py         วัดความสามารถเขียนโค้ดของโมเดล
scripts/probe-context.py        หาว่าแต่ละโมเดลรับ prompt ได้ยาวจริงเท่าไหร่
scripts/probe-latency-14k.py    จับเวลาด้วย prompt ขนาดที่ agent ใช้จริง
scripts/config_edit.py          เขียนฟิลด์กลับเข้า config โดยไม่ทำคอมเมนต์หาย
scripts/failure_hints.py        แปล error ของ provider เป็นสาเหตุ (ใช้ร่วมกันทุกสคริปต์)
tests/                          pytest ของสองโมดูลข้างบน — CI รันทุก push
ruff.toml                       กติกา lint พร้อมเหตุผลว่าทำไมปิดกฎไหน
docs/providers.md               provider ทั้ง 12 เจ้า — โควต้า วิธีขอ key
docs/benchmarks.md              ผลวัดจริง — เข้าเว็บได้ / เขียนโค้ดได้ดี
CLIENTS.md                      วิธีต่อ AI agent / coding agent
INTEGRATION.md                  กติกาสำหรับโปรเจกต์อื่นที่มาใช้ gateway ร่วมกัน
.env.example                    template — คัดลอกเป็น .env แล้วเติมค่า
```

สคริปต์ที่ยิง API ทุกตัวส่ง `"disable_fallbacks": true` เสมอ — ไม่งั้นวัดโมเดลที่
ตัวสำรองตอบแทน แล้วบันทึกผลใส่ชื่อโมเดลที่ขอ (เคยพลาดมาแล้ว 5 ครั้ง ดู INTEGRATION.md)

### scripts/

```bash
# ออก virtual key
./scripts/gen-key.sh --alias somchai --budget 5 --models cb/gemma-4-31b

# เปลี่ยน HF token (ตรวจสิทธิ์ก่อนเขียน .env แล้วยิงทดสอบทุกโมเดล)
./scripts/rotate-hf-token.sh hf_xxxxxxxx

# ตรวจ config ก่อน push — CI เรียกตัวเดียวกันนี้
./scripts/validate.sh

# วัดว่าโมเดลไหนเขียนโค้ดได้ดี (ต้อง up stack ก่อน)
set -a; source .env; set +a
python3 scripts/bench-coding.py cb/gemma-4-31b gq/gpt-oss-120b

# หาโมเดลที่ตายแล้วใน config — provider ปลดโมเดลบ่อยกว่าที่คิด
python3 scripts/health-check.py            # ทุกตัว
python3 scripts/health-check.py gq/ cb/    # เฉพาะ prefix

# เลือกโมเดลตามงาน
./scripts/pick-model.sh coding
```

## Backup

virtual key ทั้งหมด, budget และ spend log อยู่ใน Postgres — ถ้า volume หาย
ทุก client ที่ถือ key อยู่จะใช้ไม่ได้ทันที และต้องออก key ใหม่ให้ทุกคน

```bash
./scripts/backup.sh                    # เก็บลง ./backups/ (เก็บ 14 ชุดล่าสุด)
./scripts/restore.sh backups/litellm-20260814-203015.sql.gz
```

ตั้ง cron ให้อัตโนมัติ:

```bash
0 3 * * * cd /path/to/llm-gateway && ./scripts/backup.sh >> /var/log/llm-backup.log 2>&1
```

> ⚠️ ไฟล์ backup **มี virtual key ของผู้ใช้ทุกคน** เก็บให้ปลอดภัยเท่ากับ `.env`
> (`backups/` อยู่ใน `.gitignore` แล้ว)
>
> `backup.sh` เขียนไฟล์ `.saltkey.txt` คู่กับ dump เสมอ เพราะ `LITELLM_SALT_KEY`
> คือกุญแจถอดรหัส key ที่เก็บใน DB — `restore.sh` จะเช็คให้ว่าตรงกันก่อนเขียนทับ
> ถ้าไม่ตรงจะหยุดทันที ไม่ปล่อยให้ได้ DB ที่อ่านไม่ออก

## เวอร์ชันของ image

pin ไว้ที่เวอร์ชันที่ทดสอบผ่านจริง ไม่ใช้ `:latest` / `:main` เพื่อให้ทุกคนที่ clone
ได้ของชุดเดียวกัน:

| image | เวอร์ชัน |
|---|---|
| `ghcr.io/berriai/litellm` | v1.96.2 |
| `ghcr.io/open-webui/open-webui` | v0.11.0 |
| `postgres` | 16.14-alpine |
| `caddy` (prod) | 2.9.1-alpine |

อัปเกรด: แก้ tag ใน `docker-compose.yml` → `docker compose pull` → `docker compose up -d`
→ `./scripts/backup.sh` ก่อนเสมอถ้าเป็น major version

## License

[MIT](LICENSE)
