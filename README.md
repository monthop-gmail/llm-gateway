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
- **ทดสอบแล้วว่ารองรับ tool calling / streaming / Anthropic format / vision / embeddings**
  ใช้กับ AI agent และ coding agent ได้จริง ดู [CLIENTS.md](CLIENTS.md)
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
| **Groq** | `GROQ_API_KEY` | console.groq.com | เริ่มที่นี่ — ฟรี ไม่ต้องใช้บัตร |
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

## โมเดลที่ตั้งไว้ให้

รวม **105 โมเดล** จาก 9 provider — ทดสอบยิงจริงผ่านทั้งหมด (อัปเดต 2026-08-26)
ทุกตัวใช้ `sk-...` ใบเดียวกัน สลับโมเดลได้โดยไม่ต้องแก้ฝั่ง client

### โควต้าฟรีของแต่ละเจ้า — ดูก่อนเลือกโมเดล

ตัวเลขจากการวัดจริงที่บันทึกไว้ใน `test-hermes-free-model` บวกกับที่ provider ประกาศ
(ตรวจ 2026-08-26 — เปลี่ยนบ่อย ดูหน้า official ก่อนพึ่งพา)

| provider | โควต้าฟรี | เหมาะกับ |
|---|---|---|
| **Cerebras** | **~1,000,000 token/วัน** | งานหนัก แต่ระวัง TPM สะสม |
| Gemini (ยังไม่เปิด) | ~250,000 token/วัน | context ใหญ่ |
| Groq | ~200,000 token/วัน (ลดลงในปี 2026) | ยิงถี่ ตอบเร็ว |
| Mistral | 1B token/**เดือน** | งานทั่วไป โควต้าใจกว้าง |
| Cloudflare | 10,000 neurons/วัน | ทดลอง งานเบา |
| OpenRouter | 50–1,000 **req**/วัน แล้วแต่ยอดเติมเงิน | สลับโมเดลบ่อย |
| **OKMD** | **~40,000 token/วัน แชร์ทั้งตระกูล** | คุณภาพสูงเป็นครั้งคราว |
| ThaiLLM / Typhoon | จำกัดด้วย req/min (~50) | งานภาษาไทย |
| SEA-LION (ยังไม่เปิด) | 10 req/min | งานภาษาอาเซียน |
| Ollama Cloud | ไม่ประกาศ ("light usage") | ทั่วไป |
| HuggingFace | เครดิตรายเดือน — **หมดแล้ว** | — |

> **จุดที่คนพลาดบ่อยที่สุดคือ OKMD** — โควต้า ~40K token/วันนั้น **แชร์กันทั้งตระกูล**
> `okmd/claude-sonnet-5` กับ `okmd/claude-sonnet-4.6` กินก้อนเดียวกัน เช่นเดียวกับ
> ตระกูล gemini และ deepseek วัดจริงแล้วได้ราว **1 turn ต่อตระกูลต่อวัน**
> สำหรับงานที่ใช้ tool หนัก — ใช้เป็นตัวหลักของ coding agent ไม่ได้
>
> ถ้าต้องการโควต้าเยอะให้ไป **Cerebras** (1M/วัน) หรือ **Mistral** (1B/เดือน) แทน

> ### ⚠️ เครดิต HuggingFace หมดแล้ว (2026-08-23)
>
> `"You have depleted your monthly included credits"` — ยิงตรงไป HF ได้แค่ **1 จาก 21 โมเดล**
>
> **แต่ `hf/*` ทุกตัวยังใช้งานได้ตามปกติ** เพราะตั้ง `fallbacks` ใน `litellm/config.yaml`
> ให้วิ่งไป Groq / Cerebras / Cloudflare / Mistral / OpenRouter / Ollama Cloud แทน
> ทดสอบแล้ว **กู้ได้ครบ 21/21** — ฝั่ง client ไม่ต้องแก้อะไรเลย
>
> ถ้าจะกลับไปใช้ HF จริงต้องเติมเครดิตที่ https://huggingface.co/settings/billing

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
| `hf/glm-5.2` | zai-org/GLM-5.2 | **ใหม่** — รุ่นถัดจาก GLM-4.7 |
| `hf/kimi-k3` | moonshotai/Kimi-K3 | **ใหม่** — รุ่นถัดจาก K2.6 |
| `hf/deepseek-v4-pro` | deepseek-ai/DeepSeek-V4-Pro | **ใหม่** — รุ่นถัดจาก V3.2 |
| `hf/llama-4-scout` | meta-llama/Llama-4-Scout-17B-16E | **ใหม่** |
| `hf/qwen3.6-35b` | Qwen/Qwen3.6-35B-A3B | **ใหม่** |
| `hf/gemma-4-26b` | google/gemma-4-26B-A4B-it | **ใหม่** |
| `hf/sea-lion-gemma-27b` | aisingapore/Gemma-SEA-LION-v4-27B-IT | **ใหม่** — SEA-LION ฐาน Gemma |

