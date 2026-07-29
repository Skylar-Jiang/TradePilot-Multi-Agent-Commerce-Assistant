# TradePilot

TradePilot analyzes an unlisted pet product by matching it to real listed peer products, then grounding market and user
insights in peer metadata, SQL statistics, and peer-review RAG evidence. Real mode uses four LCEL Agents in one
LangGraph workflow and never falls back to Demo or Mock.

The repository contains the FastAPI backend at the root and the React + TypeScript + Vite dashboard in `frontend/`.
The deployed staging UI is [https://tradepilot-staging-hll-lbld.vercel.app/](https://tradepilot-staging-hll-lbld.vercel.app/);
it calls the FastAPI staging API on Railway. This is a **shared staging workspace**, not a public production service:
authorized members share products, analysis runs, conversations, reports, uploads, Chroma and peer caches. For the
exact Railway/Vercel setup, persistent-volume layout, access-code policy, rollback and demo-data reset steps, see
[`docs/deployment-guide.md`](docs/deployment-guide.md). The concise code-verified runtime view is
[`docs/current-state.md`](docs/current-state.md); dated handovers and validation reports are historical evidence.

## Runtime contract

- Python `>=3.12,<3.13`
- LangChain 1.3.x, LangChain Core 1.4.x, LangGraph 1.2.x
- FastAPI, Pydantic v2, SQLAlchemy/Alembic, SQLite, Chroma
- DeepSeek V4 Flash for ProductMarketAgent and UserInsightAgent by default
- Qwen 3.7 Plus for OperationsDecisionAgent, Qwen 3.6 Flash for EvidenceAuditAgent by default
- Qwen3-VL Plus for conditional image understanding and `text-embedding-v4` for bounded candidate/RAG embeddings

Demo mode remains available for deterministic compatibility tests. Real mode requires a configured text-model route,
prepared offline lookup caches, Chroma, embedding credentials for the selected embedding route, and the real source
JSONL files. The default mixed route uses DeepSeek for the two analysis Agents and Qwen for operations, audit,
embeddings and optional vision; a text-only DeepSeek route is also supported. CustomerServiceAgent uses the report
model (or `MODEL_CUSTOMER_SERVICE`) only after a report exists and is not part of the core four-Agent workflow.

## Data modes and index scope

- **Demo mode** uses deterministic fixtures for tests and local contract checks.
- **Real peer-group mode** is the production unlisted-product path. It reuses the prepared lightweight catalog and
  review offsets, embeds only bounded candidates and selected peer documents, and does not require the full index.
- **Full offline index mode** is a separate exact-product/evaluation workflow. It is retained for experiments and must
  not be rebuilt or modified by peer-group API requests.

## Install

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
```

Fill `DEEPSEEK_API_KEY` and `QWEN_API_KEY` only in the ignored `.env`. Never commit that file.

The application reads shared values from `.env`, then overlays `.env.<APP_ENV>`. For example, copy
`.env.development.example` to the ignored `.env.development` for local paths, or copy
`.env.production.example` to `.env.production` for production paths. Set `APP_ENV` in the process environment or
shared `.env`; environment names are validated before a file path is constructed.

For local Real mode, configure the required provider credentials only in ignored environment files. In Railway
staging, also set a non-empty `APP_API_KEY`; users enter this shared access code in the browser, and it must never be
placed in a `VITE_*` variable or committed to Git.

## Prepare real peer data offline

```powershell
python scripts\prepare_peer_data.py
```

This command scans product metadata and reviews only when the source signature is new or stale. It builds lightweight
catalog and review-lookup files under the configured `PEER_CACHE_DIR` (locally, `data/demo/cache`; in Railway staging,
`/data/peer-cache`). The catalog contains normalized metadata plus FTS; the review lookup stores source offsets/line
numbers, not copied review text. It does not embed the full dataset and does not read or modify the full Chroma index.

The online `/analysis-runs` path only opens valid prepared caches. Missing or stale caches return
`data_preparation_required`; online analysis never scans raw JSONL or rebuilds a cache.

To audit source-derived terminal-product coverage without creating a global online classifier, run:

```powershell
python scripts\audit_catalog_product_types.py
```

The current prepared catalog contains 161,540 products and yields 493 source-resolved type buckets plus one explicit
`__unresolved__` bucket for 9,387 records whose source category is missing. The ten entries in
`config/real_product_smoke_manifest.yaml` are representative smoke inputs, not the complete type inventory. Type
flags improve offline coverage inspection only: they do not manufacture reviews, bypass semantic peer thresholds or
guarantee that every uploaded product has enough qualified peers.
The ignored type-flag cache records both the catalog signature and explicit `source-leaf-v1` classifier version;
either change invalidates only this audit cache, not catalog FTS, review offsets, or vector indexes.

Peer matching is query-time direct-product matching, not a global product classifier. FTS recalls on product text;
`categories` and price are weak scoring signals, and missing/different categories do not block a real same-terminal
product. Acceptance thresholds and matcher version live in `config/peer_matching.yaml`. Products below the configured
rule/semantic thresholds are never used to fill a quota; fewer than 10 accepted peers produces the traceable
`insufficient_peer_products` data gap.

`peer_group_id` identifies this candidate-specific analysis group. Its stable input excludes the upload/runtime
`product_id` and includes the normalized candidate signature, catalog source signature, full matching config and
matcher version, embedding model, and sorted final `selected_parent_asins`.

## Run

For a classroom demonstration on Windows, double-click `start_demo.py` in the repository root (or run the command below).
It automatically switches to `.venv`, starts the backend, creates the prepared Real-mode pet-fountain candidate,
waits for its peer-group analysis and four Agents, then opens the final Markdown marketing report.

```powershell
.\.venv\Scripts\python.exe .\start_demo.py
```

The terminal prints the report, Swagger and run URLs; use `Ctrl+C` to stop the server. `--server-only` starts just
Swagger, while `--no-browser` and `--port 8001` are available when needed.

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health: `GET http://127.0.0.1:8000/api/v1/health`. Swagger: `/docs`.

## Frontend

The React + TypeScript operations dashboard lives in `frontend`. Start the API first, then run:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Vite serves the dashboard at `http://127.0.0.1:5173` and proxies `/api/v1` to the local API. The deployed Vercel
build uses `VITE_API_BASE_URL=https://tradepilot-staging.up.railway.app/api/v1`; the shared access code is entered at
runtime and remains only in
the current browser session. The UI covers product
creation, optional file upload, four-Agent progress, timeline, audit results, and structured/Markdown reports. See
`frontend/README.md` and `docs/frontend-implementation.md` for the design and integration details.

In staging, `/api/v1/health` is the only anonymous application endpoint. All other `/api/v1/*` calls require
`Authorization: Bearer <access-code>`; a 401 clears the browser session and returns the user to the access page.
CORS limits browser origins but does not replace this authentication.

Create a `data_mode=real` product with its name, description, features, parameters, scenarios, target species/users,
target price, and optional uploaded image. `POST /api/v1/analysis-runs` returns `202` immediately; the current UI
polls `/status` and `/timeline`. The backend also exposes persisted `/events` SSE with `Last-Event-ID` replay for
clients that need streaming progress. Timeline, Agent outputs, peers,
evidence, audit, metadata, Markdown, JSON, immutable report versions, evidence explanations, local section edits and
rollback are available from the endpoints in `docs/api-contract.md`. Frontend integration and report-support rules are
documented in `docs/frontend-integration.md` and `docs/report-support.md`.

The customer-facing report is marketing-strategy-led: positioning, target segments, value propositions, pricing,
channels, messages and launch actions follow the peer product/review analysis. Markdown shows numbered evidence links
with readable product titles and Chinese support descriptions; UUIDs, ASINs and original source text remain available
through the evidence-detail/JSON mapping rather than interrupting the narrative.

Every HTTP request writes one allow-listed application log record with request ID, method, path, status and duration.
Query strings, bodies, headers and credentials are never logged. Real Agent output uses an LCEL
`prompt | model | normalization | PydanticOutputParser` chain. Malformed JSON or Schema output is retried only up to
`MODEL_PARSE_MAX_RETRIES`; provider retries remain separately bounded by `MODEL_MAX_RETRIES`.

The peer-group Chroma path applies MMR over the bounded vector candidates (`RAG_MMR_ENABLED` and
`RAG_MMR_LAMBDA`). The separate exact-product evaluation pipeline can additionally use the configured external
reranker. MMR and rerank strategy/model metadata remain attached to retrieval results for traceability. Transient
post-upsert HNSW segment-reader errors receive only the bounded `RAG_QUERY_MAX_RETRIES` read retry; no cache/index
rebuild or Demo/Mock fallback occurs.

## Verify

```powershell
python -m pip check
python -m pytest -q
python -m compileall -q app tests scripts
python -m ruff check .
python scripts\smoke_test.py

Set-Location frontend
npm ci
npm run build
```

Real provider tests are opt-in so normal CI remains deterministic. The final HTTP E2E must be run with local secrets
and `trust_env=False` when the workstation has an incompatible system proxy. See `docs/testing-guide.md`,
`docs/current-state.md`, and the historical `docs/handover/handover.md`. Do not run a live Real-mode workflow unless its provider keys, Git LFS sources, prepared
peer cache and RAG prerequisites have been verified; it can consume model-provider quota.
