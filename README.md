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
  curl / SDK / n8n ────►│   LiteLLM    ├─► Groq / Mistral / Cloudflare / NVIDIA NIM
  Cline / Aider / ...   │  :4000 /v1   ├─► OpenRouter / Ollama Cloud
  (sk-... virtual key)  │              ├─► vLLM / Ollama ที่รันเอง (ถ้ามี GPU)
                        └──────┬───────┘
                               │
                          Postgres  (virtual keys, budget, spend log)
```

## จุดสำคัญ

- **ออก token ได้เอง** — LiteLLM สร้าง virtual key (`sk-...`) ต่อคน/ต่อแอป กำหนด budget,
  โมเดลที่เข้าถึงได้, วันหมดอายุ และดู spend ย้อนหลังได้
- **key จริงของ provider อยู่ที่ server เดียว** — ผู้ใช้ไม่เคยเห็น HF token
- **เพิ่ม backend ทีหลังไม่กระทบ client** — แก้ `litellm/config.yaml` (หรือเพิ่มผ่าน UI)
  แล้ว key เดิมยิงโมเดลใหม่ได้เลย
- **ทดสอบแล้วว่ารองรับ tool calling / streaming / Anthropic format** — ใช้กับ AI agent
  และ coding agent ได้จริง ดู [CLIENTS.md](CLIENTS.md)

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

แล้วใส่ **HuggingFace token** — สร้างที่ https://huggingface.co/settings/tokens
เลือกแบบ **Fine-grained** ติ๊ก permission **"Make calls to Inference Providers"**
(ไม่ติ๊กจะได้ 401 ทุก request)

```bash
# แก้บรรทัด HF_TOKEN= ใน .env แล้ว
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
  -d '{"model":"hf/qwen2.5-7b","messages":[{"role":"user","content":"สวัสดี"}]}'
