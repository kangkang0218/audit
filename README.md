# 投标文件三项审查系统

面向生产演进的投标文件审查单仓库。当前已完成生产底座和 Phase A 单份投标 PDF
文本优先审查链路，并已接入单文件上传、处理进度和 Excel 下载前端。
多投标人比对仍未实现。

## 已完成

- 24 个核心领域实体和 Finding-Evidence 多对多证据链。
- 追加式人工复核、敏感字段脱敏/HMAC 数据结构、任务幂等字段。
- Alembic 初始迁移 `91928d8bc3eb`。
- `/api/v1/health/live` 与 `/api/v1/health/ready`。
- Celery Worker 和可重试任务配置骨架。
- PostgreSQL、Redis、MinIO、Nginx、Prometheus、Grafana 开发拓扑。
- PDF 安全清点、历史 Excel 契约校验和固定 7 表 Excel 渲染。
- PDF 文本层、印刷页码、目录/正文关键章节定位。
- 基础事实、人员/证书、劳动合同和社保关联提取。
- 报价、保证金、人员一致性规则及固定单文件审查边界。
- 可选 PaddleOCR、Qwen/DeepSeek Provider 与无配置/调用失败降级。
- 静态前端、PDF 页数接口和纯本地单文件审查下载接口。
- 架构、数据模型、API、安全、部署和 Phase A-E 清单。

## 本地运行

推荐 Python 3.11 或 3.12：

```bash
make PYTHON=python3 install
make PYTHON=python3 test
make PYTHON=python3 api
```

如果机器上有多个 Python，可将 `PYTHON` 指向明确解释器，例如
`make PYTHON=/opt/python3.11/bin/python test`。

打开 `http://localhost:8000/` 使用前端，健康检查地址为
`http://localhost:8000/api/v1/health/live`。异步 Worker另开终端：

```bash
make worker
```

完整开发依赖：

```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8080/api/v1/health/live
```

Docker启动后前端地址为 `http://localhost:8080/`。

## 当前 CLI

```bash
cd backend

# 只输出摘要、哈希、页数和文本覆盖率，不输出 PDF 原文
python -m app.cli.main inspect-pdf "../zzsj619/中兴豫建设管理有限公司(1).pdf"

# 检查历史 Excel：exact / adaptable / incompatible
python -m app.cli.main validate-template "../中兴豫建设管理有限公司投标文件三项审查_提取与判断建议.xlsx"

# 从稳定 review.json 契约生成固定结构 Excel，默认掩码身份证类编号
python -m app.cli.main render-excel ../samples/review.example.json ../outputs/review.xlsx

# 对真实单份 PDF 执行完整 Phase A 审查
python -m app.cli.main review \
  --input "../samples/中和刚大工程顾问有限公司(1)(1).pdf" \
  --output "../outputs/zhgd"

# 完全离线导入既有页面评测结果，重算规则并生成最终 Excel
python -m app.cli.main build-excel-with-evaluation \
  --input "../samples/中和刚大工程顾问有限公司(1)(1).pdf" \
  --evaluation "../outputs/zhgd_page_eval" \
  --evaluation "../outputs/zhgd_page_eval_personnel_retry" \
  --output "../outputs/zhgd_final"

# Phase A.2：纯本地扫描整份 PDF，生成有限候选页和连续范围计划
python -m app.cli.main plan-single-file-review \
  --input "../samples/中和刚大工程顾问有限公司(1)(1).pdf" \
  --output "../outputs/zhgd_candidate_plan"

# 仅读取并汇总已生成的候选计划
python -m app.cli.main inspect-candidate-plan \
  --input "../outputs/zhgd_candidate_plan"
```

`review` 生成 `pages.json`、`toc.json`、`facts.json`、`personnel.json`、
`findings.json`、`review.json`、`audit_log.json`、`llm_calls.jsonl` 和固定
7 Sheet Excel。`samples/` 下的大 PDF 是指向 `zzsj619/` 真实文件的符号链接。

`build-excel-with-evaluation` 不初始化模型 Provider、不调用 OCR 或 HTTP，只读取已生成且
通过 Schema 校验的页面评测 JSON。页面结果作为候选证据合并；与本地文本冲突时不会
自动覆盖，而会写入来源审计、判断建议和风险样式。

`plan-single-file-review` 会扫描全部 PDF 页面的本地文本、标题、关键词、表格/图像和
低文本特征，但不会持久化整页图片，也不会调用模型或 OCR。输出中的视觉与 OCR 标记
只是后续处理建议；目录页只作为导航线索，不视为材料内容页。

兼容策略以 `single-file-legacy-v1` 为版本：固定 7 个语义工作表和规范列头；历史文件
的工作表/列头差异通过别名适配器识别，新产物统一输出规范格式。原样复制历史 Excel
不是兼容目标，因为部分样例含未脱敏身份证号且列结构已发生漂移。

## 迁移

```bash
cd backend
alembic upgrade head
alembic downgrade -1
```

生产发布不自动执行 downgrade，详见 [部署说明](docs/deployment.md)。

## 文档

- [系统架构](docs/architecture.md)
- [数据模型](docs/data-model.md)
- [API 契约](docs/api.md)
- [安全设计](docs/security.md)
- [部署说明](docs/deployment.md)
- [Phase A-E 清单](docs/phase-checklist.md)

## 可选 OCR 与模型

默认 `BID_REVIEW_ENABLE_OCR=false`、`BID_REVIEW_ENABLE_LLM=false`。启用 OCR 时需安装
`.[ocr]` 及匹配的 PaddlePaddle 运行时；初始化或调用失败会写入审计日志并回退文本层。
模型 Endpoint、Key 和模型名均从 `BID_REVIEW_QWEN_*` 或
`BID_REVIEW_DEEPSEEK_*` 环境变量读取。模型只处理关键候选页，不参与规则判断。

## 当前限制

- 扫描页的图片文字在未启用 OCR/视觉模型时需人工复核。
- 表格提取面向当前样例版式，新增投标模板需要增加黄金样本回归。
- 当前只有中和刚大样例完成字段级自动回归；其他样例仍需逐项人工校验。
- readiness 目前只校验应用配置，真实 PostgreSQL/Redis 探针留到 Phase B。
- Compose 是开发/试点骨架；认证、病毒扫描、TLS、私有桶初始化、指标和 Trace 尚未接入。
- 样例 Excel 中存在明文敏感编号，生产导入前必须执行脱敏和授权审查。
