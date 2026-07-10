# Day 5 Log and Weekly Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the main project's current RAG implementation once, retain the real Day 5 evidence, replace illustrative images with actual code and output, and write the Day 5 programmer log plus the first-week report.

**Architecture:** A small Day 5 runner imports the existing RAG build and retrieval entry points instead of copying their implementation. A focused test validates the result schema with fakes before the runner is connected to the real project; the successful real run writes one JSON artifact that is quoted by the logs.

**Tech Stack:** Python 3.12, python-dotenv, LangChain Hugging Face embeddings, ChromaDB, Markdown, PowerShell.

---

### Task 1: Add a tested Day 5 RAG result builder

**Files:**
- Create: `daily-tasks/每日任务/day5/tests_day5.py`
- Create: `daily-tasks/每日任务/day5/day5_rag_demo.py`

- [ ] **Step 1: Write the failing result-schema test**

Create `tests_day5.py` with a fake index and fake evidence list. Assert that `make_result()` records the run date, query, filtered embedding settings, Chroma collection name, unique record count, chunk count, evidence count, and full evidence metadata.

```python
from day5_rag_demo import make_result


class FakeCollection:
    name = "competitor_intelligence_baai_bge_m3"


class FakeIndex:
    collection = FakeCollection()
    embedding_settings = {
        "provider": "huggingface",
        "model_name": "BAAI/bge-m3",
        "device": "cpu",
        "normalize_embeddings": True,
        "batch_size": 64,
        "cache_dir": "ignored",
    }
    chunks = [
        type("Chunk", (), {"record_id": "record-1"})(),
        type("Chunk", (), {"record_id": "record-1"})(),
        type("Chunk", (), {"record_id": "record-2"})(),
    ]


def test_make_result():
    evidence = [
        {
            "chunk_id": "record-1-0",
            "record_id": "record-1",
            "title": "山东寿光黄瓜价格",
            "text": "山东寿光黄瓜当前价格为 3.7 元/kg。",
            "source_url": "https://example.test/shouguang",
            "competitor": "山东寿光黄瓜",
            "dimension": "price",
            "collected_at": "2026-07-10",
        }
    ]
    result = make_result(FakeIndex(), evidence, "价格对比")
    assert result["run_date"] == "2026-07-10"
    assert result["query"] == "价格对比"
    assert result["embedding"]["model_name"] == "BAAI/bge-m3"
    assert "cache_dir" not in result["embedding"]
    assert result["collection"] == "competitor_intelligence_baai_bge_m3"
    assert result["record_count"] == 2
    assert result["chunk_count"] == 3
    assert result["evidence_count"] == 1
    assert result["evidence"] == evidence


if __name__ == "__main__":
    test_make_result()
    print("day5 tests passed")
```

- [ ] **Step 2: Run the test and verify that it fails**

Run:

```powershell
.\venv\Scripts\python.exe 'daily-tasks\每日任务\day5\tests_day5.py'
```

Expected: failure because `day5_rag_demo.py` does not exist yet.

- [ ] **Step 3: Implement the minimal Day 5 runner**

Create `day5_rag_demo.py`. Load `.env` before importing the RAG modules, expose `make_result()`, call `build_project_index()` and `retrieve_evidence_tool()`, write UTF-8 JSON beside the script, and print the same JSON.

```python
from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from modules.rag_chain import build_project_index
from modules.tools import retrieve_evidence_tool

QUERY = "对比山东寿光黄瓜、河北黄瓜和辽宁黄瓜的当前价格、区域价差和采购风险"
OUTPUT_PATH = Path(__file__).with_name("day5_rag_result.json")
EMBEDDING_FIELDS = ("provider", "model_name", "device", "normalize_embeddings", "batch_size")


def make_result(index, evidence: list[dict], query: str) -> dict:
    return {
        "run_date": "2026-07-10",
        "query": query,
        "vector_store": "Chroma",
        "collection": index.collection.name,
        "embedding": {
            key: index.embedding_settings[key]
            for key in EMBEDDING_FIELDS
        },
        "record_count": len({chunk.record_id for chunk in index.chunks}),
        "chunk_count": len(index.chunks),
        "evidence_count": len(evidence),
        "evidence": evidence,
    }


def main() -> None:
    index = build_project_index()
    evidence = retrieve_evidence_tool(
        query=QUERY,
        dimension="price",
        top_k=3,
    )
    result = make_result(index, evidence, QUERY)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the focused test and verify that it passes**

Run:

```powershell
.\venv\Scripts\python.exe 'daily-tasks\每日任务\day5\tests_day5.py'
```

Expected: `day5 tests passed`.

### Task 2: Produce and verify the real Day 5 result

**Files:**
- Create: `daily-tasks/每日任务/day5/day5_rag_result.json`
- Modify as generated by the existing main-project RAG build: `data/processed/rag_index.json`
- Modify as generated by the existing main-project RAG build: `data/processed/rag_index_meta.json`
- Modify as generated by the existing main-project RAG build: `chroma_db/`

- [ ] **Step 1: Run the Day 5 runner**

Run:

```powershell
.\venv\Scripts\python.exe 'daily-tasks\每日任务\day5\day5_rag_demo.py'
```

Expected: exit code 0 and JSON output containing the actual model, model-specific collection, non-zero record and chunk counts, and non-empty evidence.

- [ ] **Step 2: Validate the generated JSON**

Run a Python assertion that loads `day5_rag_result.json` and checks `vector_store == "Chroma"`, `record_count > 0`, `chunk_count > 0`, `evidence_count > 0`, and every evidence item includes `source_url`, `record_id`, `competitor`, `dimension`, and `collected_at`.

- [ ] **Step 3: Run the main-project RAG regression tests**

Run:

```powershell
.\venv\Scripts\python.exe tests_local.py
```

Expected: `local tests passed`.

### Task 3: Write the standalone Day 5 programmer log

**Files:**
- Create: `daily-tasks/每日日志/2413507蒋林瀞-7.10.md`

- [ ] **Step 1: Write the log using only the four required level-two headings**

Use `# 第五天 2026.7.10 星期五` as the document title. Under the four required `##` headings, include:

