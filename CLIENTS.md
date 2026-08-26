# ต่อ AI agent / coding agent เข้ากับ gateway นี้

ทดสอบจริง อัปเดต 2026-08-26 — สิ่งที่ gateway นี้รองรับ:

| ความสามารถ | สถานะ | หมายเหตุ |
|---|---|---|
| OpenAI Chat Completions `/v1/chat/completions` | ✅ | endpoint หลัก |
| Streaming (SSE) | ✅ | |
| **Tool / function calling** | ✅ | ทดสอบทุก provider แล้ว — ส่วนใหญ่ผ่าน มีข้อยกเว้นรายตัวใน README |
| Anthropic format `/v1/messages` | ✅ | ใช้กับ Claude Code ได้ |
| `/v1/models` | ✅ | client ส่วนใหญ่ดึงรายชื่อโมเดลอัตโนมัติ |
| Embeddings | ✅ | `emb/nemotron-embed` (2048 มิติ) — NVIDIA ปลดตัวอื่นหมดแล้ว |
| Vision (รูปภาพ) | ❌ | Cloudflare มี llama-3.2-11b-vision แต่ต้องกดยอมรับ Model Agreement ก่อน — ดู README |
| **ค้นเว็บ / เปิด URL** | ✅ | `gq/compound`, `gq/compound-mini` (มี webfetch ด้วย), `okmd/sonar-pro` |

**ค่าที่ต้องใช้ทุก client:**

```
Base URL : https://llm-api.example.com/v1     ← เปลี่ยนเป็น API_DOMAIN ของคุณ
API Key  : sk-...                             ← ออกด้วย ./scripts/gen-key.sh
Model    : cb/gemma-4-31b, cf/qwen2.5-coder-32b, gq/compound-mini, ... (ดู README)
```

ตอนยังเป็น dev (ยังไม่มีโดเมน) ใช้ IP:port ตรงๆ ได้:

```
Base URL : http://<host>:4000/v1     (ในเครื่องเดียวกัน: http://localhost:4000/v1)
หน้าแชท  : http://<host>:3000
```

> Cursor และบริการ cloud อื่นๆ บังคับ **https** — ใช้กับ URL แบบ http ไม่ได้
> ต้อง deploy พร้อมโดเมนก่อน (ดูหัวข้อ "Deploy production" ใน README.md)
> ส่วน Cline / Aider / Continue / n8n ที่รันในเครื่องตัวเอง ใช้ http ได้เลย

ออก key แยกต่อเครื่องมือ จะได้ดู spend แยกกันและ revoke ทีละตัวได้:

```bash
./scripts/gen-key.sh --alias cline    --models cf/qwen2.5-coder-32b,gq/gpt-oss-120b
./scripts/gen-key.sh --alias n8n      --budget 2
./scripts/gen-key.sh --alias aider    --duration 90d
```

---

## Coding agents

### Cline / Roo Code / Kilo Code (VS Code)

Settings → API Provider → **OpenAI Compatible**

```
Base URL : https://llm-api.example.com/v1
API Key  : sk-...
Model ID : cf/qwen2.5-coder-32b
```

ติ๊ก **Enable streaming** ไว้ และเปิด **Function Calling / Tools** (ทดสอบแล้วรองรับ)

### Continue.dev

`~/.continue/config.yaml`:

```yaml
models:
  - name: qwen-coder
    provider: openai
    model: cf/qwen2.5-coder-32b
    apiBase: https://llm-api.example.com/v1
    apiKey: sk-...
    roles: [chat, edit, apply]
  - name: fast
    provider: openai
    model: cb/gemma-4-31b
    apiBase: https://llm-api.example.com/v1
    apiKey: sk-...
    roles: [autocomplete]
```

### Aider

```bash
export OPENAI_API_BASE=https://llm-api.example.com/v1
export OPENAI_API_KEY=sk-...
aider --model openai/cf/qwen2.5-coder-32b
```

หรือใส่ถาวรใน `~/.aider.conf.yml`:

```yaml
openai-api-base: https://llm-api.example.com/v1
openai-api-key: sk-...
model: openai/cf/qwen2.5-coder-32b
```

### Claude Code

LiteLLM มี `/v1/messages` (รูปแบบ Anthropic) ให้ ชี้ Claude Code มาที่นี่ได้:

```bash
export ANTHROPIC_BASE_URL=https://llm-api.example.com
export ANTHROPIC_AUTH_TOKEN=sk-...
export ANTHROPIC_MODEL=cf/qwen2.5-coder-32b
export ANTHROPIC_SMALL_FAST_MODEL=cb/gemma-4-31b
claude
```

> ⚠️ ใช้ได้ทางเทคนิค แต่ **คุณภาพจะตกลงเยอะ** — prompt/tool ของ Claude Code ปรับจูนมาสำหรับโมเดล Claude
> โดยเฉพาะ โมเดล open-weight มักพลาดเรื่อง tool ซ้อนหลายชั้นและ context ยาว
> เหมาะกับงานทดลอง/งานเบา ไม่แนะนำเป็นตัวหลัก

### OpenCode / Goose / Zed

ทั้งสามตัวรับ OpenAI-compatible endpoint — ใส่ base URL + key + model id ตามหน้า settings ของแต่ละตัว
Zed: `~/.config/zed/settings.json` → `language_models.openai.api_url`

---

## AI agent frameworks

### n8n

Credentials → **OpenAI** → Base URL `https://llm-api.example.com/v1`, API Key `sk-...`
แล้วใน node "OpenAI Chat Model" พิมพ์ชื่อโมเดลเอง เช่น `gq/gpt-oss-120b`