> **Qwen3.8-27B — อัปเดต 2026-08-23** ตอนนี้มีให้ใช้ฟรีแล้วที่ Cloudflare (`cf/qwen3.8-27b`)
> ต่างจากตอนตรวจเมื่อ 2026-08-16 ที่ยังไม่มี provider ฟรี
> ส่วนบน HF router ยังมีแต่รุ่น 2.4T-A95B และ OpenRouter คิดเงิน ($0.40/M, context 1M)

### OpenRouter (โมเดลฟรี 10 ตัว — ทดสอบยิงจริงทุกตัว)

ต้องมี `OPENROUTER_API_KEY` ใน `.env` — สมัครฟรีที่ https://openrouter.ai/keys
ทุกตัวในตารางรองรับ tool calling (ทดสอบแล้ว)

| model_name | context | หมายเหตุ |
|---|---|---|
| `or/nemotron-ultra-550b` | 1M | ใหญ่ที่สุด ตอบไทยดี |
| `or/nemotron-lightning` | 1M | เร็ว แต่พ่น reasoning ปนมาใน content |
| `or/nemotron-super-120b` | 262K | |
| `or/north-mini-code` | 256K | เขียนโค้ด |
| `or/dots-3-note` | 512K | **ใหม่** — context ใหญ่สุดในกลุ่ม :free |
| `or/laguna-s-2.1` | 262K | **ใหม่** — สาย coding แต่ได้ 0/3 ใน benchmark |
| `or/ox-alpha` | **1M** | ฟรีแต่ไม่มี suffix `:free` |
| `or/minimax-m2.7` | 196K | **ใหม่ 08-26** |
| `or/nemotron-omni-30b` | 256K | **ใหม่ 08-26** — เมื่อ 08-23 ยังใช้ tool ไม่ได้ ตอนนี้ผ่านแล้ว |
| `or/auto-free` | — | **router ของ OpenRouter** เลือกโมเดลฟรีที่ว่างให้เอง |

> ⚠️ **ถอด `or/gemma-4-31b` เมื่อ 2026-08-26** — ขึ้น "Provider returned error" ต่อเนื่อง
>
> ⚠️ **ถอดออก 4 ตัวเมื่อ 2026-08-23 (รอบเย็น)** — `or/gpt-oss-20b` และ
> `or/nemotron-nano-30b` เปลี่ยนเป็นแบบเสียเงิน ส่วน `or/nemotron-nano-9b` และ
> `or/nemotron-vl-12b` ขึ้น "No endpoints found"
> **gateway จึงไม่มีโมเดล vision แล้ว** (ตัวที่เพิ่งเพิ่มเมื่อเช้าถูกถอด endpoint)

> **`or/auto-free` ใช้เป็นตาข่ายรองสุดท้าย** — ตั้งไว้ท้ายสุดของ `fallbacks` ทุกสายแล้ว
> ถ้า provider อื่นล่มหมด OpenRouter จะเลือกโมเดลฟรีที่ยังว่างให้เอง
> (ทดสอบแล้ววิ่งไป `nemotron-3-ultra-550b`)
>
> ตัวที่ลองแล้วใส่ไม่ได้ (2026-08-23): `z-ai/glm-5.2:free`,
> `google/gemma-4-26b-a4b-it:free`, `poolside/laguna-xs-2.1:free` และ
> `nvidia/llama-nemotron-rerank-vl-1b-v2:free` ขึ้น "Provider returned error"
> `thinkingmachines/inkling:free` จำกัดเฉพาะ agentic harness ส่วน
> `nemotron-3-nano-omni-...-reasoning:free` แชทได้แต่ใส่ tools แล้วคืน ResourceExhausted