- LD's own tasks and the assignments to TS and PG.
- The statement that today's RAG, embedding, model-specific Chroma collection, Chinese chunking, vector retrieval, keyword fallback, and evidence metadata were added to the main project, followed by the functions those additions enable.
- Actual code blocks copied from `modules/rag_chain.py` for current embedding settings, collection naming, vector write, retrieval fallback, and diverse evidence selection.
- The actual command output and JSON values from `day5_rag_result.json`.
- The generated file locations and a concise LD acceptance table.
- Problems that actually occurred during implementation and the corresponding completed handling.
- A first-person summary without instructional language.

- [ ] **Step 2: Check the log structure and banned wording**

Assert that its level-two headings are exactly `任务安排`, `任务完成情况`, `工作中遇到的问题`, and `总结与思考`; check that it has no Markdown image syntax and contains none of `你应该`, `稳定复现`, or `主项目已经具备`.

### Task 4: Replace the Day 5 section in the combined daily log

**Files:**
- Modify: `daily-tasks/每日日志/2026.7.6-7.10每日日志.md`

- [ ] **Step 1: Replace only the fifth-day section**

Keep Day 1 through Day 4 byte-for-byte unchanged. Replace from `# 第五天 2026.7.10 星期五` to end of file with the content of the standalone Day 5 log, ensuring the two illustrative image links are removed.

- [ ] **Step 2: Verify the combined log**

Compare the prefix before the Day 5 marker with the committed version and assert equality. Assert that the updated Day 5 section contains the same four level-two headings and no `day5_rag_settings.png` or `day5_rag_index_search.png` references.

### Task 5: Write the first-week report from repository evidence

**Files:**
- Create: `daily-tasks/每日日志/2026.7.6-7.10第一周周报.md`

- [ ] **Step 1: Summarize Day 1 through Day 5 evidence**

Use the existing daily logs and generated files to record:

- Week dates, project name, and LD role.
- Day 1 environment, directory, engineering specification, and team-organization work.
- Day 2 model client and Prompt work evidenced by the Day 2 log.
- Day 3 LangChain component, memory, public crawler, runnable sequence, and generated report work.
- Day 4 three-source 60-record experiment, 580 chunks, Pandas cleaning, automatic labels, quality JSON, and analysis Markdown.
- Day 5 actual embedding model, Chroma collection, record count, chunk count, evidence count, and RAG behavior from the generated JSON.
- LD/TS/PG division of work, completed acceptance, problems handled during the week, and the second-week RAG/Function/Chain/project-review plan.

- [ ] **Step 2: Verify every numeric claim and path**

Check Day 4 numbers against `day4_run_summary.json` and `day4_quality_report.json`; check Day 5 numbers against `day5_rag_result.json`; confirm every referenced repository path exists.

### Task 6: Run final content and repository verification

**Files:**
- Verify all files created or modified by Tasks 1 through 5.

- [ ] **Step 1: Run formatting and content checks**

Run `git diff --check`, the focused Day 5 test, `tests_local.py`, JSON assertions, heading assertions, banned-word scans, image-link scans, and path-existence checks.

- [ ] **Step 2: Review the final diff for surgical scope**

Confirm that every changed line belongs to the Day 5 runner/result, the standalone Day 5 log, the combined log's Day 5 section, the weekly report, or the approved design/plan documents. Do not alter Day 1 through Day 4 content or unrelated main-project code.

- [ ] **Step 3: Record final evidence**

Report the exact test outputs, generated model/collection/count values, created file paths, and any remaining mismatch rather than inferring success.
