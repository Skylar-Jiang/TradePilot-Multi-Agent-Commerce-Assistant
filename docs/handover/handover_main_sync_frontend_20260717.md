# TradePilot main 同步与前端适配说明

日期：2026-07-17
工作分支：`feat/tradepilot-frontend`
同步来源：`origin/main`（`cf40574 add tax`）

## 1. 本次修改内容

### 同步 main 新能力

- 合并美国 HTS 税则数据、HS 映射配置、本地税则查询 provider 和报告关税章节。
- 合并模型 provider 兼容更新，保留 MiniMax、Qwen、DeepSeek 与通用 OpenAI-compatible 路径。
- 合并税则 provider 注册、报告导出以及对应的单元、契约和集成测试。

### 前端适配

- Real 模式在美国市场任务中显式请求 `us-tariff-provider` 和 `tariff_rate` 背景数据。
- 新增独立的“关税合规”页面，展示候选 HTS、一般税率、匹配置信度、风险标记、选品影响和税则证据链。
- Agent 数据准备节点增加 HTS 税则提示，报告空状态补充美国关税内容说明。
- 保持可收起侧栏、独立 Hash 页面、四 Agent 身份色和深色 Liquid Glass 视觉体系。
- 补充 375px 响应式适配、键盘焦点、语义化状态和 `prefers-reduced-motion` 支持。

### 中文输入适配

- 在 HS 映射中补充“犬用胸背带 / 胸背带”中文别名，使当前前端默认商品能匹配候选 HTS `4201006000`。
- 仍将税号标记为候选归类，保留报关行人工复核要求，不把系统匹配包装成正式归类结论。

### 合并冲突与质量修复

- 合并运营决策 Prompt：同时保留中文输出、字符串定位字段、证据 ID 约束和关税决策输入要求。
- 合并模型工厂测试，覆盖 MiniMax、Qwen、DeepSeek 和通用 OpenAI-compatible provider。
- 清理 main 新增测试中的重复字典键、重复测试函数、导入排序和行宽问题，保证 Ruff 通过。

## 2. 为什么要修改

main 已新增税则能力，但旧前端没有在分析请求中启用 provider，也没有展示报告中的 `tax_and_tariff_snapshot` 与 `tariff_selection_impact`。如果只合并后端，用户在界面上无法知道税则是否加载，也无法看到关税对 landed cost、定价和毛利的影响。

此外，前端默认使用中文商品类别，而 Phase 1 HS 映射主要是英文数据集类别；补充明确的中文别名可以避免同一个胸背带品类因为语言差异产生 `missing_hs_mapping`，同时不扩大自动推断范围。

## 3. 验证结果

- 前端生产构建：通过。
- 前端 ESLint：通过。
- Python 完整测试：`174 passed, 3 skipped`。
- Ruff：通过。
- 本地税则库：由 2026 Rev. 11 原始数据导入 `13666` 条记录。
- 中文默认商品税则查询：1 条证据，HTS `4201006000`，一般税率 `2.8%`，0 个查询缺口。
- 浏览器验收：桌面端正常；375px 宽度无横向溢出；控制台无前端错误。
- Real 端到端任务：4 个 Agent 均实际调用模型并生成报告；税则报告包含 provider、税号、税率、证据和风险标记。

端到端测试中 `UserInsightAgent` 因本地合成评论证据不足返回 `insufficient_evidence`，审校结果要求人工复核。这是证据护栏的预期状态，不是接口或模型调用失败。

## 4. 分支与合并边界

- 本次工作仅保留在 `feat/tradepilot-frontend`。
- 没有向远端 `main` 推送，也没有改写 `origin/main`。
- 后续应通过功能分支评审或 Pull Request 决定是否进入 main。

## 5. 本地运行说明

美国税则 provider 只有在以下两个文件存在时才会自动注册：

- `config/trade/hs_mapping.yaml`
- `data/external/serving/tariff_rules.sqlite`

serving SQLite 属于本地生成文件，不提交到 Git。可在项目根目录运行：

```powershell
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe scripts\import_us_hts_tariffs.py `
  --input data\raw\us_hts_2026_rev11.csv `
  --default-effective-date 2026-01-01 `
  --default-hs-version '2026 Rev. 11'
```

API Key 继续通过忽略的 `.env` 或进程环境变量注入，不写入代码、文档或 Git 历史。