เช็ครายชื่อโมเดลฟรีปัจจุบัน (เปลี่ยนบ่อย):

```bash
# ⚠️ กรองด้วย "ราคา = 0" ไม่ใช่ suffix :free — บางตัวฟรีแต่ไม่มี suffix
# (เช่น stealth/ox-alpha ที่ context 1M) ถ้ากรองด้วย :free จะพลาดไป 4 ตัว
curl -s https://openrouter.ai/api/v1/models | python3 -c '
import sys, json
free = []
for m in json.load(sys.stdin)["data"]:
    p = m.get("pricing") or {}
    if str(p.get("prompt")) in ("0", "0.0") and str(p.get("completion")) in ("0", "0.0"):
        free.append((m["id"], m.get("context_length") or 0))
for i, c in sorted(free, key=lambda x: -x[1]):
    print(i.ljust(50), "ctx=" + format(c, ","))
print("รวม", len(free), "ตัว")
'
```

ดูหน้ารวมได้ที่ https://openrouter.ai/collections/free-models

### Groq (`GROQ_API_KEY`) — เร็วที่สุด + ตัวเดียวที่เข้าเว็บได้

| model_name | ปลายทาง | หมายเหตุ |
|---|---|---|
| `gq/compound` | groq/compound | **ค้นเว็บ + เปิด URL ได้** |
| `gq/compound-mini` | groq/compound-mini | **ค้นเว็บ + เปิด URL ได้** เล็กกว่า เร็วกว่า |
| `gq/gpt-oss-120b` | openai/gpt-oss-120b | 3/3 ใน benchmark coding |
| `gq/qwen3.6-27b` | qwen/qwen3.6-27b | thinking model — ไม่เหมาะเขียนโค้ด |

> ⚠️ **Groq ปลด Llama ออกจาก free tier แล้ว (2026-08-23)** — `llama-3.3-70b-versatile`
> และ `llama-3.1-8b-instant` คืน `model_not_found` ถอดออกจาก config แล้ว
> ตัวหลังเคยเป็นตัวที่เร็วที่สุดใน gateway (181ms) ตอนนี้ตัวเร็วสุดคือ
> `cb/gemma-4-31b` (359ms)

### Cerebras (`CEREBRAS_API_KEY`) — เร็วที่สุดในกลุ่มที่เขียนโค้ดได้เต็ม

| model_name | เวลาตอบแชท | คะแนน coding | หมายเหตุ |
|---|---|---|---|
| `cb/gemma-4-31b` | **359ms** | **3/3 ใน 1.5s** | ดีที่สุดสำหรับ coding ในตอนนี้ |
| `cb/gpt-oss-120b` | 2.5s | **3/3 ใน 3.1s** | |

ทุกตัวรองรับ tool calling (ทดสอบแล้ว)

> `cb/glm-4.7` ถูกถอดออกเมื่อ 2026-08-23 — Cerebras archive โมเดลนี้แล้ว
> (`"Model zai-glm-4.7 is archived and unavailable for the organization"`)

> **ข้อจำกัดจริงคือ TPM ไม่ใช่ context** — บล็อกหลายที่เขียนว่า context จำกัด 8K
> แต่ทดสอบเองแล้วส่ง prompt **33,775 tokens ผ่านปกติ**
>
> ที่ชนคือ `token_quota_exceeded` (HTTP 429 "Tokens per minute limit exceeded")
> และเป็น **โควต้าสะสม ไม่ใช่ต่อ request** — หลังรัน benchmark ไปหลายรอบ
> prompt ขนาด ~25K ที่เคยผ่านก็เริ่มโดนปฏิเสธ ขณะที่ prompt เล็กยังใช้ได้ปกติ
> รอสักครู่ให้ reset แล้วกลับมาได้เอง
>
> ผลเชิงปฏิบัติ: เหมาะกับงานที่ยิงเป็นระยะและ prompt ไม่ใหญ่มาก
> **ไม่เหมาะกับ coding agent ที่อ่านไฟล์ทั้งโปรเจกต์เข้า context ซ้ำทุก turn**
> ถ้าจะใช้กับ agent ให้ตั้ง fallback ไป `cf/qwen2.5-coder-32b` รองรับไว้

