# TradePilot 前端实现说明

## 改动目标

TradePilot 当前前端是一套直接连接 FastAPI 的 React + TypeScript + Vite 运营工作台。用户可在一个页面完成商品录入、四 Agent 分析、过程追踪、证据审校、报告查看和报告后续交互。

## 视觉与交互

- 使用团队像素 Logo 作为品牌入口，并保留轻量像素网格与硬边阴影作为识别元素。
- 使用像素白、粉、棕、蓝作为四个 Agent 的固定身份色；深海军蓝作为工作台背景色，保证数据密集界面的层级和可读性。
- 桌面端采用固定导航与双栏工作区，移动端重排为单栏，关键表单控件保持至少 44px 的触控高度。
- 提供键盘焦点、跳转到主内容、表单标签、状态文本与 `prefers-reduced-motion` 支持。
- 设计基线由 UI UX Pro Max 生成并沉淀在 `frontend/design-system/tradepilot/MASTER.md`。

## 功能实现

1. 商品资料：支持名称、描述、卖点、参数、场景、目标用户、目标价格、币种和可选文件。
   商品类别和目标市场提供分组常用选项、中文/英文/缩写搜索，同时保留自由输入能力。
2. 分析任务：创建商品后启动分析，轮询状态并展示整体进度。
3. 四 Agent 看板：展示 ProductMarketAgent、UserInsightAgent、OperationsDecisionAgent、EvidenceAuditAgent 的运行状态、模型、耗时、证据数和调用数。
4. 过程追踪：展示阶段时间线和审校问题，不把 warning 隐藏成成功。
5. 报告输出：拉取结构化报告与 Markdown，并使用禁用原始 HTML 的渲染方式展示；支持下载 Markdown 与浏览器打印/“另存为 PDF”。没有服务端 PDF 导出接口。
6. 报告客服 AI：报告生成后打开独立浮层，通过 CustomerServiceAgent 解释、澄清或创建受证据约束的新版本报告。它不计入分析链的四个 Agent。

## 任务启动可靠性

- Demo 任务使用进程内知识库，不受 Real 模式的 Chroma 或 Embedding 密钥影响。
- Real 任务在入队前检查聊天模型、Embedding 凭证、Git LFS 数据和离线缓存；不满足条件时立即返回明确错误。
- 后台知识库初始化与工作流执行处于同一异常边界，失败状态和错误信息一定写回数据库。
- 服务重启时会恢复已创建但尚未执行的 `pending` 任务，避免永久停留在“等待创建任务”。
- 前端在任务处于 `pending` 或 `running` 时禁用重复提交和模式切换，防止连续创建相同任务；当前实现以 `/status` 和 `/timeline` 轮询进度。后端 SSE 是可供其他客户端使用的补充契约，并非本 UI 的主路径。

## 接口范围

前端调用以下 `/api/v1` 能力：

- 商品创建与文件上传
- 分析任务创建、状态、时间线、Agent 结果与审校结果
- 结构化报告和 Markdown 报告
- 报告历史、版本删除/清空和 CustomerServiceAgent 对话
- 工作流元数据

具体契约仍以 `docs/api-contract.md` 和 `docs/frontend-integration.md` 为准。

## 验证结果

- `npm run lint`：通过
- `npm run build`：通过
- 本地 Demo E2E：四 Agent 均完成，审校为 `pass`，结构化报告与 Markdown 均正常展示
- 响应式检查：桌面和 375px 级移动视口无横向溢出
- 浏览器控制台：未发现运行时错误
