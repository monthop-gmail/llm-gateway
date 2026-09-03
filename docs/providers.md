# Provider ทั้ง 12 เจ้า

โควต้า วิธีขอ key และข้อควรระวังรายเจ้า

> ส่วนหนึ่งของ [llm-gateway](../README.md) — ตัวเลขทุกตัวมาจากการยิงจริง
> ไม่ใช่จากเอกสารของ provider ดู `INTEGRATION.md` ว่าฟิลด์ไหนเชื่อได้แค่ไหน

## โมเดลที่ตั้งไว้ให้

รวม **114 โมเดล** จาก 11 provider — ทดสอบยิงจริงผ่านทั้งหมด (อัปเดต 2026-08-26)
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
| **OpenCode Zen** | **ไม่ต้องมี key** แต่ ~15 req ติดกันก็ตัน | ตัวสำรอง ใช้ประปราย |
| **LLM7.io** | **ไม่ต้องมี key** (2 โมเดล) | ตัวสำรอง |
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
| `nim/minimax-m3` | tool calling ✅ (ยืนยันโดยโปรเจกต์ hermes 2026-08-25 — ข้อมูลเดิมที่ว่า 404 ตกยุคแล้ว) |
| `nim/llama-3.3-70b` | tool calling ✅ (ทดสอบซ้ำ 2026-08-26 — ข้อมูลเดิมที่ว่า timeout ตกยุคแล้ว) |
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
| `cf/qwen3-30b-a3b` | @cf/qwen/qwen3-30b-a3b-fp8 — tool calling ✅ (ทดสอบซ้ำ 2026-08-26) |
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

### OpenCode Zen — ⭐ ไม่ต้องมี API key เลย

`https://opencode.ai/zen/v1` — **เจ้าเดียวใน gateway ที่ยิงได้โดยไม่ต้องสมัครอะไร**
ไม่ต้อง login ไม่ต้องเติมเครดิต ใช้ได้ทันทีที่ clone repo

| model_name | ปลายทาง | หมายเหตุ |
|---|---|---|
| `zen/nemotron-3-ultra` | nemotron-3-ultra-free | โมเดลเดียวกับ `or/nemotron-ultra-550b` แต่ไม่กินโควต้า OpenRouter |
| `zen/nemotron-lightning` | nemotron-3.5-lightning-free | พ่น thinking ปนใน content |
| `zen/laguna-s-2.1` | laguna-s-2.1-free | สาย coding |
| `zen/x-preview-f` | x-preview-f-free | |
| `zen/hy3` | hy3-free | thinking model |
| `zen/mimo-v2.5` | mimo-v2.5-free | |
| `zen/big-pickle` | big-pickle | |

> ### ⚠️ สองเรื่องที่ต้องรู้
>
> **1. ต้องตั้ง `api_key: ""` เท่านั้น ห้ามใส่ค่าหลอก**
> ปลายทางตรวจ key จริง — ส่งค่ามั่วไปจะได้ `"Invalid API key"` แต่ถ้าไม่ส่ง
> header เลยหรือส่ง `Bearer` ว่าง จะเข้าโหมดฟรีที่ไม่ต้อง auth
> (เจอตอนใส่ `api_key: "no-key-needed"` แล้วพังทั้ง 7 ตัว)
>
> **2. rate limit เข้มมาก** — ยิงติดกันราว 15 ครั้งก็ขึ้น `"Rate limit exceeded"`
> ทดสอบครั้งล่าสุดผ่าน 5/7 ตัว ที่พัง 2 ตัวเป็นเพราะ rate limit ไม่ใช่ config ผิด
> **เหมาะกับใช้ประปรายหรือเป็นตัวสำรอง ไม่เหมาะกับ agent ที่ยิงถี่**

`/v1/models` มี 64 โมเดล (claude-*, gpt-5*, grok-*) แต่ตัวที่ไม่ลงท้าย `-free`
ตอบ `"Missing API key"` ทั้งหมด — ใช้ได้จริงเฉพาะที่อยู่ในตารางข้างบน
(`deepseek-v4-flash-free` กับ `muse-spark-1.2-contributor-free` ลงท้าย `-free`
แต่ยิงแล้วคืน upstream error / internal server error)

เช็ครายชื่อปัจจุบัน: `curl -s https://opencode.ai/zen/v1/models`

### LLM7.io — ไม่ต้องมี key (บางตัว)

`https://api.llm7.io/v1` — `/v1/models` มี **46 โมเดล** รวม `claude-opus-5`,
`gpt-5.6-sol`, `grok-4.6`, `gemini-3.7-flash` แต่ส่วนใหญ่คืน `"Missing API key"`

