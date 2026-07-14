# Team work split

## Teammate one: domain data and statistics

Own real domain selection, `DomainAdapter` implementations, import/cleaning scripts, SQL statistics,
and source provenance. Work in `app/adapters/domains/`, `app/statistics/providers/`,
`scripts/domain_imports/`, and teammate-one test files. Consume `DomainAdapter`,
`StatisticsProvider`, Repository, and model contracts without editing them. If a shared database
change is unavoidable, request a separate Contract PR; JSON domain fields do not require one.

## Teammate two: analysis Agents and RAG

Own ProductMarketAgent, UserInsightAgent, the `product_knowledge` and `review_insight` corpora,
retrieval quality, evidence-grounded structured outputs, and later model chains. Start at
`app/agents/product_market.py`, `app/agents/user_insight.py`, `app/rag/chroma.py`, new teammate-two
RAG implementation files, and `tests/unit/agents/test_analysis_agents.py`. Consume
`app/agents/contracts.py`, `app/rag/contracts.py`, and `app/rag/factory.py` unchanged.

## Teammate three: decisions, audit, content, reports, frontend

Own OperationsDecisionAgent, EvidenceAuditAgent, bounded correction detail, OperationContentSkill,
report refinement, and the later frontend. Start at `app/agents/operations_decision.py`,
`app/agents/evidence_audit.py`, `app/skills/operation_content/`, `app/services/report_exporter.py`,
and `tests/unit/agents/test_decision_agents.py`. The frontend remains deferred until its later phase.

## Shared files and merge order

The Contract Maintainer owns every file listed in `docs/contract-governance.md`; these files are not
co-owned by the three teammates. Recommended branches are `data/<topic>`, `analysis/<topic>`, and
`decision/<topic>`. Merge any required `contract/<topic>` PR first, then merge/rebase data, analysis,
and decision PRs in that order, running all gates after each merge. The three business branches can
otherwise develop simultaneously because Demo adapters, statistics Stub, in-memory RAG, and shared
builders are available now.

This refactor deliberately did not complete any of those business implementations.
