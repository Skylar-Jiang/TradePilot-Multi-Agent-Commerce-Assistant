# File structure

```text
app/
  adapters/        DomainAdapter contract, profile loader, Demo and future domain adapters
  agents/          Four independent LCEL scaffold Agents and contracts
  api/v1/          The single formal API router
  core/            Settings, enums, exceptions
  db/              SQLAlchemy models, session, repository protocols, migration runner
  rag/             Two-domain ports, injectable factory, memory store, minimal Chroma adapter
  schemas/         Pydantic v2 request, state, evidence, output, report models
  services/        Product, analysis, knowledge, conversation, report services
  skills/          Disabled OperationContentSkill placeholder
  statistics/      StatisticsResult/Provider contract, Stub, future provider directory
  workflows/       TradePilotState and the StateGraph
config/             Domain profiles
migrations/         Alembic environment and immutable schema history
data/demo/          Explicitly marked deterministic fixtures
docs/               Architecture, contracts, development, handover, cleanup
frontend/.gitkeep   No frontend in this phase
scripts/            Init, seed, rebuild and isolated smoke commands
tests/              Shared builders plus owner-split Unit, integration and API contract tests
new-docs/           User-provided planning source, preserved unchanged
```

Shared-file ownership and Contract PR rules are defined in `docs/contract-governance.md`.
