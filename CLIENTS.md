# ต่อ AI agent / coding agent เข้ากับ gateway นี้

ทดสอบจริงเมื่อ 2026-08-14 — สิ่งที่ gateway นี้รองรับ:

| ความสามารถ | สถานะ | หมายเหตุ |
|---|---|---|
| OpenAI Chat Completions `/v1/chat/completions` | ✅ | endpoint หลัก |
| Streaming (SSE) | ✅ | |
| **Tool / function calling** | ✅ | ผ่านทั้ง 6 โมเดลที่ทดสอบ — หัวใจของ agent |
| Anthropic format `/v1/messages` | ✅ | ใช้กับ Claude Code ได้ |
| `/v1/models` | ✅ | client ส่วนใหญ่ดึงรายชื่อโมเดลอัตโนมัติ |
| Embeddings | ✅ | `emb/nemotron-embed` (2048 มิติ), `emb/nv-embedqa-e5` (1024) |
| Vision (รูปภาพ) | ยังไม่ทดสอบ | ต้องเพิ่มโมเดล VL เช่น `Qwen/Qwen2.5-VL-72B-Instruct` |

**ค่าที่ต้องใช้ทุก client:**

```
Base URL : https://llm-api.example.com/v1     ← เปลี่ยนเป็น API_DOMAIN ของคุณ
API Key  : sk-...                             ← ออกด้วย ./scripts/gen-key.sh
Model    : hf/qwen3-coder-next, hf/llama-3.3-70b, ... (ดู README)
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
./scripts/gen-key.sh --alias cline    --models hf/qwen3-coder-next,hf/deepseek-v3.2
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
Model ID : hf/qwen3-coder-next
```

ติ๊ก **Enable streaming** ไว้ และเปิด **Function Calling / Tools** (ทดสอบแล้วรองรับ)

### Continue.dev

`~/.continue/config.yaml`:

```yaml
models:
  - name: qwen3-coder
    provider: openai
    model: hf/qwen3-coder-next
    apiBase: https://llm-api.example.com/v1
    apiKey: sk-...
    roles: [chat, edit, apply]
  - name: llama-fast
    provider: openai
    model: hf/llama-3.1-8b
    apiBase: https://llm-api.example.com/v1
    apiKey: sk-...
    roles: [autocomplete]
```

### Aider

```bash
export OPENAI_API_BASE=https://llm-api.example.com/v1
export OPENAI_API_KEY=sk-...
aider --model openai/hf/qwen3-coder-next
```

หรือใส่ถาวรใน `~/.aider.conf.yml`:

```yaml
openai-api-base: https://llm-api.example.com/v1
openai-api-key: sk-...
model: openai/hf/qwen3-coder-next
```

### Claude Code

LiteLLM มี `/v1/messages` (รูปแบบ Anthropic) ให้ ชี้ Claude Code มาที่นี่ได้:

```bash
export ANTHROPIC_BASE_URL=https://llm-api.example.com
export ANTHROPIC_AUTH_TOKEN=sk-...
export ANTHROPIC_MODEL=hf/qwen3-coder-next
export ANTHROPIC_SMALL_FAST_MODEL=hf/llama-3.1-8b
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
แล้วใน node "OpenAI Chat Model" พิมพ์ชื่อโมเดลเอง เช่น `hf/llama-3.3-70b`

ถ้า n8n รันเป็น container บนเครื่องเดียวกัน ต่อ network `llm-net` แล้วใช้ `http://llm-litellm:4000/v1` จะเร็วกว่าและไม่ออกอินเทอร์เน็ต

### Dify / Flowise

Model Provider → **OpenAI-API-compatible**
API endpoint `https://llm-api.example.com/v1`, key `sk-...`, model name ตามที่ตั้งไว้

### Python — OpenAI SDK / LangChain / LlamaIndex / CrewAI

```python
from openai import OpenAI
client = OpenAI(base_url="https://llm-api.example.com/v1", api_key="sk-...")
r = client.chat.completions.create(
    model="hf/qwen3-coder-next",
    messages=[{"role": "user", "content": "เขียน fizzbuzz"}],
)
```

```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(
    base_url="https://llm-api.example.com/v1",
    api_key="sk-...",
    model="hf/llama-3.3-70b",
)
```

CrewAI / LiteLLM-native ใช้ชื่อ `openai/hf/llama-3.3-70b` พร้อม `OPENAI_API_BASE`

---

## เลือกโมเดลยังไง

| งาน | แนะนำ |
|---|---|
| coding agent (แก้โค้ดหลายไฟล์) | `hf/qwen3-coder-next`, `hf/deepseek-v3.2` |
| agent ที่เรียก tool เยอะ | `hf/llama-3.3-70b`, `hf/qwen3.5-397b` |
| งานเบา/จัดหมวด/สรุป (ประหยัด) | `hf/llama-3.1-8b`, `hf/qwen2.5-7b` |
| งานที่ต้องคิดเยอะ | `hf/deepseek-r1`, `hf/glm-4.7` — แต่ช้า ไม่เหมาะเป็น agent loop |
| ต้องการความเร็วสูงสุด | `gq/llama-3.1-8b` (181ms), `gq/llama-3.3-70b` (688ms) |
| context ยาวมาก | `or/nemotron-ultra-550b` (1M), `or/nemotron-lightning` (1M) |
| ภาษาไทยโดยเฉพาะ | `hf/sea-lion-32b`, `cf/sea-lion-27b` |
| RAG / embeddings | `emb/nemotron-embed`, `emb/nv-embedqa-e5` |

## ข้อควรระวัง

- **บัญชี HF เป็น free tier** เครดิต inference จำกัดต่อเดือน — coding agent กิน token มหาศาล
  (อ่านไฟล์ทั้งโปรเจกต์เข้า context ทุกรอบ) ให้ออก key แบบมี `--budget` เสมอ
- ดู spend ได้ที่ https://llm-api.example.com/ui → **Usage** แยกตาม key ได้
- ถ้าเจอ rate limit จาก provider ให้เพิ่ม fallback ใน `litellm/config.yaml`:
  ```yaml
  litellm_settings:
    fallbacks: [{"hf/qwen3-coder-next": ["hf/deepseek-v3.2", "hf/qwen2.5-7b"]}]
  ```
- context window ของโมเดลต่างกันมาก (8k–128k) coding agent มักต้องการ 32k+
  ถ้าเจอ error เรื่องความยาว ให้ย้ายไปโมเดลใหญ่ขึ้น
