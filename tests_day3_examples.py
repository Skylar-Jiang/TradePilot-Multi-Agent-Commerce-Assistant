from modules.competitor_analysis_chains import build_prompt_inputs, extract_keywords
from pathlib import Path
from tempfile import TemporaryDirectory

from modules.conversation_crawler import crawl_public_webpage, extract_webpage_text, write_crawl_result
from modules.price_memory_dialogue import create_price_memory_prompt, run_price_memory_dialogue


def test_extract_keywords_keeps_meaningful_competitor_terms():
    text = "山东寿光黄瓜批发价下降，河北黄瓜受降雨影响到货减少，辽宁市场低价到货。"

    result = extract_keywords(text, max_chars=24)

    assert result == "山东寿光黄瓜批发价下降，河北黄瓜受降雨影响到货减"


def test_build_prompt_inputs_normalizes_empty_fields():
    result = build_prompt_inputs(product="黄瓜", competitor="", key_points="  批发价更低  ")

    assert result == {
        "product": "黄瓜",
        "competitor": "未指定竞品",
        "key_points": "批发价更低",
    }


def test_extract_webpage_text_removes_script_and_keeps_links():
    html = """
    <html>
      <head><title>竞品新闻</title><script>bad()</script></head>
      <body>
        <h1>山东寿光黄瓜新批次上市</h1>
        <a href="/news/1">新闻标题一</a>
      </body>
    </html>
    """

    result = extract_webpage_text(html, source_url="https://example.com/list")

    assert result["title"] == "竞品新闻"
    assert "bad()" not in result["text"]
    assert "山东寿光黄瓜新批次上市" in result["text"]
    assert "新闻标题一" in result["text"]


def test_crawl_public_webpage_falls_back_to_sample_fresh_html():
    def failing_fetcher(_url: str) -> str:
        raise TimeoutError("network timeout")

    result = crawl_public_webpage("https://www.chinaprice.cn/", fetcher=failing_fetcher)

    assert result["used_fallback"] is True
    assert "生鲜批发价格公开样例" in result["title"]
    assert "山东寿光黄瓜" in result["text"]
    assert "network timeout" in result["error"]


def test_write_crawl_result_saves_markdown_and_csv(tmp_path: Path):
    page = {
        "title": "生鲜批发价格公开样例",
        "source_url": "https://www.chinaprice.cn/",
        "text": "鸡蛋价格下降，蔬菜价格平稳。",
        "used_fallback": True,
        "error": "timeout",
    }

    paths = write_crawl_result(page, tmp_path)

    assert paths["markdown"].exists()
    assert paths["csv"].exists()
    assert "生鲜批发价格公开样例" in paths["markdown"].read_text(encoding="utf-8")
    assert "https://www.chinaprice.cn/" in paths["csv"].read_text(encoding="utf-8-sig")


def test_price_memory_prompt_keeps_history_and_web_context_placeholders():
    prompt = create_price_memory_prompt()

    assert "{history}" in prompt.template
    assert "{web_context}" in prompt.template
    assert "{question}" in prompt.template


def test_price_memory_dialogue_mock_outputs_two_memory_turns():
    outputs = run_price_memory_dialogue(mock=True)

    assert len(outputs) == 2
    assert "山东寿光" in outputs[0]
    assert "上一轮记忆" in outputs[1]


if __name__ == "__main__":
    test_extract_keywords_keeps_meaningful_competitor_terms()
    test_build_prompt_inputs_normalizes_empty_fields()
    test_extract_webpage_text_removes_script_and_keeps_links()
    test_crawl_public_webpage_falls_back_to_sample_fresh_html()
    with TemporaryDirectory() as temp_dir:
        test_write_crawl_result_saves_markdown_and_csv(Path(temp_dir))
    test_price_memory_prompt_keeps_history_and_web_context_placeholders()
    test_price_memory_dialogue_mock_outputs_two_memory_turns()
    print("day3 example tests passed")