### Mistral (`MISTRAL_API_KEY`) — 1B token/เดือน

| model_name | เหมาะกับ |
|---|---|
| `mi/small` `mi/medium` `mi/large` | งานทั่วไป |
| `mi/magistral-medium` | **ใหม่** — สาย reasoning ได้ **3/3 ใน 4.9s** ใน benchmark |
| `mi/magistral-small` | **ใหม่** — reasoning ตัวเล็ก (1/3) |
| `mi/codestral` `mi/mistral-code` `mi/mistral-code-agent` | เขียนโค้ด |
| `mi/mistral-code-fim` | **ใหม่ 08-26** — fill-in-the-middle เหมาะกับ autocomplete |
| `mi/ministral-3b` | **ใหม่ 08-26** — เล็กสุด เร็วสุด 373ms |
| `mi/devstral` `mi/devstral-medium` | coding agent โดยเฉพาะ |
| `mi/ministral-8b` `mi/ministral-14b` | เล็ก ประหยัด |

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
| `cf/qwen3.8-27b` | @cf/qwen/qwen3.8-27b — **ใหม่** thinking model |
| `cf/llama-4-scout` | @cf/meta/llama-4-scout-17b-16e-instruct — **ใหม่** |
| `cf/nemotron-3-120b` | @cf/nvidia/nemotron-3-120b-a12b — **ใหม่** |
| `cf/gemma-4-26b` | @cf/google/gemma-4-26b-a4b-it — **ใหม่** |
| `cf/qwen3-30b-a3b` | @cf/qwen/qwen3-30b-a3b-fp8 (ไม่เรียก tool) |
| `cf/mistral-small-24b` | @cf/mistralai/mistral-small-3.1-24b-instruct — **ใหม่ 08-26** |
| `cf/qwq-32b` | @cf/qwen/qwq-32b — **ใหม่ 08-26** thinking model |
| `cf/deepseek-r1-32b` | @cf/deepseek-ai/deepseek-r1-distill-qwen-32b — **ใหม่ 08-26** (ไม่เรียก tool) |
| `cf/granite-4-micro` | @cf/ibm-granite/granite-4.0-h-micro — **ใหม่ 08-26** เล็ก เร็ว 676ms |

> **Cloudflare มี vision แล้ว แต่ต้องกดยอมรับก่อน** — `@cf/meta/llama-3.2-11b-vision-instruct`
> คืน `"Model Agreement: Prior to using this model, you must agree..."`
> ไปกดที่ dash.cloudflare.com แล้วปลดคอมเมนต์ `cf/llama-3.2-vision` ใน config
> จะได้ vision กลับมา (ตอนนี้ gateway ไม่มี vision)

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

### OKMD AI Playground (`OKMD_API_KEY`) — ไทย 🇹🇭

`https://gen.ai.kku.ac.th/okmd/api/v1` — สร้าง key ที่ playground.okmd.or.th → API Platform
**key เดียวได้ 22 โมเดล** และเป็นที่เดียวใน gateway ที่มีโมเดลระดับ frontier

> ⚠️ **โควต้า ~40,000 token/วัน และแชร์กันทั้งตระกูล** — ดูตารางโควต้าด้านบน
> เหมาะกับงานที่ต้องการคุณภาพสูงเป็นครั้งคราว ไม่เหมาะเป็นตัวหลักของ agent