| model_name | หมายเหตุ |
|---|---|
| `l7/llama-3.1-8b` | meta-Llama-3.1-8B-Instruct-Turbo — ยิงได้เลย |
| `l7/codestral` | codestral-latest — ยิงได้เลย เขียนโค้ด |

> ขอ key ฟรีที่ https://llm7.io (ไม่ต้องใช้บัตร) แล้วเปลี่ยน `api_key` เป็น
> `os.environ/LLM7_API_KEY` จะปลดล็อกอีก 44 โมเดล — มีตัวอย่างคอมเมนต์ไว้ใน config

### ต้นทางของโมเดลที่ตอนนี้ใช้ผ่านคนกลาง (เตรียม config ไว้ รอ key)

GLM / Qwen / DeepSeek / Grok ของเราตอนนี้วิ่งผ่าน HF (เครดิตหมด),
OKMD (40K token/วัน) หรือ Cloudflare (10K neurons/วัน) — **ติดโควต้าคนกลางทั้งหมด**
ต่อตรงเข้าต้นทางจะได้โควต้าของตัวเองเต็มๆ

| provider | ต้นทางของ | สมัคร | บัตร |
|---|---|---|---|
| **Z AI (Zhipu)** | GLM | z.ai | ไม่ต้อง |
| **Alibaba Model Studio** | Qwen | modelstudio.console.alibabacloud.com | ไม่ต้อง |
| **DeepSeek** | DeepSeek | platform.deepseek.com | ไม่ต้อง |
| **Cohere** | Command-A (ยังไม่มีใน gateway เลย) | dashboard.cohere.com | ไม่ต้อง |
| **xAI** | Grok | console.x.ai | ⚠️ ต้องผูกบัตร |

endpoint ทั้งหมดยืนยันแล้วว่า path ถูก (คืน 401 ไม่ใช่ 404) เมื่อ 2026-08-26

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

### iApp Technology (`IAPP_API_KEY`) — ไทย 🇹🇭

สมัครฟรีที่ https://iapp.co.th — **ฟรีถึง 2026-09-30 เท่านั้น** หลังจากนั้นคิด
`0.01 / 0.02 IC ต่อ 1K token` (input/output) ดูฟิลด์ `free_until` ใน `model_info`

| โมเดล | ฐาน | จุดเด่น |
|---|---|---|
| `th/openthai2` | Qwen3.8-27B | context 256K · เข้าใจบริบทไทย |
| `th/openthai2-legal` | Nemotron-3-Nano-30B | **มี RAG ประมวลกฎหมายไทย 39 ฉบับ 6,300 มาตราในตัว** ตอบพร้อมเลขมาตรา |

โควตา **30 req/นาที** (ตัวหลักนับต่อ API key · ตัว legal นับต่อ IP) ไม่มีเพดานรายวัน

**ข้อควรระวังที่เจอจากการยิงจริง:**

- **`th/openthai2` เป็น thinking model** — คิดใน field `reasoning` ก่อนตอบ
  ใช้ ~85–100 token กับคำตอบคำเดียว ถ้า `max_tokens` ต่ำกว่า ~200 จะได้
  `content: null` พร้อม `finish_reason: length` โดยไม่มี error
- **`th/openthai2-legal` กิน prompt ~2,900 token ต่อคำถาม** แม้คำถามสั้นมาก
  เพราะ RAG ดึงตัวบทกฎหมายใส่มาให้ คิดเผื่อตอนคำนวณโควตา
- **tool calling ใช้ไม่ได้ทั้งสองตัว** ทั้งที่เอกสารบอกว่ารองรับ (BFCL 0.820) —
  ฝั่งเขาไม่ได้เปิด flag `--tool-call-parser` ตอน start vLLM ยิงจริงได้ error:
  `"auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`
  ลองครบทั้ง `auto` / `required` / ระบุชื่อฟังก์ชัน พังทั้งสามแบบ
- เอกสารให้ใช้ header `apikey:` แต่ **`Authorization: Bearer` ก็ผ่าน** จึงตั้ง config
  แบบ OpenAI-compatible ปกติได้ ไม่ต้อง `extra_headers`
- แต่ละโมเดลมี **base path ของตัวเอง** ต้องตั้ง `api_base` แยกรายตัว

### Typhoon (`TYPHOON_API_KEY`) — ไทย 🇹🇭 + OCR

API ของ SCB10X ตรง ต่างจาก `th/typhoon` ที่เป็นรุ่น 8B ซึ่งทำให้ ThaiLLM โดยเฉพาะ
สมัครที่ https://opentyphoon.ai — ไม่มีการคิดเงินในเอกสาร

