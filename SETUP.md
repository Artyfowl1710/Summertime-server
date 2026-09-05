# Air-Gapped AI Workbench - Setup & Deployment Guide

This guide provides the complete, step-by-step instructions required to set up the Air-Gapped AI Workbench Server in any environment (On-Premise, Laptop, or Isolated Cloud VM).

---

## 1. Prerequisites

Ensure your host machine meets the following requirements:

- **OS**: Linux (Ubuntu 22.04+ recommended) or Windows (via WSL2 or Native)
- **Python**: 3.10 or higher
- **Hardware**: 
  - At least 16GB RAM
  - NVIDIA GPU with CUDA support (Highly recommended for vLLM & ComfyUI)
- **Software**:
  - `git`
  - Docker & Docker Compose (Optional, but **required** for the secure gVisor Code Sandbox)
  - `nvidia-smi` (Installed automatically with NVIDIA drivers)

---

## 2. Environment Configuration

The server is configured entirely via environment variables. Create a `.env` file in the root of the project directory. 

### `.env` Template

```env
# ── API & Security ─────────────────────────
ADMIN_TOKENS=super-secret-admin-token
USER_TOKENS=user-token-1,user-token-2
PUBLIC_API_BASE=http://127.0.0.1:8000

# ── Private Artifactory (Model Storage) ────
# Where the server downloads models from (must be accessible from the air-gapped network)
ARTIFACTORY_URL=http://artifactory.internal.company.com
ARTIFACTORY_REPO=ai-models-local
ARTIFACTORY_TOKEN=your-artifactory-access-token

# ── Lifecycle & GPU Limits ─────────────────
MODEL_DEFAULT_TTL_S=3600
MAX_CONCURRENT_VLLM_PROCESSES=2
LIFECYCLE_POLL_INTERVAL_S=10

# ── Code Sandbox ───────────────────────────
SANDBOX_GVISOR_RUNTIME=runsc
SANDBOX_MEMORY_MB=512
SANDBOX_CPU_COUNT=1

# ── Backend Specifics ──────────────────────
VLLM_HOST=127.0.0.1
VLLM_BASE_PORT=8100
VLLM_MAX_PORT=8199
ONNX_HOST=127.0.0.1
ONNX_BASE_PORT=8200
```

> **Note:** If `ARTIFACTORY_URL` is omitted, the server will assume models are already placed manually inside the local models directory.

---

## 3. Installation

You can run the server directly on bare-metal (using Python virtual environments) or via Docker.

### Option A: Bare-Metal Setup (Recommended for Development)

1. **Clone the repository:**
   ```bash
   git clone <your-internal-repo-url>
   cd server-workbench
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Linux/macOS
   source venv/bin/activate
   # On Windows
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -e .
   ```

4. **Initialize the Database:**
   ```bash
   # Generates the SQLite database schema in the current directory
   python -c "from server.db import Base, engine; Base.metadata.create_all(engine)"
   ```

5. **Start the Server:**
   ```bash
   uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 1
   ```

### Option B: Docker Compose (Recommended for Production)

1. **Clone the repository:**
   ```bash
   git clone <your-internal-repo-url>
   cd server-workbench
   ```

2. **Ensure your `.env` file is present in the root directory.**

3. **Start the containers:**
   ```bash
   docker-compose up -d --build
   ```
   *The server will be available at `http://localhost:8000`.*

---

## 4. Usage & Model Management

### Generating an API Request

Use the `ADMIN_TOKENS` or `USER_TOKENS` defined in your `.env` file for the `Authorization` header.

**Health Check:**
```bash
curl -H "Authorization: Bearer user-token-1" http://localhost:8000/v1/health
```

### Registering a Model

Before the server can serve a model, you must register it. The Lifecycle Manager will automatically download it from your Artifactory if it isn't cached locally.

```bash
curl -X POST http://localhost:8000/v1/models \
  -H "Authorization: Bearer super-secret-admin-token" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "llama-3-8b-instruct",
    "source": {
      "type": "artifactory",
      "path": "llm/llama-3-8b-instruct"
    },
    "backend": "vllm",
    "type": "text",
    "task_tags": ["chat", "coding"],
    "vram_mb": 16000,
    "pinned": false
  }'
```

### Generating Text (OpenAI Compatible)

The server acts identically to OpenAI's endpoints. Note that if the model is currently "cold" (unloaded), the very first request will take slightly longer as the server automatically spins up the vLLM/ONNX backend in the background.

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer user-token-1" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3-8b-instruct",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Write a python script to calculate fibonacci."}
    ]
  }'
```

## 5. Troubleshooting

- **QueuePool limit reached**: If you have high concurrency, you may need to increase the SQLite connection pool size in `server/db/models.py`.
- **vLLM OOM Error**: Ensure you correctly set the `vram_mb` estimate during model registration. If omitted, the server uses a heuristic based on file size, which may underestimate memory requirements for large context windows.
- **Sandbox Failing**: If executing code fails instantly, ensure Docker is running and the gVisor (`runsc`) runtime is properly installed on the host. If running on Windows without Docker, check the server logs for the bare-metal fallback warning.