| model_name | หมายเหตุ |
|---|---|
| `okmd/claude-sonnet-5` `okmd/claude-sonnet-4.6` | **Claude** — ไม่มีที่อื่นใน gateway |
| `okmd/gpt-5.4` `okmd/gpt-5.4-mini` `okmd/gpt-5.4-nano` | **GPT-5.4** — ไม่มีที่อื่น |
| `okmd/grok-4.3` | **Grok** — ไม่มีที่อื่น |
| `okmd/gemini-3.7-flash` `okmd/gemini-3.5-flash` `okmd/gemini-3.1-pro` | Gemini รุ่นใหม่ |
| `okmd/gemini-3.1-flash-lite` `okmd/gemini-2.5-flash-lite` | Gemini ตัวเล็ก |
| `okmd/sonar-pro` | **Perplexity Sonar — ค้นเว็บได้** ตอบพร้อม citation |
| `okmd/deepseek-v4-pro` `okmd/deepseek-v4-flash` | DeepSeek V4 |
| `okmd/qwen3.7-max` `okmd/qwen3.7-plus` `okmd/qwen3.6-flash` | Qwen รุ่นใหม่กว่าที่อื่นใน gateway |
| `okmd/llama-4-maverick` `okmd/llama-4-scout` | Llama 4 |
| `okmd/mistral-medium-3.1` | |
| `okmd/nova-pro` `okmd/nova-2-lite` | Amazon Nova |

ทดสอบ tool calling แล้วผ่านทั้ง Claude Sonnet 5, GPT-5.4, Gemini 3.7, Grok 4.3

> `qwen3.5-9b` อยู่ใน `/v1/models` แต่ยิงจริงคืน `"No models provided"` — ยังไม่ได้ใส่

### ThaiLLM (`THAILLM_API_KEY`) — โมเดลไทย 🇹🇭

`https://thaillm.or.th` — 4 เจ้าคนละ endpoint แต่ใช้ key เดียวกัน

| model_name | เจ้าของ | หมายเหตุ |
|---|---|---|
| `th/typhoon` | SCB10X | ตอบตรง ไม่มี `<think>` — ใช้ง่ายสุดในกลุ่ม |
| `th/openthaigpt` | OpenThaiGPT | thinking model พ่น `<think>` ใน content |
| `th/pathumma` | NECTEC | thinking model |
| `th/thalle` | KBTG | thinking model |

> ⚠️ **ต้องตั้ง `extra_headers` User-Agent** — `thaillm.or.th` อยู่หลัง Cloudflare
> ที่บล็อก User-Agent ของ Python คืน `"error code: 1010"` / `"Your request was blocked"`
> ยิงด้วย `curl` จาก host ผ่าน แต่ผ่าน LiteLLM ไม่ผ่านถ้าไม่ตั้ง header
> config ตั้ง `{"User-Agent": "curl/8.5.0"}` ไว้ให้แล้วทั้ง 4 ตัว
>
> ทุกตัวใช้ model id ว่า `/model` จึงเขียนเป็น `openai//model` (สอง slash ไม่ใช่พิมพ์ผิด)

**ยังมีอีก 5 เจ้าที่เตรียม config ไว้แล้วแต่ยังไม่มี key** — ปลดคอมเมนต์ใน
`litellm/config.yaml` ได้ทันทีที่สมัคร:

| provider | endpoint | โควต้าฟรี | โมเดลที่เตรียมไว้ |
|---|---|---|---|
| **Typhoon ตรง** (SCB 10X) 🇹🇭 | `api.opentyphoon.ai/v1` | ~50 req/min, ctx 8K | `typhoon-v2.5-30b-a3b-instruct`, `typhoon-v2.1-12b-instruct` |
| **SEA-LION ตรง** (AI Singapore) 🇸🇬 | `api.sea-lion.ai/v1` | 10 req/min | `Qwen-SEA-LION-v4.5-27B-IT`, `Llama-SEA-LION-v3.5-70B-R` |
| **Chinda** (iApp) 🇹🇭 | `api.iapp.co.th/v3/llm/chinda-thaillm-4b` | ดูหน้าโปรฯ | `chinda-qwen3-4b` (ฐาน Qwen3-4B) |
| **KNPLabs** 🇹🇭 | `play.knplabai.com/ai/v1` (ฟรี)<br>`streamapi.knplabai.com/v1` (จ่ายเงิน) | — | `gpt-4o-mini` / tier จ่ายเงินมี 664 โมเดล |
| **Float16.cloud** 🇹🇭 | ⚠️ endpoint แยกต่อลูกค้า | — | โฮสต์ Typhoon/Qwen3/GPT-OSS บน H100 |

