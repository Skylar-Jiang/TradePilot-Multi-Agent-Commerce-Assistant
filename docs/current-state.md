# Current implementation state

Last verified against `main`: 2026-07-29.

This is the current-state companion to the source code. Dated plans, handovers, validation reports and work-split
notes remain in the repository as historical records; they do not override this document, `README.md`, or the API
implementation.

## Runtime and deployment

- Frontend: React 19, TypeScript 6 and Vite 8 in `frontend/`; deployed on Vercel at
  [https://tradepilot-staging-hll-lbld.vercel.app/](https://tradepilot-staging-hll-lbld.vercel.app/).
- Backend: FastAPI at the repository root; deployed on Railway at
  `https://tradepilot-staging.up.railway.app/api/v1`.
- The environment is staging and uses one shared access code. `GET /api/v1/health` is anonymous; all other API
  routes require `Authorization: Bearer <access-code>`. It is not a user-isolated or public production deployment.
- Railway persists SQLite, Chroma, uploads, reports, peer caches and the tariff database on a single `/data` volume.
  Use one replica because the deployment uses SQLite and an in-process admission lock.

## Analysis and interaction boundaries

The core LangGraph analysis chain has exactly four Agents:

1. `ProductMarketAgent` and `UserInsightAgent` run in parallel.
2. `OperationsDecisionAgent` consumes their validated outputs.
3. `EvidenceAuditAgent` applies deterministic guards and can request at most one operations retry.

`CustomerServiceAgent` is not a fifth analysis Agent. It is a report-follow-up service reached through
`/reports/{report_id}/customer-service/*` after report generation; it uses stored conversation records and can explain,
clarify, reject an unsupported request, make a guarded local edit, or create a targeted next report version.
Its explanatory replies are model-backed: unavailable or failed model calls surface as an error rather than silently
falling back to a generated answer.

There is no Vue or uni-app client, LangGraph checkpointer, Tool Calling orchestration, or legacy Conversation Manager
in the current implementation. Conversation persistence is provided by `ConversationService` and the customer-service
service.

## Progress, reports and tariff data

- `POST /analysis-runs` is asynchronous. The React client currently polls `/status` and `/timeline`; the backend also
  offers durable `text/event-stream` progress at `/events`, including numeric IDs, heartbeats, terminal close and
  `Last-Event-ID` replay.
- The backend exports every report as persisted Markdown and JSON. The UI supports Markdown download and browser
  printing (including the browser's “save as PDF” flow); there is no server-side PDF-export endpoint.
- A US-targeted UI request asks for `us-tariff-provider`. The provider only uses the local normalized HTS serving
  database and explicit mappings in `config/trade/hs_mapping.yaml`; it never infers an HS classification. Missing,
  ambiguous or stale tariff data becomes a visible data gap. A matched candidate classification still requires customs
  broker review before import decisions.

## Model routing

The defaults in `.env.example` are `deepseek-v4-flash` for analysis, `qwen3.6-flash` for audit,
`qwen3.7-plus` for operations and customer service, `qwen3-vl-plus` for optional vision, and
`text-embedding-v4` for embeddings. `MODEL_ANALYSIS` uses DeepSeek when `DEEPSEEK_API_KEY` is set. Operations and
audit prefer Qwen when its credential is configured and otherwise can use DeepSeek. Vision always needs Qwen but is
skipped when the candidate has no valid image. See `docs/model-provider-configuration.md` for configuration details.

## Historical material retained deliberately

`docs/handover/`, `docs/plans/`, `docs/validation/`, `docs/development-log-2026-07-15.md`,
`docs/team-work-split.md`, `docs/team-two-rag-and-agents.md`, `docs/refactor-mapping.md`, and
`docs/cleanup-report.md` are retained because they record delivery ownership, validation evidence or migration
decisions. Their dated statements and old local paths are historical, not current operating instructions.

The untracked materials in `new-docs/` are also retained as historical design and assessment inputs. In particular,
the project-design `.docx` describes an earlier Vue/uni-app, Checkpointer, Tool Calling and Conversation Manager
proposal rather than the current implementation; the assessment PDF is a user-provided delivery reference.