```

## ออก token ให้ผู้ใช้

```bash
./scripts/gen-key.sh --alias somchai --budget 5 --models hf/qwen2.5-7b,hf/llama-3.1-8b
./scripts/gen-key.sh --alias n8n-bot --duration 90d
./scripts/gen-key.sh --alias cline                # เต็มสิทธิ์ ไม่มี budget
```

หรือกดออกจากหน้า **Virtual Keys** ใน `/ui`

ผู้ใช้เอา key ไปใช้กับอะไรก็ได้ที่คุยภาษา OpenAI ได้:

```python
from openai import OpenAI
client = OpenAI(base_url="http://<host>:4000/v1", api_key="sk-....")
client.chat.completions.create(model="hf/qwen2.5-7b", messages=[...])
```

**แนะนำ:** เปลี่ยน `OPENWEBUI_LITELLM_KEY` ใน `.env` จาก master key เป็น virtual key
แล้ว `docker compose up -d openwebui` — จะได้แยก spend ของหน้าแชทออกจาก key อื่น

## โมเดลที่ตั้งไว้ให้

รวม **50 โมเดล** จาก 6 provider — ทดสอบยิงจริงผ่านทั้งหมด (อัปเดต 2026-08-17)
ทุกตัวใช้ `sk-...` ใบเดียวกัน สลับโมเดลได้โดยไม่ต้องแก้ฝั่ง client

### HuggingFace (ต้องมี `HF_TOKEN`)

| model_name | ปลายทาง | เหมาะกับ |
|---|---|---|
| `hf/llama-3.1-8b` | meta-llama/Llama-3.1-8B-Instruct | เล็ก เร็ว ประหยัด |
| `hf/qwen2.5-7b` | Qwen/Qwen2.5-7B-Instruct | ภาษาไทยดี |
| `hf/gemma-3-12b` | google/gemma-3-12b-it | |
| `hf/gpt-oss-20b` | openai/gpt-oss-20b | |
| `hf/llama-3.3-70b` | meta-llama/Llama-3.3-70B-Instruct | agent ที่เรียก tool |
| `hf/gpt-oss-120b` | openai/gpt-oss-120b | |
| `hf/qwen3.5-397b` | Qwen/Qwen3.5-397B-A17B | งานยาก |
| `hf/qwen3.6-27b` | Qwen/Qwen3.6-27B | Qwen รุ่นใหม่สุดที่ยังฟรี |
| `hf/sea-lion-32b` | aisingapore/Qwen-SEA-LION-v4-32B-IT | เน้นภาษาอาเซียน/ไทย |
| `hf/glm-4.7` | zai-org/GLM-4.7 | thinking model — ช้า |
| `hf/kimi-k2.6` | moonshotai/Kimi-K2.6 | thinking model — ช้า |
| `hf/deepseek-r1` | novita/deepseek-ai/DeepSeek-R1 | reasoning |
| `hf/deepseek-v3.2` | deepseek-ai/DeepSeek-V3.2 | |
| `hf/qwen3-coder-next` | Qwen/Qwen3-Coder-Next | เขียนโค้ด |

> **Qwen3.8-27B** (ออก 2026-08-05) ตรวจแล้วเมื่อ 2026-08-16 — ยังไม่มี provider ฟรี
> ไม่อยู่ใน HF router, ไม่มีบน Groq/Cloudflare/NVIDIA NIM
> มีบน OpenRouter แต่คิดเงิน ($0.45/M prompt) ตอนนี้ใช้ `hf/qwen3.6-27b` แทนไปก่อน

### OpenRouter (โมเดล `:free` — ทดสอบผ่านทั้งหมดเมื่อ 2026-08-15)

ต้องมี `OPENROUTER_API_KEY` ใน `.env` — สมัครฟรีที่ https://openrouter.ai/keys
ทั้ง 6 ตัวรองรับ tool calling (ทดสอบแล้ว)

| model_name | context | หมายเหตุ |
|---|---|---|
| `or/nemotron-ultra-550b` | 1M | ใหญ่ที่สุด ตอบไทยดี |
| `or/nemotron-lightning` | 1M | เร็ว แต่พ่น reasoning ปนมาใน content |
| `or/nemotron-super-120b` | 262K | |
| `or/gemma-4-31b` | 262K | ตอบไทยดี |
| `or/gpt-oss-20b` | 131K | ต้องให้ max_tokens สูงพอ ไม่งั้นได้แต่ reasoning |
| `or/north-mini-code` | 256K | เขียนโค้ด |

เช็ครายชื่อ `:free` ปัจจุบัน (เปลี่ยนบ่อย):

```bash
curl -s https://openrouter.ai/api/v1/models | python3 -c \
  'import sys,json;[print(m["id"],m.get("context_length")) for m in json.load(sys.stdin)["data"] if m["id"].endswith(":free")]'
