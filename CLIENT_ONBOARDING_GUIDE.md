# Client Onboarding & Integration Guide

Welcome to the **Summertime AI Model Gateway**. This guide is designed for client-side engineers, data scientists, and analysts connecting client applications (INDRA Desktop, Hermes Agent, IDE plugins, custom automation scripts, or web UIs) to a remote GPU server.

---

## 📋 What You Need Before Starting

Obtain your client connection packet from your Server Administrator. You need two pieces of information:
1. **Server Base URL**: e.g., `http://192.168.1.100:8000` or `https://ai.internal.enterprise.com`
2. **Dynamic API Key**: A secure key beginning with `wb_live_...`

---

## 🚀 1. INDRA Desktop & Hermes Agent (Single Command)

If you are using the INDRA AI workstation or Hermes Agent CLI:

```bash
# Run the automated server configuration command:
indra set-server --url http://192.168.1.100:8000 --key wb_live_YOUR_KEY_HERE
```

This automated utility:
1. Pings the server's `/v1/health` and `/v1/models` endpoints to verify connectivity.
2. Updates your local `.env` with `WORKBENCH_API_BASE` and `WORKBENCH_API_KEY`.
3. Patches `config.yaml` to route inference through the remote gateway.
4. Executes a lightweight test inference turn to ensure end-to-end readiness.

Launch your local dashboard as usual:
```bash
indra dashboard
```

---

## 🐍 2. Official OpenAI Python SDK

Summertime is 100% wire-compatible with the standard OpenAI API specification. You can use the official `openai` Python library without modifying client logic:

```python
from openai import OpenAI

# Point client to the remote Summertime Server
client = OpenAI(
    base_url="http://192.168.1.100:8000/v1",
    api_key="wb_live_YOUR_KEY_HERE",
)

# 1. Non-Streaming Turn
response = client.chat.completions.create(
    model="indra-auto",
    messages=[
        {"role": "system", "content": "You are a concise enterprise technical advisor."},
        {"role": "user", "content": "Provide 3 best practices for sovereign network isolation."}
    ],
    temperature=0.2,
)
print("Assistant:", response.choices[0].message.content)

# 2. Real-Time Token Streaming
stream = client.chat.completions.create(
    model="indra-engineer",
    messages=[{"role": "user", "content": "Write a Python script to validate CIDR blocks."}],
    stream=True,
)

print("\nStreaming Output: ")
for chunk in stream:
    delta = chunk.choices[0].delta.content or ""
    print(delta, end="", flush=True)
print()
```

---

## 🟨 3. Official OpenAI Node.js / TypeScript SDK

```typescript
import OpenAI from "openai";

const openai = new OpenAI({
  baseURL: "http://192.168.1.100:8000/v1",
  apiKey: "wb_live_YOUR_KEY_HERE",
});

async function main() {
  const completion = await openai.chat.completions.create({
    model: "indra-auto",
    messages: [{ role: "user", content: "Summarize the benefits of local model inference." }],
  });

  console.log(completion.choices[0].message.content);
}

main();
```

---

## 💻 4. Developer IDEs (Cursor & VS Code Continue)

### VS Code (Continue Extension)
Add the following to your `~/.continue/config.json`:
```json
{
  "models": [
    {
      "title": "Summertime Sovereign AI (Remote)",
      "provider": "openai",
      "model": "indra-engineer",
      "apiBase": "http://192.168.1.100:8000/v1",
      "apiKey": "wb_live_YOUR_KEY_HERE"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Summertime Autocomplete",
    "provider": "openai",
    "model": "indra-engineer",
    "apiBase": "http://192.168.1.100:8000/v1",
    "apiKey": "wb_live_YOUR_KEY_HERE"
  }
}
```

### Cursor IDE
1. Open Cursor Settings -> **Models**.
2. Under **OpenAI API Key**, enter: `wb_live_YOUR_KEY_HERE`.
3. Check **Override OpenAI Base URL** and enter: `http://192.168.1.100:8000/v1`.
4. Enter model names: `indra-auto`, `indra-engineer`.

---

## 🌐 5. Web UIs (OpenWebUI / LibreChat)

### OpenWebUI (Docker or Bare Metal)
Set the environment variables before starting OpenWebUI:
```bash
OPENAI_API_BASE_URL="http://192.168.1.100:8000/v1"
OPENAI_API_KEY="wb_live_YOUR_KEY_HERE"
```
Or navigate to **Admin Panel -> Settings -> Connections -> OpenAI API**:
- URL: `http://192.168.1.100:8000/v1`
- Key: `wb_live_YOUR_KEY_HERE`
- Click **Verify** to auto-populate all available models!

---

## 🦜 6. LangChain & LlamaIndex

### LangChain (Python)
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="indra-analyst",
    openai_api_base="http://192.168.1.100:8000/v1",
    openai_api_key="wb_live_YOUR_KEY_HERE",
    temperature=0.1,
)

response = llm.invoke("Calculate estimated cost variance for maintenance log #420.")
print(response.content)
```

### LlamaIndex (Python)
```python
from llama_index.llms.openai import OpenAI

llm = OpenAI(
    model="indra-auto",
    api_base="http://192.168.1.100:8000/v1",
    api_key="wb_live_YOUR_KEY_HERE",
)

response = llm.complete("Explain the vector chunking strategy.")
print(response.text)
```

---

## 🎯 Supported Model Roles & Aliases

You do not need to manage underlying file paths. Request models by their specialized role:

| Model Alias | Primary Domain | Best Used For |
| :--- | :--- | :--- |
| `indra-auto` | **Smart Adaptive Router** | General intent; automatically analyzes the query and dispatches to the optimal specialized model. |
| `indra-engineer` | **Code & Systems** | Software development, shell scripting, debugging, architecture design. |
| `indra-analyst` | **Structured Reasoning** | Excel spreadsheets, tabular data, financial formulas, quantitative queries. |
| `indra-writer` | **Prose & Synthesis** | Report writing, executive briefings, documentation, summarization. |
| `indra-vision` | **Vision & Multimodal** | OCR, diagram inspection, image analysis, screenshot transcription. |
| `indra-general` | **Fast Turnaround** | Low-latency chat, quick lookups, definitions. |

---

## 🔍 Quick Command Line Sanity Test

Run this single-line curl command from your terminal to verify your connection:

```bash
curl -i -X POST "http://192.168.1.100:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer wb_live_YOUR_KEY_HERE" \
  -d '{
    "model": "indra-auto",
    "messages": [{"role": "user", "content": "Hello sovereign server!"}],
    "max_tokens": 30
  }'
```

A successful response returns `HTTP/1.1 200 OK` with JSON completion payload and the routing headers.
