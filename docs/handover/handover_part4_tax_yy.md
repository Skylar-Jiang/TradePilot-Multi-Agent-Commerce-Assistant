# TradePilot 美国税费接入工作交接说明

更新时间：2026-07-17

本文档用于交接本轮围绕“美国市场税费接入”的实际改动、当前状态、运行方式、遗留问题与后续建议。  
本轮工作严格沿用既有架构，不重做整体架构分析。

## 一、本轮目标与范围

本轮目标不是新增独立市场情报系统，而是在现有 TradePilot 工作流中，把美国 HTS 税费能力接入到真实分析链路，并最终反映到 Markdown 报告中。

本轮明确完成的范围：

1. 继续完善美国 HTS 路线。
2. 按项目现有 `categories / product.category` 扩展 HS 映射。
3. 将税费从后台 evidence 提炼为 agent 可消费的决策输入。
4. 在最终 Markdown 报告中明确体现税费对选品的影响。
5. 保持现有 agent 主逻辑与 workflow 主结构不变，仅做增量接入和兼容性修补。

本轮明确未做的范围：

1. 未接入欧洲市场税费。
2. 未新增独立前端税费可视化。
3. 未重构 peer matching 主体策略。

## 二、本轮完成的核心结果

### 1. 美国 HTS 税费已经进入真实报告链路

此前税费只停留在 provider/evidence 层，本轮已经打通到最终真实 Markdown 报告：

1. provider 能查询本地 `tariff_rules.sqlite`
2. workflow state 能携带 `background_context`
3. `operations_decision` 能消费税费摘要
4. `report_exporter` 能输出：
   - `美国税费快照`
   - `美国税费对选品影响`


### 2. HS 映射在既有类目上做了安全扩展

本轮没有发明新分类体系，而是继续沿用项目已有 `product.category` 和现有 categories 做对齐扩展。  
当前已补充或强化的映射集中在这些类目及别名：

1. `Fountains`
2. `Basic Collars`
3. `Slip & Martingale Collars`
4. `Vest Harnesses`
5. `Basic Halter Harnesses`
6. `Basic Leashes`
7. `Shampoos`

同时新增了一批安全 alias，例如：

1. `pet water fountain`
2. `cat water fountain`
3. `dog harness`
4. `dog leash`
5. `pet shampoo`

仍然没有为了覆盖率去强猜的类目，继续保留 `data_gaps` 更安全。

### 3. 税费 evidence 已提炼成 agent 可消费的决策输入

`us_tariff_provider` 现在不只是返回一条证据文本，而是会生成结构化税费决策输入，包括：

1. `tariff_summary`
2. `tariff_profiles`
3. `tariff_risk_flags`
4. `tariff_cost_burden`
5. `manual_review_required`
6. `selection_impact`
7. `tariff_recommended_actions`
8. `agent_decision_brief`
9. `primary_tariff_profile`

这部分让税费不再只是 evidence index 里的背景说明，而是真正能进入选品判断与报告表达。

### 4. DeepSeek-only 的 real 模式已经可运行

此前项目把 `real_model_configured` 写得过严，要求 `DeepSeek` 和 `Qwen` 同时存在。  
本轮已调整为：

1. 文本 real 链路支持 `DeepSeek-only`
2. `OperationsDecisionAgent` 与 `EvidenceAuditAgent` 在没有 Qwen 时可回退到 DeepSeek
3. 没有候选商品图片时，图像理解会被安全跳过，不再因为缺 Qwen vision 直接中断整条 real 运行
4. 若 `EMBEDDING_MODEL` 置空，则使用本地 hash embedding，避免误走 Qwen embedding

这使得只配一个有效的 `DeepSeek API key` 也能跑出真实中文报告。

## 三、主要代码改动

### 1. 税费 provider 与映射

- [config/trade/hs_mapping.yaml](/f:/TradePilot/config/trade/hs_mapping.yaml)
  - 扩展美国 HTS 安全映射与 alias

- [app/background/providers/us_tariff_provider.py](/f:/TradePilot/app/background/providers/us_tariff_provider.py)
  - 增加税费结构化摘要
  - 增加决策输入字段
  - 增加 landed cost / 毛利 / 人工复核方向的表达

### 2. agent 接入与兼容处理

- [app/agents/operations_decision.py](/f:/TradePilot/app/agents/operations_decision.py)
  - 在不改主逻辑骨架的前提下接入税费决策输入
  - 允许背景税费 evidence ID 进入 plan
  - 对模型返回的对象型 `positioning` 做兼容归一化
  - 将 `background_context` 中的数字纳入允许来源，避免 HTS 编码与税率数字被误替换

- [app/agents/evidence_audit.py](/f:/TradePilot/app/agents/evidence_audit.py)
  - 修复税费背景中的 HTS 编码被误判为未验证数字的情况

- [app/agents/model_factory.py](/f:/TradePilot/app/agents/model_factory.py)
  - `operations` 与 `audit` 支持 DeepSeek-only real 模式

### 3. 真实运行兼容与跳过逻辑

- [app/services/product_vision_service.py](/f:/TradePilot/app/services/product_vision_service.py)
  - 仅在真正存在有效候选图片时才初始化 vision model
  - 无图场景不再因为缺 `QWEN_API_KEY` 中断整条 real 工作流

