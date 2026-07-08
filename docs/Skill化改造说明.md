# Skill 化改造说明

系统保留原有 Agent 与 RAG 能力，新增 Skill 封装层。代码结构没有大改，主要将业务口径统一为生鲜批发采购场景下的区域供应源竞品对标。

当前 Skill：

- `price_monitor_skill`：分析生鲜批发价格波动、区域价差、单位价格、涨跌幅、异常价差和采购优势。
- `product_update_skill`：分析新产季上市、新品种、新产区、新规格、新批次供应和到货量变化。
- `sentiment_risk_skill`：分析食品安全、抽检不合格、质量风险、供应短缺、天气物流影响和监管通报。
- `trend_compare_skill`：分析黄瓜、番茄、鸡蛋、猪肉等品类的日/周/月行情趋势和区域供应源对比。
- `report_generation_skill`：生成生鲜批发采购区域供应源竞品对标报告。
- `orchestrator_skill`：调度价格、供应动态、质量风险、趋势和报告生成 Skill。

默认 `provider=mock`，无真实模型 Key 时也能演示。证据不足时统一输出 `insufficient_evidence=true`，禁止凭空编造。

说明：接口中的 `competitor` 字段暂时保留，业务含义统一为“区域供应源竞品”，不是品牌、公司或电商平台。
