# Agent contract

Every Agent has its own input model, output model, file, LCEL `RunnableSequence`, and LangGraph node.
All inputs and outputs are validated by Pydantic v2.

| Agent | Output | Current behavior | Future owner |
| --- | --- | --- | --- |
| ProductMarketAgent | `ProductMarketAnalysis` | Deterministic Demo scaffold or `insufficient_evidence` | Teammate two |
| UserInsightAgent | `UserInsight` | Deterministic Demo scaffold or `insufficient_evidence` | Teammate two |
| OperationsDecisionAgent | `OperationPlan` | Binds existing IDs and emits no business rules | Teammate three |
| EvidenceAuditAgent | `AuditResult` | Checks Demo/Scaffold markers only | Teammate three |

All four outputs include `data_origin=demo` and `implementation_status=scaffold`. No complete Prompt,
sentiment logic, market statistics, decision rules, marketing copy, or semantic audit exists here.
Agent contracts and the StateGraph field boundaries are the stable extension points.

`ProductMarketAgentInput` and `UserInsightAgentInput` both require the same validated
`StatisticsResult`. The `statistics_provider` LangGraph node writes
`TradePilotState.statistics_result` once before those two nodes fan out. The default
`ScaffoldStatisticsProvider` returns empty metrics and `insufficient_evidence`; teammate one replaces
the provider, while teammate two consumes the contract. Neither team needs to edit the graph.

The Contract Maintainer owns `app/agents/contracts.py`, `TradePilotState`, and graph topology.