ต่างจากที่มีอยู่ตรงที่ยิงตรงเข้าเจ้าของโมเดล ไม่ผ่าน HF/Cloudflare/thaillm.or.th
จึงไม่กินโควต้าของตัวกลาง

> ชื่อโมเดลข้างบนยืนยันจาก `test-opencode-free-model/config/models.json` แล้ว
> — เดิมเดาไว้ผิด 2 ตัว (`Gemma-SEA-LION-v4-27B-IT` ที่จริงคือ `Qwen-SEA-LION-v4.5-27B-IT`
> และ `chinda-thaillm-4b` ที่จริงคือ `chinda-qwen3-4b`) ถ้าใส่ key แล้วยิงตามชื่อเดิมจะพัง
>
> **Float16 ไม่มี host กลาง** — `api.float16.cloud` คืน HTTP 000 ต้องตั้ง
> `FLOAT16_BASE_URL` ให้ตรงกับ endpoint ที่ได้รับตอนสมัคร
>
> **KNPLabs มี 2 tier คนละ host คนละ key** — tier จ่ายเงินมีบันทึกว่าทดสอบเมื่อ
> 2026-08-13 ผ่าน 11/12 latency กลาง 3.5 วิ

### Embeddings (NVIDIA NIM)

ใช้กับ RAG ได้ ทดสอบกับข้อความภาษาไทยแล้ว

| model_name | มิติ |
|---|---|
| `emb/nemotron-embed` | 2048 |

> ⚠️ **NVIDIA ปลด embedding เกือบหมดเมื่อ 2026-08-26** — `nv-embedqa-e5-v5` (คืน 410 Gone),
> `nv-embed-v1`, `llama-nemotron-embed-1b-v2` และ `baai/bge-m3` ขึ้น
> `"has reached its end of life"` เหลือ `nemotron-3-embed-1b` ตัวเดียวที่ยังใช้ได้

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

## โมเดลไหนเข้าเว็บได้ — ทดสอบแล้ว

**คำตอบสั้น: `gq/compound`, `gq/compound-mini` และ `okmd/sonar-pro`**

LLM ทั่วไปต่ออินเทอร์เน็ตไม่ได้ ที่จะค้นเว็บได้ต้องเป็น provider ที่แนบ tool
ฝั่ง server มาให้ — ในบรรดา 9 provider ที่ต่อไว้ มี Groq compound กับ OKMD sonar

| ความสามารถ | สถานะ | หลักฐาน |
|---|---|---|
| websearch | ✅ | Groq compound ตอบพร้อม `executed_tools: ['search']` + URL |
| webfetch (เปิด URL ที่ระบุ) | ✅ | `executed_tools: ['visit']` — สั่งเปิด example.com อ่านเนื้อหากลับมาตรง |
| websearch (อีกทาง) | ✅ | `okmd/sonar-pro` (Perplexity) ตอบพร้อม citation `[1][6]` — ทดสอบถามราคาทองวันนี้ได้ค่าจริง |

```bash
curl -s http://localhost:4000/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" -H "Content-Type: application/json" \
  -d '{"model":"gq/compound-mini","messages":[{"role":"user","content":"ราคาทองไทยวันนี้"}]}'
```

> **ข้อจำกัด** — หน้าเว็บใหญ่เกินจะคืน `Request Entity Too Large`
> (เปิด example.com ผ่าน แต่หน้า GitHub repo ไม่ผ่าน)

**โมเดลอื่นทั้งหมดเข้าเว็บไม่ได้** ทดสอบตัวแทนทุก provider ด้วยคำถามที่ต้องรู้
ข้อมูลหลัง training cutoff แล้ว — ทุกตัวตอบตรงๆ ว่าเข้าอินเทอร์เน็ตไม่ได้
ไม่มีตัวไหนเดามั่ว ถ้าต้องการให้โมเดลอื่นเข้าเว็บ ต้องทำ tool ฝั่ง client เอง
(ให้ agent เรียก search API แล้วป้อนผลกลับเข้า context) gateway ไม่ได้ทำให้อัตโนมัติ

## โมเดลไหนเขียนโค้ดได้ดี — วัดจริง

