from modules.agent_core import registry_snapshot
from modules.dashboard import comparison_data, competitor_summary, risk_tags_view
from modules.data_loader import load_csv
from modules.llm_client import parse_json_object
from modules.rag_chain import SimpleRAGIndex, build_project_index
from modules.skill_core import list_skills, run_skill
from modules.source_manager import load_sources, run_collection_job
from modules.tools import ingest_csv_tool, retrieve_evidence_tool


def test_data_and_rag():
    records = load_csv("data/raw/hema_price_manual.csv")
    assert len(records) >= 3
    assert all(record.source_url for record in records)

    result = ingest_csv_tool("data/raw/hema_price_manual.csv")
    assert result["count"] >= 3

    index = build_project_index()
    assert len(index.chunks) >= 6

    evidence = retrieve_evidence_tool("盒马 鸡蛋 牛奶 番茄 价格", competitor="盒马", top_k=3)
    assert evidence
    assert evidence[0]["source_url"]


def test_collection_and_dashboard():
    sources = load_sources()
    assert sources
    job = run_collection_job(force=True, use_llm_filter=False)
    assert job["source_count"] >= 1
    assert competitor_summary()
    assert comparison_data()["dimensions"] == ["price", "new_product", "sentiment"]
    assert isinstance(risk_tags_view(), list)


def test_agents_registered():
    names = {item["name"] for item in registry_snapshot()}
    assert {"price_monitor", "new_product", "sentiment"} <= names


def test_json_parser():
    parsed = parse_json_object('```json\n{"ok": true, "items": [1]}\n```')
    assert parsed["ok"] is True


def test_skills_mock_provider():
    skill_names = {item["name"] for item in list_skills()}
    assert {
        "price_monitor_skill",
        "product_update_skill",
        "sentiment_risk_skill",
        "trend_compare_skill",
        "report_generation_skill",
        "orchestrator_skill",
    } <= skill_names
    result = run_skill(
        "orchestrator_skill",
        {
            "competitor": "盒马",
            "query": "分析盒马近期肉蛋奶和基础蔬菜的价格变化、促销活动和负面舆情",
            "top_k": 2,
            "provider": "mock",
        },
    )
    assert result["competitor"] == "盒马"
    assert "analysis_result" in result
    assert "insufficient_evidence" in result


if __name__ == "__main__":
    test_data_and_rag()
    test_collection_and_dashboard()
    test_agents_registered()
    test_json_parser()
    test_skills_mock_provider()
    print("local tests passed")
