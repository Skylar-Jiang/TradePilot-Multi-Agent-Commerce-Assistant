# Agent contract

Every Agent has its own Pydantic input/output, LCEL sequence, model-backed Real path, deterministic Demo compatibility
path, and LangGraph node.

| Agent | Real provider | Evidence scope | Output responsibility |
| --- | --- | --- | --- |
| ProductMarketAgent | DeepSeek | candidate profile, peer products, SQL statistics, optional sourced background | price plus features, structure, positioning, ratings, homogenization, differentiation, missing parameters, validations |
| UserInsightAgent | DeepSeek | peer reviews and sample boundary | needs, positives, pains, purchase factors, use/maintenance concerns, validations, opportunities, limitations |
| OperationsDecisionAgent | Qwen | validated parallel outputs and existing evidence IDs | positioning, evidence-bound conclusions, launch actions |
| EvidenceAuditAgent | Qwen plus deterministic guards | plan, all carried evidence, SQL statistics, expected peer group | attribution, scope, accessory, numeric, hypothesis, ID, conflict, and risk checks |

Real outputs use `implementation_status=production`. Every Real path uses the LCEL sequence
`prompt | model | normalization | PydanticOutputParser`. Model JSON is normalized before final Pydantic validation;
unknown evidence IDs are removed, invalid status prose is converted from the actual valid-evidence boundary, and
unsupported numeric values are replaced with an explicit pending-validation marker. Model audit findings are advisory;
deterministic checks alone decide blocking rejection and manual review.

Malformed JSON or output-Schema failures retry the complete typed chain up to `MODEL_PARSE_MAX_RETRIES`. Provider
transport retries are controlled separately by `MODEL_MAX_RETRIES`; runtime/provider exceptions are not mistaken for
parse failures. Output metadata records model-call count, parse-retry count, parser name and returned token usage.

ProductMarketAgent and UserInsightAgent receive the same `peer_group_id` and selected ASIN set and run in parallel.
No Agent may call the database or claim peer reviews belong to the candidate product.

Optional background context is admitted only through `BackgroundProviderRegistry` and carries provider, source URI,
jurisdiction and effective/query dates. Empty context remains a data gap. It does not authorize any Agent to generate
policy, tax, platform or trend facts from model memory.
