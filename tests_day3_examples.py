from modules.competitor_analysis_chains import build_prompt_inputs, extract_keywords
from modules.conversation_crawler import extract_webpage_text


def test_extract_keywords_keeps_meaningful_competitor_terms():
    text = "盒马鲜生鸡蛋会员价下降，叮咚买菜推出满减，履约时效和售后评价出现差异。"

    result = extract_keywords(text, max_chars=24)

    assert result == "盒马鲜生鸡蛋会员价下降，叮咚买菜推出满减，履约时"


def test_build_prompt_inputs_normalizes_empty_fields():
    result = build_prompt_inputs(product="盒马鲜生", competitor="", key_points="  价格更低  ")

    assert result == {
        "product": "盒马鲜生",
        "competitor": "未指定竞品",
        "key_points": "价格更低",
    }


def test_extract_webpage_text_removes_script_and_keeps_links():
    html = """
    <html>
      <head><title>竞品新闻</title><script>bad()</script></head>
      <body>
        <h1>盒马推出夏季水果促销</h1>
        <a href="/news/1">新闻标题一</a>
      </body>
    </html>
    """

    result = extract_webpage_text(html, source_url="https://example.com/list")

    assert result["title"] == "竞品新闻"
    assert "bad()" not in result["text"]
    assert "盒马推出夏季水果促销" in result["text"]
    assert "新闻标题一" in result["text"]


if __name__ == "__main__":
    test_extract_keywords_keeps_meaningful_competitor_terms()
    test_build_prompt_inputs_normalizes_empty_fields()
    test_extract_webpage_text_removes_script_and_keeps_links()
    print("day3 example tests passed")
