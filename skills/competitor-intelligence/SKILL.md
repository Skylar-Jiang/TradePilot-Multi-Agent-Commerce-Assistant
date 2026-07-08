---
name: competitor-intelligence
description: 分析指定生鲜电商竞品的公开情报、价格促销、商品动态和负面舆情，生成可追溯的对比摘要或报告。
trigger_keywords:
  - 竞品分析
  - 生鲜价格
  - 促销监控
  - 负面舆情
  - 竞争对手
location: ./skills/competitor-intelligence/SKILL.md
---

# Competitor Intelligence Skill

## 使用场景

当用户需要分析盒马、叮咚买菜、美团买菜、京东生鲜等生鲜电商竞品时触发本 Skill。输入可以是竞品名称、网页 URL、手工 CSV 数据或一段公开情报文本。

## 输入

- `competitor`：竞品名称，例如“盒马”。
- `query`：分析问题，例如“分析近期鸡蛋和牛奶价格变化”。
- `evidence`：公开网页、CSV、RAG 检索结果或人工整理文本。

## 输出

- 一句话结论。
- 价格、促销、新品/节令商品、负面舆情等关键发现。
- 可执行建议。
- 证据来源 URL 或文件路径。

## 使用示例

```text
请使用 competitor-intelligence 分析盒马近期肉蛋奶价格变化，并和叮咚买菜做对比。
```

## 执行规则

1. 优先使用公开、可追溯的数据源，不绕过登录、验证码或反爬限制。
2. 结论必须基于证据；证据不足时明确说明缺口。
3. 报告面向运营决策，避免空泛评价。
