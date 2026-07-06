# Skill 化改造说明

系统保留原有 Agent 与 RAG 能力，新增 Skill 封装层。

当前 Skill：

- `price_monitor_skill`：分析生鲜价格波动、平台价差、单位价格、促销力度、涨跌幅和价格异常。
- `product_update_skill`：分析新品上架、节令商品、预制菜新品、产地变化、规格变化。
- `sentiment_risk_skill`：分析不新鲜、缺斤少两、配送慢、包装破损、售后差、价格争议。
- `trend_compare_skill`：分析肉蛋奶、基础蔬菜、水果等商品的日/周/月趋势。
- `report_generation_skill`：生成生鲜电商竞品分析报告。
- `orchestrator_skill`：调度价格、新品、舆情、趋势和报告生成 Skill。

默认 `provider=mock`，无真实模型 Key 时也能演示。证据不足时统一输出 `insufficient_evidence=true`，禁止凭空编造。
