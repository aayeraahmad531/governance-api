# governance-api

Unified governance FastAPI service wrapping enterprise AI auditing & compliance tools:
- **`POST /api/bias`**: Audits job descriptions for gender, age, and cultural bias.
- **`POST /api/compliance`**: Audits AI systems against EU AI Act requirements.
- **`POST /api/hallucination`**: Measures LLM hallucination rates on indexed topics.

---

## System Architecture

```mermaid
graph TD
    Client["Browser (Vercel Frontend)"] -->|HTTPS POST| API["Cloud Run Service (FastAPI)"]
    subgraph Container["Cloud Run Container (python:3.13-slim)"]
        API --> Embedder["ONNX Query Embedder (all-MiniLM-L6-v2)"]
        Embedder -->|Sub-ms Dot Product| Indexes[".npz Vector Indexes (eu_ai_act, bias_lexicon, facts)"]
        API --> Guard["Semaphore(2) & SHA256 LRU Cache"]
    end
    Guard -->|15 RPM Free Tier| LLM["Gemini 3.5 Flash-Lite API"]
```

---

## Technical Features & Performance

### 1. ONNX Retrieval Tokenization Optimization
During retrieval benchmarking, vector dot-product calculation was confirmed sub-millisecond ($<0.05\text{ms}$), but end-to-end `search()` latency bottlenecked at **218.0ms**.
- **Root Cause**: The tokenizer enforced fixed 512-token padding (`_tokenizer.enable_padding(length=512)`), forcing ONNX Runtime to evaluate full $512 \times 512$ matrix multiplications across 6 transformer layers for 5-word queries.
- **Fix**: Replaced fixed 512 padding with dynamic query length tokenization (`_tokenizer.no_padding()`).
- **Result**: ONNX query embedding latency dropped from **218.0ms to 4.7ms** (**46.1x speedup**), reducing total warm retrieval search time to **~5.3ms**.

### 2. Single-Category Score Ceiling (0.40 Capping)
The bias detection engine enforces a deliberate architectural ceiling: **single-category bias is capped at a maximum risk contribution of 0.40 / 1.00**, regardless of the volume of biased terms detected within that single category.
- **Design Rationale**: Single-dimension jargon (e.g., `ninja`, `rockstar`, `crush`, `killer`) represents isolated style jargon within Gender. Capping single-category contribution at 0.40 guarantees that multi-category systemic exclusion (Gender + Age + Cultural) is prioritized and reaches **1.00**.

---

## Cost Math & Rate Limiting

| Component | Limit / Multiplier | Rationale |
| :--- | :--- | :--- |
| **`POST /api/bias`** | 1 LLM call | Single structured extraction call |
| **`POST /api/compliance`** | 1 LLM call | Single structured compliance evaluation |
| **`POST /api/hallucination`** | $2N + 1$ LLM calls | 7 calls for default $N=3$ (1 question + 3 extractions + 3 verifications) |
| **Upstream RPM Limit** | 15 RPM | Enforced by Gemini 3.5 Flash-Lite free tier |
| **Endpoint Rate Limit** | 5 req / hour / IP | SlowAPI IP rate limiter |
| **Concurrency Ceiling** | `Semaphore(2)` | Protects against free-tier rate limit exhaustion |
| **Cloud Run Ceiling** | `--max-instances=3` | Strict infrastructure cost ceiling |

---

## Latency Benchmarks (Warm Round-Trip)

| Endpoint | Warm Latency | Target | Status & Notes |
| :--- | :---: | :---: | :--- |
| **`POST /api/bias`** | **4.86s** | < 5.0s | **PASSED** (k=10 retrieval depth) |
| **`POST /api/compliance`** | **6.39s** | < 5.0s | **Exceeds 5s Target** (Required for complex multi-article regulatory reasoning against EU AI Act) |
| **`POST /api/hallucination`** | **22.87s** | < 25.0s | **PASSED** (7 calls routed through `Semaphore(2)`) |

---

## Engineering Honesty & Limitations

1. **Facts Corpus Provenance**: The facts corpus (100 chunks across 5 topics) was built by scraping Wikipedia REST API summary extracts. Wikipedia is a reference source and not an authoritative ground truth. The retrieval engine is completely source-agnostic; replacing Wikipedia with a curated enterprise knowledge base is a zero-code `.npz` config change.
2. **Provider Fallback**: Provider failover logic (Gemini $\rightarrow$ OpenAI / Groq) is fully implemented in `app/llm.py` and unit-mocked, but **has never been verified against a live upstream API outage**.

---

## Repository Structure

```
governance-api/
├── app/
│   ├── main.py            # FastAPI application & privacy middleware
│   ├── config.py          # Environment settings
│   ├── llm.py             # LLM provider wrapper & Semaphore(2)
│   ├── retrieval.py       # Fast ONNX vector retrieval engine
│   ├── guards.py          # SlowAPI rate limiter & LRU cache
│   ├── schemas.py         # Pydantic schemas
│   └── routers/           # Endpoint handlers (bias, compliance, hallucination)
├── data/
│   ├── model.onnx         # ONNX transformer model
│   ├── model.onnx.data    # ONNX model weight tensors (90.8 MB)
│   ├── bias_lexicon.npz   # Bias vector index
│   ├── eu_ai_act.npz      # EU AI Act vector index
│   ├── facts.npz          # Wikipedia facts index
│   └── tokenizer/         # Tokenizer JSON files
├── scripts/
│   └── build_index.py     # Corpus index builder script
├── web/
│   ├── index.html         # Frontend landing page
│   ├── vercel.json        # Vercel security headers & CSP
│   └── assets/            # Frontend JS & CSS
├── Dockerfile             # Multi-stage production container build
├── .dockerignore          # Docker build exclusion list
├── deploy.sh              # Cloud Run deployment script
└── requirements.txt       # Production dependencies (No PyTorch)
```

---

## Local Development & Index Building

```bash
# 1. Install runtime dependencies
pip install -r requirements.txt

# 2. Run local development environment (API on 8080 + UI on 3000 concurrently)
python scripts/dev.py

# 3. Or run backend server standalone
python -m uvicorn app.main:app --port 8080 --reload

# 4. Rebuild vector indexes
python scripts/build_index.py --all

# 5. Run test suite
python -m pytest -o pythonpath=. -v
```
