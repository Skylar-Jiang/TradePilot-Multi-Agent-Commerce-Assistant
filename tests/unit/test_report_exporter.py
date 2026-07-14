import json
from pathlib import Path

from app.agents.contracts import EvidenceAuditAgentInput, OperationsDecisionAgentInput
from app.agents.evidence_audit import EvidenceAuditAgent
from app.agents.operations_decision import OperationsDecisionAgent
from app.core.enums import AgentStatus, DataMode, DataOrigin, KnowledgeType
from app.schemas.analysis import ProductMarketAnalysis, UserInsight
from app.schemas.evidence import EvidenceReference
from app.schemas.product import ProductCreate, ProductProfile
from app.schemas.report import DEMO_DISCLAIMER
from app.services.report_exporter import ReportExporter
from app.workflows.state import TradePilotState


def completed_state() -> TradePilotState:
    product = ProductProfile(
        product_id="product-1",
        data_origin=DataOrigin.DEMO,
        **ProductCreate(
            name="DEMO Portable Organizer",
            category="demo",
            features=["compact storage"],
            use_scenarios=["dorm rooms"],
            target_market="United States",
            target_audience=["college students"],
            data_mode=DataMode.DEMO,
        ).model_dump(),
    )
    market = ProductMarketAnalysis(
        status=AgentStatus.SUCCEEDED,
        data_origin=DataOrigin.DEMO,
        evidence_ids=["market-1"],
    )
    insight = UserInsight(
        status=AgentStatus.SUCCEEDED,
        data_origin=DataOrigin.DEMO,
        evidence_ids=["review-1"],
    )
    plan = OperationsDecisionAgent().run(
        OperationsDecisionAgentInput(
            product=product,
            product_market_analysis=market,
            user_insight=insight,
        )
    )
    audit = EvidenceAuditAgent().run(
        EvidenceAuditAgentInput(product=product, operation_plan=plan)
    )
    return TradePilotState(
        task_id="task-1",
        run_id="run-1",
        session_id="session-1",
        thread_id="thread-1",
        data_mode=DataMode.DEMO,
        product_profile=product,
        target_market=product.target_market,
        product_market_analysis=market,
        user_insight=insight,
        operation_plan=plan,
        audit_result=audit,
        rag_evidence=[
            EvidenceReference(
                evidence_id="market-1",
                evidence_type="rag_excerpt",
                knowledge_type=KnowledgeType.PRODUCT_KNOWLEDGE,
                source_name="Demo product source",
                excerpt="Demo product evidence.",
                data_origin=DataOrigin.DEMO,
                is_demo=True,
            ),
            EvidenceReference(
                evidence_id="review-1",
                evidence_type="rag_excerpt",
                knowledge_type=KnowledgeType.REVIEW_INSIGHT,
                source_name="Demo review source",
                excerpt="Demo review evidence.",
                data_origin=DataOrigin.DEMO,
                is_demo=True,
            ),
        ],
        report_version=2,
    )


def test_exporter_writes_versioned_structured_json_and_markdown(tmp_path: Path) -> None:
    report = ReportExporter(tmp_path).export(completed_state())

    json_path = Path(report.json_path)
    markdown_path = Path(report.markdown_path)
    assert json_path.exists()
    assert markdown_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["data_origin"] == "demo"
    assert payload["implementation_status"] == "scaffold"
    assert payload["disclaimer"] == DEMO_DISCLAIMER
    assert payload["version"] == 3
    assert payload["sections"]["content_playbook"]["title"]
    assert len(payload["sections"]["content_playbook"]["bullets"]) == 5
    assert payload["sections"]["executive_summary"]["evidence_count"] == 2
    assert {item["evidence_id"] for item in payload["sections"]["evidence_index"]} == {
        "market-1",
        "review-1",
    }
    assert "DEMO" in markdown
    assert "Scaffold" in markdown
    assert "Content playbook" in markdown
    assert "market-1" in markdown
    assert DEMO_DISCLAIMER in markdown