| โมเดล | ใช้ทำอะไร | โควตา |
|---|---|---|
| `th/typhoon2.5` | แชทไทย 30B (MoE ใช้จริง 3B) · **เรียก tool ได้** · 307ms | 200 req/นาที |
| `ocr/typhoon` | OCR เอกสารไทย · 5.4s | **20 req/นาที** |
| `ocr/typhoon-v1.5` | OCR รุ่นใหม่กว่า · 6.3s | **20 req/นาที** |
| `asr/typhoon` | ถอดเสียงไทยเป็นข้อความ | 100 req/นาที |
| `asr/typhoon-isan` | ถอดเสียงไทยถิ่นอีสาน | 100 req/นาที |

**โควตาแยกต่อโมเดล ไม่ใช่ต่อ pool** — OCR จำกัดกว่าแชท 10 เท่า จึงแยก `quota_pool`
เป็น `typhoon` กับ `typhoon-ocr`

#### ASR ยิงคนละ endpoint กับแชท

`asr/*` เป็น `mode: audio_transcription` ต้องยิงที่ `/v1/audio/transcriptions`
แบบ multipart ไม่ใช่ `/v1/chat/completions`

```bash
curl -s http://localhost:4000/v1/audio/transcriptions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -F 'model=asr/typhoon' -F 'file=@เสียง.wav;type=audio/wav'
```

⚠️ **ต้องใส่ `;type=audio/wav` เอง** — curl เดาเป็น `application/octet-stream`
แล้วปลายทางตอบ `400 File type application/octet-stream not supported.
Supported formats: wav, flac, mp3, ogg, opus` ซึ่งอ่านแล้วเหมือนไฟล์เสีย
ทั้งที่ไฟล์ถูกต้อง แค่ประกาศชนิดไม่ครบ

**ยังไม่ได้วัดความแม่น** — ยิงผ่านด้วยไฟล์เงียบ 200ms ได้ `{"text":"", "usage":{...}}`
ถูกรูปแบบ ยืนยันได้แค่ว่าเส้นทางใช้ได้ ไม่ได้ยืนยันคุณภาพการถอดเสียง

#### ไม่มี TTS

`/v1/audio/speech` คืน 404 จากต้นทาง — Typhoon ไม่มีบริการสังเคราะห์เสียง
`./scripts/pick-model.sh tts` จึงขึ้น 0 ตัว (หมวดมีไว้รอ ไม่ใช่ลืมใส่)

#### ⚠️ OCR ไวต่อ prompt มากจนน่าตกใจ

ทดสอบกับงบแสดงฐานะการเงินภาษาไทย (ตัวเลข 20 จำนวน) รันซ้ำ 2 รอบทุกแบบ:

| prompt | ผล |
|---|---|
| `อ่านเอกสารนี้ให้ครบ รักษาตัวเลขทุกตัวตามที่พิมพ์` | **20/20** ทั้ง 2 รอบ |
| `Extract all text and tables from this document.` | **20/20** ทั้ง 2 รอบ |
| `อ่านเอกสารนี้ให้ครบ รักษาตัวเลขทุกตัว` | **0/20** ทั้ง 2 รอบ |
| `อ่านเอกสารนี้` | **0/20** ทั้ง 2 รอบ |

**เวลาพัง มันไม่ error** — คืน template คำสั่งของตัวเองมาแทน:

```
Extract all text from the image.
Instructions:
- Only return the clean Markdown.
...
```

ปลายทางที่ไม่ตรวจผลจะได้ข้อความหน้าตาสมเหตุสมผลแต่ไม่มีข้อมูลจากเอกสารเลย
**ให้เช็คว่าผลมีตัวเลข/เนื้อหาที่คาดว่าจะเจอจริงก่อนใช้ต่อเสมอ**

#### ผลอ่านคืนเป็นตาราง HTML

```html
<table><tr><td>เงินสดและรายการเทียบเท่าเงินสด</td><td>1,245,830</td><td>987,412</td></tr>
```

เอาไปแปลงเป็น DataFrame ต่อได้เลย ไม่ต้อง parse ข้อความดิบ

#### context ของตัวแชทมากกว่าที่เอกสารบอก

เอกสารระบุ 32,768 แต่ยิงจริงผ่านที่ **63,389 token** จึงตั้ง `verified_max_prompt`
ตามที่วัดได้ ไม่ใช่ตามสเปก

#### ⚠️ ถ้าใช้ production เขาขอให้ไปทาง Together AI

เอกสารเขียนว่า *"If you plan to use our API for the real production use, please
support us by using the API through Together AI, our infrastructure partner"*
— endpoint นี้ฟรีสำหรับพัฒนา/ทดสอบ ถ้าจะใช้หนักควรคุยกับเขาก่อน