รันด้วย `scripts/bench-coding.py` โจทย์ 3 ข้อ ตรวจผลอัตโนมัติ (อัปเดต 2026-08-23):
คำนวณนิพจน์พร้อม edge case, LRU cache แบบมี TTL, แก้บั๊กจากโค้ดที่ให้มา
โค้ดที่โมเดลเขียนถูกรันใน container แยก ไม่ได้รันบนเครื่องตรงๆ

**เรียงตามคะแนนก่อน แล้วเวลาจากน้อยไปมาก** — เวลาคือผลรวมของทั้ง 3 โจทย์

### ✅ ทำครบทั้ง 3 ข้อ

| model_name | คะแนน | เวลารวม | provider | หมายเหตุ |
|---|---|---|---|---|
| `cb/gemma-4-31b` | **3/3** | **1.5s** | Cerebras | เร็วที่สุด — แต่ระวัง TPM ของ Cerebras |
| `cb/gpt-oss-120b` | **3/3** | 3.1s | Cerebras |  |
| `mi/magistral-medium` | **3/3** | 4.9s | Mistral | สาย reasoning โควต้า 1B token/เดือน |
| `cf/qwen2.5-coder-32b` | **3/3** | 15.6s | Cloudflare | โควต้าใจกว้าง เหมาะกับ agent ที่ยิงถี่ |
| `gq/gpt-oss-120b` | **3/3** | 26.2s | Groq | โควต้าประกาศชัด 30 RPM |
| or/nemotron-nano-30b | **3/3** | 28.9s | OpenRouter | _ถอดออกแล้ว — เปลี่ยนเป็นเสียเงิน_ |
| `oc/gpt-oss-120b` | **3/3** | 42.0s | Ollama Cloud |  |
| `or/nemotron-ultra-550b` | **3/3** | 51.9s | OpenRouter | context 1M |
| `or/ox-alpha` | **3/3** | 52.9s | OpenRouter | **context 1M** — ตัวเดียวที่ได้เต็มพร้อม context ยาว |
| `or/north-mini-code` | **3/3** | 97.6s | OpenRouter |  |

### ได้ 2 จาก 3

| model_name | คะแนน | เวลารวม | provider | หมายเหตุ |
|---|---|---|---|---|
| gq/llama-3.3-70b | 2/3 | 2.1s | Groq | _Groq ปลดออกจาก free tier แล้ว_ |
| `mi/codestral` | 2/3 | 4.9s | Mistral |  |
| `mi/mistral-code` | 2/3 | 8.7s | Mistral |  |
| `mi/mistral-code-agent` | 2/3 | 15.7s | Mistral | **ใหม่ 08-26** |
| `cf/mistral-small-24b` | 2/3 | 23.9s | Cloudflare | **ใหม่ 08-26** |
| `or/minimax-m2.7` | 2/3 | 76.7s | OpenRouter | **ใหม่ 08-26** |
| `mi/large` | 2/3 | 10.4s | Mistral |  |
| cb/glm-4.7 | 2/3 | 10.5s | Cerebras | _ถอดออกแล้ว — Cerebras archive_ |
| `hf/qwen3-coder-next` | 2/3 | 10.8s | HuggingFace |  |
| `mi/devstral` | 2/3 | 12.2s | Mistral |  |
| `mi/devstral-medium` | 2/3 | 13.5s | Mistral |  |
| `cf/llama-4-scout` | 2/3 | 21.5s | Cloudflare |  |
| `or/dots-3-note` | 2/3 | 54.5s | OpenRouter | context 512K |
| `cf/qwen3-30b-a3b` | 2/3 | 56.3s | Cloudflare |  |
| `or/auto-free` | 2/3 | 60.3s | OpenRouter | router — คะแนนไม่คงที่ ดูหมายเหตุด้านล่าง |

### ได้ 1 หรือ 0

