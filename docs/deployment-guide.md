# TradePilot 测试环境传统部署手册

本文只覆盖 Vercel 前端 Preview 与 Railway 后端 staging，不创建正式生产部署，不绑定自定义域名。

## 1. 已确认的仓库结构

| 项目 | 目录 | 技术栈 | 安装 | 本地启动 | 构建/检查 |
| --- | --- | --- | --- | --- | --- |
| 后端 | 仓库根目录 | Python 3.12、FastAPI、Uvicorn、SQLAlchemy/Alembic、SQLite、Chroma | `python -m pip install -r requirements.txt` | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` | `python -m pytest`、`python -m ruff check .` |
| 前端 | `frontend` | React 19、TypeScript 6、Vite 8 | `npm ci` | `npm run dev` | `npm run lint`、`npm run build`，输出 `dist` |

前端通过 `VITE_API_BASE_URL` 访问后端，未设置时使用 `/api/v1`。后端健康检查为 `GET /api/v1/health`，不调用外部模型。

## 2. 部署前边界

- `.env`、`.env.*` 默认被 Git 忽略，只有 `.gitignore` 中明确列出的 example 模板允许跟踪。不要把真实值写进模板、日志、提交或前端的 `VITE_*` 变量。
- `APP_API_KEY` 目前只是配置项，API 路由没有强制校验它。CORS 和 Trusted Host 也不是身份认证。因此测试后端生成公网域名后仍属于公开 API；建议先保持 `DEFAULT_DATA_MODE=demo`，不配置模型密钥，只放非敏感演示数据。
- 两个 Git LFS 数据文件约为 616 MB 与 317 MB。Railway 从 GitHub 构建时是否取到真实 LFS 内容必须在构建日志或容器中验证；不能只凭健康检查认定 Real 模式可用。
- 不要把本次 Preview/staging 提升为 Production，也不要绑定自定义域名。

## 3. Railway 后端 staging 精确配置

1. 新建 Railway Project 和名为 `staging` 的 Environment，从 GitHub 导入本仓库。
2. Service 的 Root Directory 保持仓库根目录（留空或 `/`），不要填 `frontend`。
3. Config as Code 路径使用 `/railway.json`。其中已设置：
   - Builder：`RAILPACK`
   - Start Command：`python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Healthcheck Path：`/api/v1/health`
   - Healthcheck Timeout：`300`
   - Restart Policy：失败时重启，最多 5 次
4. Build Command 留空，让 Railpack 根据 `.python-version`、`pyproject.toml` 和 `requirements.txt` 自动安装。Python 必须为 3.12.x。
5. Replica 数量固定为 `1`。SQLite 与本地 Chroma 不适合多副本并发写入。
6. 在这个 Service 上创建一个 Volume，Mount Path 精确填写 `/data`。Volume 在运行时挂载，不能在构建命令或 pre-deploy 命令中初始化。
7. 将下表变量填入 Railway Variables。不要手工设置 `PORT`，Railway 会注入。
8. 首次部署成功后，在 Settings → Networking 点击 **Generate Domain**，只使用 Railway 提供的测试域名，不添加 Custom Domain。

### Railway 变量

| 名称 | staging 值/规则 | 是否敏感 |
| --- | --- | --- |
| `APP_ENV` | `staging` | 否 |
| `APP_DEBUG` | `false` | 否 |
| `CORS_ALLOWED_ORIGINS` | 首次可留空；Vercel 生成真实 Preview URL 后填完整 origin，多个值用逗号分隔 | 否 |
| `TRUSTED_HOSTS` | `healthcheck.railway.app,*.up.railway.app,*.railway.internal` | 否 |
| `DATABASE_URL` | `sqlite:////data/tradepilot.db` | 否 |
| `CHROMA_DIR` | `/data/chroma` | 否 |
| `CHROMA_PERSIST_DIR` | `/data/chroma` | 否 |
| `UPLOAD_DIR` | `/data/uploads` | 否 |
| `REPORT_DIR` | `/data/reports` | 否 |
| `RAG_MANIFEST_PATH` | `/data/index-manifest.sqlite` | 否 |
| `PEER_CACHE_DIR` | `/data/peer-cache` | 否 |
| `TRADE_TARIFF_DB_PATH` | `/data/tariff-rules.sqlite` | 否 |
| `PEER_METADATA_PATH` | `data/filtered/meta_pet_supplies_prefiltered.jsonl` | 否 |
| `PEER_REVIEWS_PATH` | `data/filtered/pet_supplies_reviews_prefiltered.jsonl` | 否 |
| `PEER_MATCH_CONFIG_PATH` | `config/peer_matching.yaml` | 否 |
| `TRADE_HS_MAPPING_PATH` | `config/trade/hs_mapping.yaml` | 否 |
| `DEFAULT_DATA_MODE` | 首次使用 `demo` | 否 |
| `RAG_USE_CHROMA` | `true` | 否 |
| `RUN_WORKER_COUNT` | `1` | 否 |
| `LOG_LEVEL` | `INFO` | 否 |
| `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`QWEN_API_KEY` | 公网 demo staging 留空；只有增加访问控制后再作为 Railway Secret 配置 | 是 |
| 模型与 RAG 调优变量 | 从 `.env.staging.example` 或 `.env.example` 复制所需项 | 部分敏感 |

`.env.staging.example` 只提供变量名和非秘密示例，不应上传为 Railway 的真实 env 文件。

### 首次后端验证

将实际 Railway 地址记为 `https://<railway-domain>`，逐项验证：

