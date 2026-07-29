# TradePilot 前端

TradePilot 前端是基于 React、TypeScript 和 Vite 的多智能体跨境商品运营工作台。界面使用团队像素 Logo，并用像素白、粉、棕、蓝区分四个 Agent。

## 本地启动

先启动仓库根目录的 FastAPI 服务（默认端口 `8000`），再在本目录执行：

```powershell
npm ci
npm run dev
```

开发服务器默认运行在 `http://127.0.0.1:5173`，并通过 Vite 代理访问 `/api/v1`。如需连接其他后端地址，可复制 `.env.example` 并设置 `VITE_API_BASE_URL`。

## 质量检查

```powershell
npm run lint
npm run build
```

构建产物位于 `frontend/dist`，该目录不会提交到 Git。

## 已接入的工作流

- 创建商品并选择 Demo / Real 数据模式
- 搜索或选择常见商品类别与目标市场，也可以提交自定义内容
- 上传可选的商品图片或文档
- 启动四 Agent 分析并轮询运行状态（后端另提供可重放 SSE，当前 UI 不消费它）
- 展示阶段时间线、Agent 输出摘要、模型调用和证据数量
- 展示审校状态、问题清单、结构化报告和报告历史
- 安全渲染最终 Markdown 报告，并支持下载 Markdown、浏览器打印/另存为 PDF
- 在报告生成后通过独立 CustomerServiceAgent 浮层进行解释和受证据约束的改版；它不属于核心四 Agent

当前 staging 部署在 [Vercel](https://tradepilot-staging-hll-lbld.vercel.app/)，构建时连接 Railway API。

设计决策与 Token 见 `design-system/tradepilot/MASTER.md`。
