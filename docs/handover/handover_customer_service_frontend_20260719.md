# TradePilot 客服 AI 与四页面前端适配说明（2026-07-19）

## 同步基线

- 工作分支：`feat/tradepilot-frontend`
- 最新上游：`origin/main` 的 `2c0ad67 CustomerServiceAgent`
- 本地合并提交：`cb54248 merge: sync customer service agent from main`
- 本次没有直接修改或推送远程 `main`。

## 为什么重构前端信息架构

上一版侧栏有任务、Agent、营销、证据、关税、审校、报告 7 个入口。功能虽然完整，但同一条分析链路被拆成过多页面，用户需要频繁切换才能理解上下游关系。

本轮按照四个核心 Agent 重新组织为 4 个主界面：

| 主界面 | 身份色 | 合并后的能力 |
| --- | --- | --- |
| 商品市场 | 白 | 真实任务创建、商品与市场输入、同类数据准备 |
| 用户洞察 | 粉 | 四 Agent 协作图、同类用户洞察、执行时间线 |
| 运营决策 | 棕 | 营销策略、Markdown 报告、报告客服 AI |
| 证据审校 | 蓝 | 审校结论、人工复核边界、美国 HTS、证据中心 |

营销策略/报告和审校/关税/证据仍保留独立内容，但改为主界面内部的二级切换，不再占用侧栏入口。

## CustomerServiceAgent 前端接入

对接接口：

- `POST /api/v1/reports/{report_id}/customer-service/messages`
- `GET /api/v1/reports/{report_id}/customer-service/conversations/{conversation_id}`

前端实现：

1. 在“运营决策”页面增加“客服 AI”入口和右侧对话抽屉。
2. 报告未生成时显示受控空态，避免用户误以为客服可以脱离报告回答。
3. 支持 `simple`、`professional`、`companion`、`innovative` 四种固定回复风格。
4. 首轮保存后端返回的 `conversation_id`，后续消息继续沿用同一会话。
5. 展示后端返回的意图动作、修改摘要、待澄清问题和报告版本。
6. 如果客服生成新 `report_id`，自动拉取新版结构化报告与 Markdown，并刷新当前页面。
7. 输入过程中禁用重复提交，并显示客服 Agent 正在核对报告边界的加载状态。
8. 明确提示客服不能编造销量、转化率或没有证据支持的新数字。

## 视觉与交互改进

- 四个主界面分别使用白、粉、棕、蓝语义色，并在侧栏显示 A01-A04。
- 页面切换使用基于 `opacity + transform` 的渐变进入效果，避免布局重排。
- 二级内容使用统一分段导航，当前状态同时由边框、背景和文字标记，不只依赖颜色。
- 客服抽屉使用遮罩、模糊和滑入动效，并提供明确关闭按钮。
- 保留 `prefers-reduced-motion`，用户要求减少动效时会禁用页面过渡和装饰动画。
- 修复客服抽屉与顶部栏的层叠上下文冲突，关闭按钮不会再被顶部栏拦截。
- 修复 375px 下粒子光晕造成的横向溢出。

## 上游质量修正

最新版 `main` 合入时带有 5 个 Ruff 问题，本分支已做纯格式/可读性修正：

- 调整 `app/api/v1/router.py` 导入顺序。
- 拆分客服受众规则的 3 个超长条件表达式。
- 拆分客服集成测试中的 1 个超长断言。

这些修改不改变业务行为。

## 验证结果

### 自动化检查

- 前端 `npm run lint`：通过。
- 前端 `npm run build`：通过。
- `python -m ruff check app tests scripts`：通过。
- `python -m pytest -q`：`217 passed, 3 skipped`。

### 运行中 API 冒烟

- 分析任务状态：`succeeded`。
- 第一轮解释请求：`action_taken=explain`，报告版本保持 v1。
- 第二轮定位调整：`action_taken=positioning_edit`，生成报告 v2。
- 两轮使用同一 `conversation_id`。
- 会话详情返回 4 条 user/assistant 消息。
- `latest_report_id` 与增量版本报告一致。

### 浏览器验收

- 侧栏主入口数量：4。
- 四页面主题变量：白 `#f5f7fb`、粉 `#f1a5bd`、棕 `#c98a64`、蓝 `#67a5ff`。
- 运营决策二级入口：营销策略、决策报告、客服 AI。
- 证据审校二级入口：审校结果、关税合规、证据中心。
- 客服抽屉可打开、可关闭，遮罩与顶部栏层级正常。
- 375px 视口无横向溢出。
- 浏览器控制台无错误。

## 后续合并建议

1. 仅推送当前功能分支并发起 Pull Request。
2. PR 重点复核客服增量版本刷新、四页面信息架构和移动端抽屉。
3. 不提交 `.env`、API Key、本地数据库或运行日志。