```

### Groq (`GROQ_API_KEY`) — เร็วที่สุด

วัดจริงผ่าน gateway: `gq/llama-3.1-8b` ตอบใน **181ms**, 70B ใน 688ms

| model_name | ปลายทาง |
|---|---|
| `gq/llama-3.3-70b` | llama-3.3-70b-versatile |
| `gq/llama-3.1-8b` | llama-3.1-8b-instant |
| `gq/gpt-oss-120b` | openai/gpt-oss-120b |
| `gq/qwen3.6-27b` | qwen/qwen3.6-27b |

### Mistral (`MISTRAL_API_KEY`) — 1B token/เดือน

| model_name | เหมาะกับ |
|---|---|
| `mi/small` `mi/medium` `mi/large` | งานทั่วไป |
| `mi/codestral` | เขียนโค้ด |
| `mi/devstral` | coding agent โดยเฉพาะ |
| `mi/ministral-8b` | เล็ก ประหยัด |

### NVIDIA NIM (`NVIDIA_NIM_API_KEY`)

| model_name | หมายเหตุ |
|---|---|
| `nim/deepseek-v4-flash` | tool calling ✅ |
| `nim/gemma-4-31b` | tool calling ✅ |
| `nim/mistral-nemotron` | tool calling ✅ |
| `nim/step-3.7-flash` | tool calling ✅ |
| `nim/minimax-m3` | chat ได้ แต่ **ใส่ tools แล้ว 404** |
| `nim/llama-3.3-70b` | chat ได้ แต่ **ใส่ tools แล้วค้างจน timeout** |
| `nim/nemotron-nano-30b` | พ่น reasoning ปนใน content |
| `nim/nemotron-super-49b` | thinking model |

> `/v1/models` ของ NIM โฆษณา 102 โมเดล แต่ส่วนใหญ่คืน 404 `Not found for account`
> ต้องยิงจริงถึงจะรู้ว่าตัวไหนใช้ได้

### Cloudflare Workers AI (`CLOUDFLARE_API_KEY` + `CLOUDFLARE_ACCOUNT_ID`)

| model_name | ปลายทาง |
|---|---|
| `cf/sea-lion-27b` | @cf/aisingapore/gemma-sea-lion-v4-27b-it |
| `cf/llama-3.3-70b` | @cf/meta/llama-3.3-70b-instruct-fp8-fast |
| `cf/qwen2.5-coder-32b` | @cf/qwen/qwen2.5-coder-32b-instruct |

> โมเดลใหญ่บางตัว (glm-5.2, deepseek-v4) **ไม่อยู่ใน Workers Free plan**
> คืน error `code 5035` ต้องอัปเกรดแผน

### Ollama Cloud (`OLLAMA_API_KEY`) — โมเดลใหญ่โดยไม่ต้องมี GPU

Ollama โฮสต์ให้ ไม่กิน RAM/GPU เครื่องเรา สร้าง key ที่ https://ollama.com/settings/keys
**ชั้นฟรีใช้ได้ 7 จาก 19 โมเดล** (ทดสอบ 2026-08-17) ทุกตัวรองรับ tool calling

| model_name | เวลาตอบ | หมายเหตุ |
|---|---|---|
| `oc/gpt-oss-120b` | 1.5s | เร็วสุดในกลุ่ม |
| `oc/minimax-m3` | 1.5s | |
| `oc/nemotron-3-nano-30b` | 1.4s | |
| `oc/gpt-oss-20b` | 2.7s | |
| `oc/nemotron-3-ultra` | 3.7s | ใหญ่สุดที่ฟรี |
| `oc/nemotron-3-super` | 7.0s | thinking model |
| `oc/gemma4-31b` | 13.3s | ช้าสุด |

**ต้องมี Pro ($20/เดือน) ขึ้นไป** — คืน `this model requires a subscription`:
`glm-5.1` `glm-5.2` `qwen3.5:397b` `mistral-large-3:675b` `deepseek-v4-flash`
`deepseek-v4-pro` `kimi-k2.6` `kimi-k2.7-code` `minimax-m2.7`
ส่วน `kimi-k3` ต้อง Pro/Max/Team **บวก** extra usage

> Ollama ไม่ประกาศตัวเลขโควต้าฟรีเลย ทดลองยิงรัว 15 ครั้งติดไม่โดน rate limit
> แต่ไม่ได้แปลว่าไม่มีเพดาน — ดูการใช้งานจริงที่หน้า settings ของบัญชี

### Embeddings (NVIDIA NIM)

ใช้กับ RAG ได้ ทดสอบกับข้อความภาษาไทยแล้ว

| model_name | มิติ |
|---|---|
| `emb/nemotron-embed` | 2048 |
| `emb/nv-embedqa-e5` | 1024 (ตั้ง `input_type: passage` ไว้ในconfig เพราะโมเดลบังคับ) |

โมเดลบน HF ถูกปลด/เพิ่มเป็นระยะ เช็คว่าตอนนี้มีอะไรใช้ได้:

```bash
source .env
curl -s https://router.huggingface.co/v1/models -H "Authorization: Bearer $HF_TOKEN" \
  | python3 -c 'import sys,json;[print(m["id"], [p["provider"] for p in m.get("providers",[]) if p.get("status")=="live"]) for m in json.load(sys.stdin)["data"]]'