| model_name | คะแนน | เวลารวม | provider | หมายเหตุ |
|---|---|---|---|---|
| `mi/ministral-3b` | 1/3 | 4.3s | Mistral | **ใหม่ 08-26** เล็กสุด |
| `mi/magistral-small` | 1/3 | 5.1s | Mistral |  |
| `cf/nemotron-3-120b` | 1/3 | 24.0s | Cloudflare |  |
| or/nemotron-vl-12b | 1/3 | 94.2s | OpenRouter | _ถอดออกแล้ว — No endpoints found_ |
| `gq/qwen3.6-27b` | 0/3 | 41.2s | Groq | พ่น `<think>` ใน content จน token หมด |
| `or/laguna-s-2.1` | 0/3 | 103.5s | OpenRouter |  |
| `cf/qwen3.8-27b` | 0/3 | 120.8s | Cloudflare | thinking model + Cloudflare timeout |

**เลือกยังไง**

- **เขียนโค้ด — เร็วที่สุด** → `cb/gemma-4-31b` ทำครบ 3 ข้อใน 1.5s เร็วกว่าอันดับถัดไป 10 เท่า
  แต่ระวัง TPM limit ของ Cerebras ถ้ายิงงานใหญ่ติดกัน
- **coding agent ที่ยิงถี่ต่อเนื่อง** → `cf/qwen2.5-coder-32b` (3/3, 15.6s) ช้ากว่าแต่โควต้าใจกว้าง
- **งานยากที่ต้องแม่น** → `gq/gpt-oss-120b` ได้เต็มเหมือนกัน และ Groq บอกโควต้าชัดเจน
- **autocomplete / งานสั้นๆ ที่ต้องการความเร็ว** → `cb/gemma-4-31b` (359ms) หรือ
  `mi/magistral-small` (498ms) ยอมแลกความแม่นบางส่วนกับความเร็ว
- **ต้องการข้อมูลสดจากเว็บ** → `gq/compound-mini` เป็นตัวเดียวที่ค้นเว็บได้
- **หลีกเลี่ยง** → `gq/qwen3.6-27b` เป็น thinking model ที่พ่น `<think>` ลงใน content
  แล้วใช้ token หมดก่อนเขียนโค้ดจบ ได้ 0/3

> ที่น่าสังเกต: โมเดลที่ตั้งชื่อว่าสาย coding ไม่ได้ชนะเสมอ — `mi/devstral`,
> `mi/mistral-code` และ `hf/qwen3-coder-next` ได้ 2/3 ขณะที่ `mi/magistral-medium`
> (สาย reasoning) กับ `gq/gpt-oss-120b` (ทั่วไป) ได้เต็ม
> ข้อที่ตกกันมากคือโจทย์ parser (ลำดับความสำคัญ + วงเล็บ + เลขติดลบ)

> **`or/auto-free` วัดคะแนนไม่ได้แน่นอน** — เป็น router ที่เลือกโมเดลให้ทุกครั้ง
> คะแนนจึงขึ้นกับว่ารอบนั้นวิ่งไปโมเดลไหน ใช้เป็น fallback ดี แต่อย่าใช้เป็นตัวหลัก
> เวลาต้องการผลที่ทำซ้ำได้

> **`cf/qwen3.8-27b` ได้ 0/3 — ไม่ใช่เพราะเขียนโค้ดไม่เป็น** ทดสอบแยกแล้วเขียนฟังก์ชัน
> ง่ายๆ ได้ถูกต้อง แต่เป็น thinking model ที่ใช้ token หมดไปกับการคิด
> (`finish_reason: length`, content ว่าง ที่ max_tokens 3000) และ Cloudflare
> ยังตัด request ทิ้งด้วย `AiError: Request timeout` เมื่อขอ 8000 tokens
> เหมาะกับงานถาม-ตอบสั้น ไม่เหมาะกับงานที่ต้องเขียนโค้ดยาว

รันเองกับโมเดลอื่น:

```bash
set -a; source .env; set +a
python3 scripts/bench-coding.py cf/qwen2.5-coder-32b gq/gpt-oss-120b mi/codestral
```

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
scripts/health-check.py         ยิงทุกโมเดลหาว่าตัวไหนตาย แยกจากตัวที่แค่โควต้าหมด
scripts/bench-coding.py         วัดความสามารถเขียนโค้ดของโมเดล
CLIENTS.md                      วิธีต่อ AI agent / coding agent
.env.example                    template — คัดลอกเป็น .env แล้วเติมค่า
```

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
