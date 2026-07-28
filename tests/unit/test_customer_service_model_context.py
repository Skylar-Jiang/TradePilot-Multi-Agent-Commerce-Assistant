from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.enums import AuditStatus, CustomerServicePersonality, DataOrigin, ImplementationStatus
from app.core.exceptions import TradePilotError
from app.schemas.customer_service import CustomerServiceMessageRequest
from app.schemas.report import FinalReport, ReportSectionDescriptor
from app.services.customer_service_agent_service import CustomerServiceAgentService


class _CapturingModel:
    def __init__(self) -> None:
        self.prompt = None

    def invoke(self, prompt):  # type: ignore[no-untyped-def]
        self.prompt = prompt
        return SimpleNamespace(content="这是模型基于完整报告上下文给出的解释。")


class _FailingModel:
    def invoke(self, _prompt):  # type: ignore[no-untyped-def]
        raise RuntimeError("provider unavailable")


def _report() -> FinalReport:
    return FinalReport(
        report_id="report-1",
        run_id="run-1",
        version=1,
        audit_status=AuditStatus.PASS,
        data_origin=DataOrigin.DEMO,
        implementation_status=ImplementationStatus.PRODUCTION,
        is_demo=True,
        disclaimer="演示报告",
        sections={"launch_marketing_strategy": {"channel_strategy": ["内容种草"]}},
        section_index={
            "launch_marketing_strategy": ReportSectionDescriptor(
                section_id="launch-marketing-strategy",
                title="新商品上市营销策略",
            )
        },
        markdown_path="report.md",
        json_path="report.json",
        created_at=datetime.now(UTC),
    )


def test_customer_service_uses_configured_model_for_demo_reports() -> None:
    model = _CapturingModel()
    service = CustomerServiceAgentService(session=SimpleNamespace(), model=model)  # type: ignore[arg-type]
    service._conversation_history = lambda _conversation_id: "user: 之前的追问"  # type: ignore[method-assign]
    reply = service._generate_explanation(
        report=_report(),
        section_id="launch-marketing-strategy",
        request=CustomerServiceMessageRequest(
            message="为什么建议优先做内容种草？",
            personality=CustomerServicePersonality.PROFESSIONAL,
        ),
        conversation_id="conversation-1",
        grounded_answer="这是证据化的基础说明。",
    )

    assert reply == "这是模型基于完整报告上下文给出的解释。"
    assert model.prompt is not None
    assert "内容种草" in model.prompt.to_string()
    assert "之前的追问" in model.prompt.to_string()


def test_customer_service_surfaces_model_failures_instead_of_using_a_template_reply() -> None:
    service = CustomerServiceAgentService(session=SimpleNamespace(), model=_FailingModel())  # type: ignore[arg-type]
    service._conversation_history = lambda _conversation_id: "（无历史对话）"  # type: ignore[method-assign]

    with pytest.raises(TradePilotError, match="Customer-service model request failed"):
        service._generate_explanation(
            report=_report(),
            section_id="launch-marketing-strategy",
            request=CustomerServiceMessageRequest(
                message="解释一下",
                personality=CustomerServicePersonality.PROFESSIONAL,
            ),
            conversation_id="conversation-1",
            grounded_answer="这是证据化的基础说明。",
        )