ถ้า n8n รันเป็น container บนเครื่องเดียวกัน ต่อ network `llm-net` แล้วใช้ `http://llm-litellm:4000/v1` จะเร็วกว่าและไม่ออกอินเทอร์เน็ต

### Dify / Flowise

Model Provider → **OpenAI-API-compatible**
API endpoint `https://llm-api.example.com/v1`, key `sk-...`, model name ตามที่ตั้งไว้

### Python — OpenAI SDK / LangChain / LlamaIndex / CrewAI

```python
from openai import OpenAI
client = OpenAI(base_url="https://llm-api.example.com/v1", api_key="sk-...")
r = client.chat.completions.create(
    model="cf/qwen2.5-coder-32b",
    messages=[{"role": "user", "content": "เขียน fizzbuzz"}],
)
```

```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    base_url="https://llm-api.example.com/v1",
    api_key="sk-...",
    model="gq/gpt-oss-120b",
)
```

CrewAI / LiteLLM-native ใช้ชื่อ `openai/gq/gpt-oss-120b` พร้อม `OPENAI_API_BASE`

---

## เลือกโมเดลยังไง

| งาน | แนะนำ |
|---|---|
| **งานที่ต้องการคุณภาพสูงสุด** | `okmd/claude-sonnet-5`, `okmd/gpt-5.4` — frontier model ผ่าน OKMD |
| **เขียนโค้ด — เร็วสุด** | `cb/gemma-4-31b` (3/3 ใน 1.5s) — ระวัง TPM limit ของ Cerebras |
| **เขียนโค้ด — สมดุลสุด** | `mi/magistral-medium` (3/3 ใน 4.9s) โควต้า Mistral 1B token/เดือน |
| **coding agent ที่ยิงถี่** | `cf/qwen2.5-coder-32b` (3/3, 15.6s) โควต้าใจกว้างกว่า |
| **autocomplete ในบรรณาธิการ** | `mi/mistral-code-fim` (FIM โดยเฉพาะ), `mi/ministral-3b` (373ms) |
| agent ที่เรียก tool เยอะ | `gq/gpt-oss-120b`, `or/nemotron-ultra-550b` |
| งานเบา/จัดหมวด/สรุป (ประหยัด) | `mi/ministral-8b`, `cb/gemma-4-31b` |
| งานที่ต้องคิดเยอะ | `mi/magistral-medium`, `cb/gpt-oss-120b` — ช้ากว่าแต่แม่นกว่า |
| ต้องการความเร็วสูงสุด | `cb/gemma-4-31b` (359ms), `mi/magistral-small` (498ms) |
| context ยาวมาก | `or/nemotron-ultra-550b` (1M), `or/nemotron-lightning` (1M) |
| ภาษาไทยโดยเฉพาะ | `th/typhoon` (โมเดลไทย), `cf/sea-lion-27b` |
| RAG / embeddings | `emb/nemotron-embed` |
| ต้องการข้อมูลสดจากเว็บ | `gq/compound-mini` (ค้น+เปิด URL), `okmd/sonar-pro` (citation) |
| ไม่อยากเลือกเอง / กันล่ม | `or/auto-free` — OpenRouter เลือกให้ (ผลไม่คงที่ ไม่เหมาะเป็นตัวหลัก) |
| coding บน OpenRouter | `or/ox-alpha` (3/3, ctx 1M) |

ตัวเลข coding มาจากการวัดจริงด้วย `scripts/bench-coding.py` — ดูตารางเต็มใน README

> ⚠️ อย่าใช้ `gq/qwen3.6-27b` กับงานเขียนโค้ด — เป็น thinking model ที่พ่น `<think>`
> ลงใน content แล้วใช้ token หมดก่อนเขียนโค้ดจบ ได้ 0/3 ในการทดสอบ

## ข้อควรระวัง

- **coding agent กิน token มหาศาล** (อ่านไฟล์ทั้งโปรเจกต์เข้า context ทุกรอบ)
  ให้ออก key แบบมี `--budget` เสมอ ไม่ว่าจะใช้ provider ไหน
- ดู spend ได้ที่ https://llm-api.example.com/ui → **Usage** แยกตาม key ได้
- ถ้าเจอ rate limit จาก provider ให้เพิ่ม fallback ใน `litellm/config.yaml`:
  ```yaml
  litellm_settings:
    fallbacks: [{"cf/qwen2.5-coder-32b": ["gq/gpt-oss-120b", "mi/codestral"]}]
  ```
- context window ต่างกันมาก (8k ถึง 1M) coding agent มักต้องการ 32k+
  ถ้าเจอ error เรื่องความยาว ย้ายไป `or/nemotron-ultra-550b` หรือ `or/nemotron-lightning` (1M)
- **บัญชี HF ไม่ใช่ทางเดียวแล้ว** — ตอนนี้มี 9 provider ถ้าเจ้าไหนโควต้าหมด
  สลับ model_name ได้เลยโดยไม่ต้องแก้ฝั่ง client
- **เครดิต HF หมดแล้ว (2026-08-23)** แต่ `hf/*` ยังเรียกได้ปกติเพราะตั้ง `fallbacks`
  ให้วิ่งไป provider อื่น — ทดสอบแล้วกู้ได้ 21/21 ฝั่ง client ไม่ต้องแก้อะไร
- **อย่าใช้ `cf/qwen3.8-27b` กับงานเขียนโค้ดยาว** — thinking model ที่ token หมดก่อน
  เขียนโค้ดจบ และ Cloudflare timeout เมื่อขอ max_tokens สูง (ได้ 0/3)
