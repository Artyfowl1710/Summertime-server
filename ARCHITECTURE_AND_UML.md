# Architecture & UML Specifications

This document defines the formal software architecture, data models, sequence flows, and state machines for the **Summertime AI Workbench Server**.

---

## 1. High-Level Component Diagram

```mermaid
graph TB
    subgraph ClientLayer ["Client Layer"]
        CLI["Hermes / INDRA CLI"]
        WebUI["INDRA Web Dashboard"]
        Ext["External SDK / IDEs"]
    end

    subgraph Gateway ["FastAPI Gateway Subsystem (Port 8000)"]
        HTTP["HTTP / SSE Ingress Handler"]
        AuthMid["Authentication Dependency (require_auth / require_admin)"]
        Router["Model Router (resolve_requested_model)"]
        Lifecyc["Lifecycle Manager (ModelLifecycleManager)"]
        RAGRouter["RAG Endpoints (/v1/rag/*)"]
        AdminRouter["Admin Endpoints (/v1/admin/*)"]
    end

    subgraph InferenceSubsystem ["Inference Subsystem"]
        SwapDriver["LlamaSwap Driver (server.backends.llamaswap)"]
        SwapDaemon["llama-swap Process (Port 8100)"]
        Llama1["llama-server :Port_A (Qwen 3.5 4B)"]
        Llama2["llama-server :Port_B (Gemma 2 2B)"]
    end

    subgraph StorageSubsystem ["Data & Storage Layer"]
        SQLite[("SQLite Database: workbench.db")]
        Qdrant[("Qdrant Vector Store: Port 6333")]
        ModelFiles[("Model Storage: models/*.gguf")]
    end

    CLI --> HTTP
    WebUI --> HTTP
    Ext --> HTTP

    HTTP --> AuthMid
    AuthMid --> SQLite
    HTTP --> Router
    Router --> Lifecyc
    Lifecyc --> SQLite
    Lifecyc --> SwapDriver
    SwapDriver --> SwapDaemon
    SwapDaemon --> Llama1
    SwapDaemon --> Llama2
    Llama1 --> ModelFiles
    Llama2 --> ModelFiles

    HTTP --> RAGRouter
    RAGRouter --> Qdrant
    HTTP --> AdminRouter
    AdminRouter --> SQLite
```

---

## 2. End-to-End Inference Sequence Diagram

The following sequence illustrates a client requesting an inferencing stream (`POST /v1/chat/completions` with `stream=True` and `model="indra-auto"`).

```mermaid
sequenceDiagram
    autonumber
    actor Client as Client Workstation
    participant GW as FastAPI Gateway
    participant Auth as Auth Subsystem
    participant Router as Model Router
    participant Life as Lifecycle Arbiter
    participant Swap as llama-swap (:8100)
    participant LS as llama-server Child Process

    Client->>GW: POST /v1/chat/completions (Bearer wb_live_...)
    activate GW
    GW->>Auth: Verify Bearer Token
    Auth->>Auth: Argon2 verify against active DB hashes
    Auth-->>GW: Key Validated (Owner: analyst-1, Scope: user)
    
    GW->>Router: resolve_requested_model("indra-auto", messages)
    Router->>Router: Inspect prompt tokens & task keywords
    Router-->>GW: Decision: routed_model="qwen3.5-4b", role="engineer"

    GW->>Life: track_request("qwen3.5-4b")
    activate Life
    Life->>Life: Reconcile loaded models & check VRAM budget
    alt Model is Cold
        Life->>Swap: POST /load (qwen3.5-4b)
        Swap->>LS: Spawn llama-server --model Qwen_Qwen3.5-4B.gguf
        LS-->>Swap: Health Check OK
        Swap-->>Life: 200 OK (Model Resident)
    end
    Life->>Life: Increment active_requests counter (status="busy")
    Life-->>GW: Acquired Lease Context

    GW->>Swap: POST /v1/chat/completions (stream=True, model="qwen3.5-4b")
    Swap->>LS: Forward to assigned child port
    activate LS
    
    loop Real-Time Generation
        LS-->>Swap: SSE Token Chunks
        Swap-->>GW: SSE Token Chunks
        GW-->>Client: data: {"choices":[{"delta":{"content":"..."}}]}
    end
    LS-->>Swap: data: [DONE]
    deactivate LS
    Swap-->>GW: data: [DONE]
    GW-->>Client: data: [DONE]

    GW->>Life: Release Lease Context
    Life->>Life: Decrement active_requests counter (status="idle")
    deactivate Life
    deactivate GW
```

---

## 3. Dynamic API Key Issuance Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Server Administrator
    participant CLI as Workbench Admin CLI
    participant GW as Gateway (/v1/admin/keys)
    participant DB as SQLite (api_keys table)

    Admin->>CLI: workbench admin export-client --owner "laptop-alice" --scope "user"
    CLI->>GW: POST /v1/admin/keys (Bearer master_admin_key)
    activate GW
    GW->>GW: generate_key() -> "wb_live_random32chars"
    GW->>GW: hash_key(plaintext) -> Argon2id Hash
    GW->>DB: INSERT INTO api_keys (key_id, key_hash, owner, scope, created_at, revoked)
    DB-->>GW: Commit OK
    GW-->>CLI: 200 OK {"api_key": "wb_live_..."}
    deactivate GW
    CLI-->>Admin: Format & Display Client Onboarding Packet
```

---

## 4. Model Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Cold: Model Registered

    state Cold {
        [*] --> Unloaded
        Unloaded: Zero VRAM consumption
        Unloaded: Weight files on disk
    }

    Cold --> Loading: First Inference Request Received
    
    state Loading {
        Spawning: llama-swap executes llama-server
        Allocating: Offloading layers to GPU VRAM
        HealthCheck: Polling loopback port until 200 OK
    }

    Loading --> Idle: Health Check Passed
    Loading --> Cold: Load Failure (OOM or missing weight)

    state Idle {
        Resident: Model weights resident in GPU VRAM
        Waiting: active_requests == 0
        Timer: TTL Countdown Active (e.g. 300s)
    }

    Idle --> Busy: Inbound Request Dispatched
    
    state Busy {
        Processing: active_requests > 0
        Generating: KV cache active
        Streaming: Emitting SSE tokens
    }

    Busy --> Idle: Request Completed (active_requests == 0)

    Idle --> Evicted: TTL Expired OR VRAM Reclaim Demanded
    
    state Evicted {
        Terminating: Process killed cleanly
        Reclaiming: VRAM freed for other models
    }

    Evicted --> Cold: State Reset to Unloaded
```

---

## 5. Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    API_KEYS {
        string key_id PK "16-hex unique ID"
        string key_hash "Argon2id cryptographic hash"
        string owner "Assigned client/machine/user"
        string scope "'user' or 'admin'"
        datetime created_at "Creation timestamp UTC"
        datetime last_used_at "Last authenticated turn UTC"
        boolean revoked "Revocation flag"
    }

    MODELS {
        string id PK "Canonical ID (e.g. qwen3.5-4b)"
        string name "Human-readable label"
        string backend "llamaswap / vllm / onnx"
        string status "cold / loading / idle / busy"
        int vram_mb "VRAM allocation footprint"
        int active_requests "Concurrent stream counter"
        boolean pinned "True prevents auto-eviction"
    }

    GENERATION_JOBS {
        string id PK "Job UUID"
        string model_id FK "References MODELS.id"
        string status "pending / running / completed / failed"
        datetime created_at "Job submission timestamp"
        datetime completed_at "Job completion timestamp"
        string error "Error message if failed"
    }

    MODELS ||--o{ GENERATION_JOBS : executes
```
