# ผลวัดจริง

โมเดลไหนเข้าเว็บได้ · โมเดลไหนเขียนโค้ดได้ดี

> ส่วนหนึ่งของ [llm-gateway](../README.md) — ตัวเลขทุกตัวมาจากการยิงจริง
> ไม่ใช่จากเอกสารของ provider ดู `INTEGRATION.md` ว่าฟิลด์ไหนเชื่อได้แค่ไหน

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
