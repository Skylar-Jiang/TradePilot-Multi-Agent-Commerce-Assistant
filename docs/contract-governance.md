# Contract governance

## Owner and frozen surface

The **Contract Maintainer (the backend base owner)** owns the shared surface below. Teammates may
consume it directly, but changes require a separate Contract PR approved and merged by the Contract
Maintainer before dependent implementation PRs are rebased.

- Pydantic contracts: `app/schemas/`, `app/agents/contracts.py`, and
  `app/statistics/contracts.py`.
- Orchestration: `app/workflows/state.py` and `app/workflows/graph.py`.
- API: `app/api/v1/router.py`, `app/api/responses.py`, and the ten-route `/api/v1` surface.
- Persistence: `app/db/models/core.py`, repository Protocols, Alembic configuration, and migration
  history.
- Cross-team ports: `app/adapters/base.py`, `app/adapters/profiles.py`,
  `app/rag/contracts.py`, `app/rag/factory.py`, and `app/statistics/factory.py`.
- Shared enums/config and cross-team tests: `app/core/enums.py`, `app/core/config.py`,
  `tests/conftest.py`, `tests/builders.py`, workflow, migration, and API contract tests.

## Contract PR rule

Do not mix a public-contract change into a teammate's business implementation PR. Open a small
`contract/<topic>` branch and PR containing:

1. the compatibility classification (additive or breaking) and affected consumers;
2. updated Pydantic/OpenAPI/Protocol documentation and a failing contract test first;
3. an Alembic migration plus downgrade when persisted schema changes;
4. fixture/Stub compatibility so all three teammate branches can still test independently;
5. the required rebase order for dependent branches.

The Contract Maintainer merges that PR first. Teammate branches then rebase on the new baseline,
update only their owned code, run all four gates, and merge one at a time. A breaking API or state
change needs explicit team approval; field renames/removals are not performed silently.

## Database schema changes

`migrations/versions/` is the schema history; runtime code and scripts use `alembic upgrade head`.
Create a revision from repository root with:

```powershell
python -m alembic revision --autogenerate -m "describe schema change"
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic upgrade head
```

Inspect generated migrations before commit. A schema Contract PR must include migration tests,
compatibility notes, and updates to Repository/Pydantic contracts when applicable. Domain-only
fields stay in `attributes_json` or `metadata_json` and do not require shared-model edits.
