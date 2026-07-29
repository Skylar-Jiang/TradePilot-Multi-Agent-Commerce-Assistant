# Model provider configuration

Last verified against `main`: 2026-07-29. Configure ignored `.env` and optional `.env.<APP_ENV>` files from the
repository root; use `.env.example` as the authoritative variable template. Never put credentials in `VITE_*` values.

## Default mixed-provider route

The staging-oriented default is:

```env
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
QWEN_API_KEY=your_qwen_key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

MODEL_ANALYSIS=deepseek-v4-flash
MODEL_FAST=qwen3.6-flash
MODEL_REPORT=qwen3.7-plus
MODEL_CUSTOMER_SERVICE=qwen3.7-plus
MODEL_VISION=qwen3-vl-plus
EMBEDDING_MODEL=text-embedding-v4
RAG_USE_CHROMA=true
```

`ProductMarketAgent` and `UserInsightAgent` use `MODEL_ANALYSIS` through DeepSeek. `OperationsDecisionAgent` uses
`MODEL_REPORT` and `EvidenceAuditAgent` uses `MODEL_FAST`; each prefers Qwen when its credential is configured and
can otherwise use DeepSeek. CustomerServiceAgent is separate from the core four-Agent graph and uses
`MODEL_CUSTOMER_SERVICE` or, when omitted, `MODEL_REPORT`.

`text-embedding-*` routes through the Qwen-compatible endpoint. `qwen3-vl-plus` is only constructed for a valid
candidate image; without an image, vision is skipped. A Qwen credential is therefore required for the default
embedding route and for image analysis, but not for a text-only DeepSeek run with a separately configured embedding
route.

## Supported alternatives

### Text-only DeepSeek

Set `MODEL_ANALYSIS`, `MODEL_FAST`, and `MODEL_REPORT` to compatible DeepSeek models and leave `QWEN_API_KEY` empty.
This is valid for text generation, including operations and audit fallback. A real run still needs
`RAG_USE_CHROMA=true`, a non-empty embedding model with its matching credentials, real source files and prepared peer
caches. Empty `EMBEDDING_MODEL` is only suitable for tests/offline helpers and fails real-readiness checks.

### OpenAI-compatible fallback

With `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `MODEL_ANALYSIS`, the analysis model can use an OpenAI-compatible
endpoint. Fully custom routes should be validated with the real-readiness and smoke commands because the default
mixed DeepSeek/Qwen route has the broadest coverage.

## Checks and common failures

Use the repository virtual environment after updating configuration:

```powershell
.\.venv\Scripts\python.exe -c "from app.core.config import get_settings; s=get_settings(); print(s.real_model_configured); print(s.model_analysis, s.model_fast, s.model_report, s.model_customer_service, s.embedding_model)"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`real_model_configured=True` only confirms that text-Agent entry points can be constructed. It does not prove that
the RAG source files, prepared caches, embedding route, optional tariff data or external credentials are ready.

- `llm_not_configured`: configure a valid analysis path and the models it needs.
- DashScope embedding `401`: verify that `QWEN_API_KEY` is real rather than a placeholder, or choose a fully
  configured non-Qwen embedding route.
- `Real image understanding requires QWEN_API_KEY`: submit no candidate image for a text-only run, or configure
  Qwen for image analysis.

For the full staging configuration, cache preparation and health/API checks, see `docs/deployment-guide.md`.