- [app/core/config.py](/f:/TradePilot/app/core/config.py)
  - 放宽 `real_model_configured`
  - 允许只用 DeepSeek 跑文本 real 链路

### 4. 报告与配置文档

- [docs/model-provider-configuration.md](/f:/TradePilot/docs/model-provider-configuration.md)
  - 新增模型 provider 配置文档
  - 覆盖 `DeepSeek-only` / `DeepSeek + Qwen` / `OpenAI-compatible`

## 四、测试与验证

### 1. 已补充或更新的测试

- [tests/unit/background/test_us_tariff_provider.py](/f:/TradePilot/tests/unit/background/test_us_tariff_provider.py)
- [tests/unit/agents/test_decision_agents.py](/f:/TradePilot/tests/unit/agents/test_decision_agents.py)
- [tests/unit/agents/test_model_factory.py](/f:/TradePilot/tests/unit/agents/test_model_factory.py)
- [tests/unit/test_config.py](/f:/TradePilot/tests/unit/test_config.py)
- [tests/integration/test_background_provider_workflow.py](/f:/TradePilot/tests/integration/test_background_provider_workflow.py)

### 2. 已执行通过的命令

统一使用 `shixun` 虚拟环境执行。

```powershell
& C:\Users\ASUS\.conda\envs\shixun\python.exe -m pytest tests\unit\agents\test_decision_agents.py tests\unit\agents\test_model_factory.py tests\unit\test_config.py tests\integration\test_background_provider_workflow.py -q
```

本轮最终回归结果：

- `19 passed`

### 3. 已完成的真实运行验证

真实运行已经验证通过以下路径：

1. `data_mode=real`
2. `DeepSeek-only`
3. 美国税费 provider 命中
4. 中文长报告生成
5. 报告中包含美国税费 section
6. HTS 编码与税率数字在报告中正常保留

最新真实运行示例：

- `run_id = d7e920fb-bbd6-40e5-b1b2-3dd7d59a140c`
- `report_id = 5acf14a6-9d7c-4639-97a0-418b747aea7d`
- 状态：`manual_review`

这里的 `manual_review` 不是系统链路失败，而是分析质量上的人工复核提示，主要因为当前 peer matching 只抓到少量配件商品，样本不够理想。

## 五、当前运行配置建议

当前最推荐的本地配置是 `DeepSeek-only` 文本 real 模式。

关键 `.env` 形态如下：

```env
DEEPSEEK_API_KEY=你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com

QWEN_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=

MODEL_ANALYSIS=deepseek-v4-flash
MODEL_FAST=deepseek-v4-flash
MODEL_REPORT=deepseek-v4-flash

EMBEDDING_MODEL=
RAG_USE_CHROMA=true
```

完整配置说明见：

- [model-provider-configuration.md](/f:/TradePilot/docs/model-provider-configuration.md)

## 六、当前结论

### 已经可以认为“跑通”的部分

1. 美国 HTS provider 已接入工作流
2. 税费 evidence 已进入真实报告
3. 税费已被提炼成 agent 可消费的决策输入
4. 报告中已明确体现税费对选品的影响
5. DeepSeek-only real 模式已实际跑通

### 还没有完全收口的部分

1. 部分真实商品仍会因 peer matching 命中配件而进入 `manual_review`
2. 美国 HTS 映射还可以继续补高频但归类清晰的类目
3. 真实报告质量仍受 peer group 样本质量约束
4. 目前没有恢复美国 Census 贸易统计能力

## 七、后续建议

如果下一轮继续沿着当前主线推进，建议优先顺序如下：

1. 继续扩展 `config/trade/hs_mapping.yaml`
   - 仅补高频且归类清晰的现有类目

2. 收紧 peer matching 对“配件”的误命中
   - 尤其是 `Fountains` 这类场景，优先拉完整饮水机而不是刷子、滤棉

3. 补更多美国税费真实报告断言
   - 确保 HTS 编码、税率、人工复核状态、风险标记在报告中稳定保留

4. 视需要增强 importer 兼容性
   - 针对更多真实 HTS 导出格式变体


## 八、最短复现步骤

### 1. 启动服务

```powershell
cd F:\TradePilot
& C:\Users\ASUS\.conda\envs\shixun\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. 运行真实商品分析

使用已有 API 流程：

1. `POST /api/v1/products`
2. `POST /api/v1/analysis-runs`
3. `GET /api/v1/reports/{report_id}/markdown`

建议测试商品：

- `Cordless Pet Fountain`
- `category = Fountains`
- `data_mode = real`
- `background_context_types = ["tariff_rate"]`

### 3. 预期结果

最终 Markdown 报告中应能看到：

1. 中文完整分析报告
2. `美国税费快照`
3. `美国税费对选品影响`
4. `HTS 8421210000`
5. `一般税率 Free`
6. 人工复核提示

## 十、交接结论

本轮“美国税费接入”已经完成从本地 HTS serving 数据，到 background evidence，到 agent 可消费税费摘要，再到真实中文 Markdown 报告展示的闭环。  
当前已经不是“税费能力没接上”，而是“税费主链路已通，下一步要继续提升 peer matching 质量与报告分析质量”。