```powershell
Invoke-RestMethod https://<railway-domain>/api/v1/health
Invoke-WebRequest https://<railway-domain>/openapi.json -UseBasicParsing
```

两项都应返回 HTTP 200。还需检查部署日志确认 Alembic 升级成功，且不存在重启循环。Railway 的部署健康检查只在发布切换时执行，不是持续监控。

## 4. Vercel 前端 Preview 精确配置

在后端 Railway 测试域名真实生成且健康检查通过后再导入前端：

| Vercel 字段 | 精确值 |
| --- | --- |
| Repository | 同一 TradePilot 仓库 |
| Root Directory | `frontend` |
| Framework Preset | `Vite` |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Node.js Version | `22.x` |
| Environment Variable | `VITE_API_BASE_URL=https://<railway-domain>/api/v1`，只勾选 Preview |

`frontend/vercel.json` 已包含 SPA fallback 和基础安全响应头。`VITE_*` 会进入浏览器产物，绝对不能放 API Key、数据库地址或其他秘密。

第一次 Vercel Preview 生成后：

1. 复制其真实 origin，例如 `https://<actual-preview>.vercel.app`，不要猜地址。
2. 将这个 origin 填入 Railway 的 `CORS_ALLOWED_ORIGINS`，不带路径、不用 `*`。
3. 重新部署 Railway staging。
4. 打开 Vercel Preview，在浏览器 Network 中确认 `/health` 与 `/workflow` 请求均成功，且响应的 `Access-Control-Allow-Origin` 精确等于当前 Preview origin。
5. 每个新的随机 Preview 地址都需要加入 allowlist；也可以只维护一个明确的测试 Preview 地址。

## 5. 持久化与数据风险

| 数据 | 目标路径 | 风险与处理 |
| --- | --- | --- |
| SQLite 业务状态 | `/data/tradepilot.db` | 必须持久化；保持单副本。Volume 丢失即丢失产品、运行与报告元数据。 |
| Chroma 索引 | `/data/chroma` | 可重建但成本高；持久化，且不要让多个实例同时写。 |
| 上传文件 | `/data/uploads` | 业务输入，必须持久化并备份。 |
| 报告文件 | `/data/reports` | 业务输出，必须持久化并备份。 |
| Peer cache | `/data/peer-cache` | 派生数据，可重建但源文件很大，建议持久化。 |
| RAG manifest | `/data/index-manifest.sqlite` | 派生状态，建议和 Chroma 一起持久化。 |
| Tariff SQLite | `/data/tariff-rules.sqlite` | 派生规则库，建议持久化。 |

Railway Volume 会跨重启和重新部署保留，但删除/Wipe Volume 会清空数据。带 Volume 的 Service 重新部署时可能有短暂停机。测试阶段也应在重要数据写入后创建 Volume backup。

如果确认 Git LFS 文件在运行容器中是完整 JSONL，而不是几行 LFS pointer，才可在运行环境中准备真实数据：

```powershell
python scripts/prepare_peer_data.py --cache-dir /data/peer-cache
python scripts/import_us_hts_tariffs.py --input data/raw/us_hts_2026_rev11.csv --database-output /data/tariff-rules.sqlite --normalized-output /data/us-hts-tariffs.jsonl
```

Volume 在 build/pre-deploy 阶段不可用，因此这些命令只能在已挂载 Volume 的运行环境中执行。未验证 LFS、索引、模型供应商和访问控制前，不要把 `DEFAULT_DATA_MODE` 改为 `real`。

## 6. 回滚与重新部署

- 代码回滚：对本次独立提交执行 `git revert <commit>`，推送 staging 分支后重新部署；不要改写共享分支历史。
- Railway：选择上一个成功 Deployment 重新部署。Volume 数据会保留，但代码回滚不会自动回滚数据库 schema；当前启动只执行 Alembic `upgrade head`，禁止自动降级或删除数据库。
- Vercel：保留 Preview 历史，重新部署上一个成功 commit；不要 Promote to Production。
- 环境变量改变后必须重新部署对应平台。Vercel URL 改变时要同步 Railway CORS allowlist。
- 任何时候都不要通过删除 Volume 来“回滚”；先备份，再单独制定数据恢复方案。

## 7. 安全检查清单

- [ ] `.env` 没有被 Git 跟踪，提交差异中没有真实密钥。
- [ ] Vercel 只有 `VITE_API_BASE_URL`，没有任何服务端 Secret。
- [ ] Railway Secret 只存在平台变量中，不在日志和代码中。
- [ ] `APP_DEBUG=false`、单副本、`/data` Volume 已挂载。
- [ ] `TRUSTED_HOSTS` 包含 `healthcheck.railway.app` 和实际 Railway 域名模式。
- [ ] `CORS_ALLOWED_ORIGINS` 只包含已验证的 Vercel Preview origin。
- [ ] API 无认证这一限制已被接受，或在加入模型 Secret/真实数据前另行实现访问控制。
- [ ] 未绑定自定义域名，未将 Preview/staging 标记为正式生产。

## 8. 当前未生成的地址

在平台账号授权和实际部署完成前，前端 Preview URL 与后端 Railway URL 均为“未生成”。占位符不是可访问地址，也不得作为部署成功证据。
