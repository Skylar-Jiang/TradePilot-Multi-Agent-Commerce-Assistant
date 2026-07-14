# Data contract

Alembic creates eleven SQLAlchemy baseline tables: `products`, `product_files`, `competitor_offers`,
`reviews`, `knowledge_sources`, `analysis_runs`, `agent_outputs`, `evidence_references`, `reports`,
`conversations`, and `messages`. Domain-specific product fields belong in `attributes_json` or
`metadata_json`; the scaffold intentionally has no domain-specific migration or analytical SQL.
Alembic revision `20260714_0001` is the baseline matching those models.

Mode and origin are independent and explicit:

| Value | Meaning |
| --- | --- |
| `demo` | Bundled deterministic fixtures, always visibly marked |
| `mock` | Test/simulation boundary; analysis is not implemented in this phase |
| `real` | Real external/model execution; never falls back |
| `user` | User-supplied source origin, used for Real product profiles |

Exact prices, ratings, counts, and ratios may only enter conclusions from user input, SQL,
Repository, or `StatisticsProvider`. `StatisticsResult` is the formal SQL-to-Agent boundary; its
default Stub contains no metrics. RAG excerpts are evidence text, not a numeric authority.

Database model, Repository Protocol, and migration changes are Contract Maintainer work through a
standalone Contract PR. Teammate one can implement providers against existing tables without
blocking teammates two or three.
