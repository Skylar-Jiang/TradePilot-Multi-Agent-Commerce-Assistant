# 生鲜批发采购区域供应源竞品动态追踪与智能对标分析系统

本项目基于现有 Skill + Agent + RAG + FastAPI + 报告生成架构，研究对象统一为生鲜批发采购场景下的区域供应源竞品分析。系统面向生鲜批发商、采购商和供应链人员，围绕黄瓜、番茄、鸡蛋、猪肉等具体生鲜品类，追踪不同产区、批发市场和供应渠道提供的同类商品动态，例如山东寿光黄瓜、河北黄瓜、辽宁某批发市场黄瓜。

在本项目中，代码和接口里的 `competitor` 字段暂时保留，含义统一解释为“区域供应源竞品”，不是传统品牌、公司或电商平台。

## 为什么选择生鲜批发采购

- 生鲜批发价格每天变化明显，适合验证价格监控、价差识别与时序分析。
- 黄瓜、番茄、鸡蛋、猪肉等高频采购品类，对批发商和供应链人员具有直接决策价值。
- 区域供应源之间的竞争集中在批发价、到货价、供应稳定性、质量等级和采购窗口，适合验证多 Agent 分析。
- 系统可优先使用区域官方数据、批发市场行情、监管公告、行业资讯、天气物流信息和手工 CSV 样例，不绕过登录、验证码和反爬。

## 数据源

默认配置文件：

```text
config/sources.yaml
```

数据源类型：

- 政府/行业价格公开页面：全国农产品批发市场价格信息、商务部食用农产品价格信息。
- 区域/市场行情手工 CSV：产区报价、批发市场报价、到货价、成交价和异常价差。
- 监管与质量风险手工 CSV：抽检不合格、食品安全通报、质量等级、腐损率和计量争议。
- 行业资讯手工 CSV：新产季上市、新品种、新产区、新规格、新批次供应、天气物流影响。

无法稳定公开抓取的来源默认采用 `manual_csv` 手工导入公开样例，不写绕过登录、验证码、反爬、App 抓包的代码。后续若接入真实市场行情或监管数据，应通过公开网页、授权 API 或规范化 CSV 接入。

## 快速运行

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Swagger：

```text
http://127.0.0.1:8000/docs
```

默认 LLM Provider 使用 OpenAI-compatible 协议。`.env` 可以直接配置 DeepSeek 官方兼容网关：

```text
OPENAI_API_KEY=<你的 DeepSeek Key>
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL_FAST=deepseek-v4-flash
MODEL_ANALYSIS=deepseek-v4-pro
MODEL_REPORT=deepseek-v4-pro
```

这三个模型变量不要合并：`fast` 用于轻量抓取/清洗/分类，`analysis` 用于结构化竞品分析，`report` 用于报告生成。可以按 DeepSeek 账号实际可用模型分别配置。

RAG 默认使用 Hugging Face `BAAI/bge-m3` + Chroma。首次真实重建向量库时会下载模型；如果网络不稳定，可以在 `.env` 中保留 `HF_ENDPOINT=https://hf-mirror.com` 或改成可用镜像。

如果本地曾经下载中断，可能出现 `BAAI/bge-m3 does not appear to have a file named pytorch_model.bin or model.safetensors`。可先补全 embedding 模型缓存：

```powershell
$env:HF_ENDPOINT="https://hf-mirror.com"
.\venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-m3', resume_download=True)"
```

## 推荐演示顺序

1. `GET /sources`：查看生鲜批发采购数据源。
2. `POST /ingest/csv`：导入任一手工 CSV，例如 `data/raw/shouguang_cucumber_manual.csv`。
3. `POST /rag/rebuild`：重建 Chroma 生鲜批发采购知识库。
4. `GET /rag/search`：查询 `山东寿光黄瓜 河北黄瓜 批发价 到货价 价差 风险`。
5. `GET /skills`：查看 Skill 列表。
6. `POST /analyze/multi-agent`：运行区域供应源多 Agent 分析。
7. `POST /report/generate`：生成生鲜批发采购对标报告。
8. `GET /reports`：查看报告列表。
9. `GET /logs/skill-trace`：查看 Skill 调用记录。

更完整的阶段边界、验收接口和剩余风险见：

```text
docs/任务边界与验收总说明.md
docs/接口说明.md
```

`/analyze/multi-agent` 示例：

```json
{
  "competitor": "山东寿光黄瓜",
  "query": "分析山东寿光黄瓜相对河北黄瓜和辽宁批发市场黄瓜的批发价波动、异常价差、新批次供应和质量风险",
  "dimensions": ["price", "product", "sentiment", "trend"],
  "report_type": "weekly",
  "provider": "mock",
  "date_range": {
    "start": "2026-07-01",
    "end": "2026-07-06"
  }
}
```

## 架构说明

原有通用架构保持不变，只替换业务场景：

```text
区域官方数据/批发市场行情/监管公告/手工 CSV
  -> 数据清洗与分块
  -> Chroma RAG 知识库
  -> 价格 / 新品 / 舆情 / 趋势 Skill
  -> orchestrator_skill 多 Agent 汇总
  -> 生鲜批发采购对标报告生成
  -> FastAPI + Swagger 演示
```

默认 `provider=mock`，不依赖真实模型 Key；如果切换 `provider=openai` 或调用 `/analyze`，系统会使用 `.env` 中的 OpenAI-compatible 配置。