```

`litellm/config.yaml` ใช้รูปแบบ **auto-route** (`huggingface/<org>/<model>`) เป็นหลัก
ให้ HF เลือก provider ที่ว่างเอง ทนกว่าการล็อก provider ตัวเดียว
ถ้าจะล็อกให้ใช้ `huggingface/<provider>/<org>/<model>`

> บาง provider (เช่น groq) อาจตอบ `Not allowed to POST ... for provider X`
> แปลว่าบัญชี HF ยังไม่มีสิทธิ์/billing กับ provider นั้น ให้ใช้ auto-route แทน

## เพิ่ม backend

แก้ `litellm/config.yaml` (มีตัวอย่างคอมเมนต์ไว้ครบ) แล้ว `docker compose restart litellm`

**vLLM** — ต้องมี GPU รันแยกแล้วชี้มา:
```yaml
- model_name: local/vllm-qwen
  litellm_params:
    model: hosted_vllm/Qwen/Qwen2.5-7B-Instruct
    api_base: os.environ/VLLM_API_BASE    # http://<gpu-host>:8000/v1
    api_key: "dummy"
```

**Ollama (รันเอง)**:
```yaml
- model_name: local/ollama-llama3
  litellm_params:
    model: ollama_chat/llama3.1:8b
    api_base: os.environ/OLLAMA_API_BASE  # http://<host>:11434
```

**Ollama Cloud** — Ollama โฮสต์โมเดลใหญ่ให้ ไม่ต้องมี GPU และไม่กิน RAM เครื่องเรา
เป็น OpenAI-compatible แท้ (`https://ollama.com/v1`) จึงใช้ prefix `openai/` + `api_base`
สร้าง key ที่ https://ollama.com/settings/keys แล้วใส่ `OLLAMA_API_KEY` ใน `.env`

```yaml
- model_name: oc/glm-5.2
  litellm_params:
    model: openai/glm-5.2
    api_base: https://ollama.com/v1
    api_key: os.environ/OLLAMA_API_KEY
```

มี 19 โมเดล cloud รวมตัวที่หาฟรีที่อื่นไม่ได้ — `qwen3.5:397b`, `mistral-large-3:675b`,
`deepseek-v4-pro`, `kimi-k3`, `glm-5.2` มีบล็อกคอมเมนต์ไว้ใน `litellm/config.yaml` แล้ว
เช็ครายชื่อ: `curl -s https://ollama.com/v1/models`

> ชั้นฟรีมีจริง ($0 "light usage") แต่ Ollama **ไม่ประกาศตัวเลขโควต้า** ดูการใช้งาน
> จริงได้ที่หน้า settings ของบัญชี — Pro $20/เดือน ได้โควต้า 50 เท่า

**Cloud** — ใส่ API key ที่ `.env` (มีตัวแปรรออยู่แล้ว) แล้วเปิดคอมเมนต์ใน config.yaml

> ตั้ง `store_model_in_db: true` ไว้ — เพิ่มโมเดลผ่านหน้า UI ได้โดยไม่ต้องแตะไฟล์
> แต่ของที่เพิ่มผ่าน UI จะอยู่ใน DB ไม่อยู่ใน git ของถาวรควรเขียนลง `config.yaml`

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
CLIENTS.md                      วิธีต่อ AI agent / coding agent
.env.example                    template — คัดลอกเป็น .env แล้วเติมค่า
```

### scripts/

```bash
# ออก virtual key
./scripts/gen-key.sh --alias somchai --budget 5 --models hf/qwen2.5-7b

# เปลี่ยน HF token (ตรวจสิทธิ์ก่อนเขียน .env แล้วยิงทดสอบทุกโมเดล)
./scripts/rotate-hf-token.sh hf_xxxxxxxx

# ตรวจ config ก่อน push — CI เรียกตัวเดียวกันนี้
./scripts/validate.sh
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
