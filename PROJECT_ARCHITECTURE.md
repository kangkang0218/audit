# 投标文件三项审查系统 — 项目架构文档

> 本文档从全局视角描述项目的技术栈、目录结构、核心架构、业务处理流程、数据模型、
> 基础设施以及演进规划，供新成员快速上手和团队协作参考。

---

## 一、项目概述

本系统面向中国工程建设领域的招投标场景，对投标文件（PDF，通常 100+ 页）进行
自动化审查。系统完成以下核心工作：

1. **解析** — 从投标 PDF 中提取文本、图片、目录结构和页面元数据。
2. **抽取** — 通过正则、OCR 和可选的大语言模型（LLM），提取报价、保证金、人员
   证书等 25+ 结构化事实字段。
3. **校验** — 使用确定性 Python 规则引擎对内部一致性进行验证（报价一致性、保证金
   一致性、人员证书冲突等）。
4. **输出** — 生成固定 7 表结构的 Excel 审查报告，包含发现、证据、风险等级和
   人工复核建议。

系统 **只输出风险线索和证据不足建议**，不作违法、串通、虚假材料、废标或中标无效
等法律定性。

**当前阶段：Phase A（单文件 CLI 管线）已基本完成**，Phase B 已提供单文件上传和
Excel 下载 API，并接入轻量静态前端。完整项目管理、复核队列等 Phase C 功能尚未开始。

---

## 二、技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **语言** | Python 3.11+ | 主力开发语言 |
| **Web 框架** | FastAPI + Uvicorn | 异步 API 服务 |
| **ORM** | SQLAlchemy 2.0 | 声明式模型，支持异步 |
| **数据库** | PostgreSQL 16 | 主存储，psycopg 驱动 |
| **数据库迁移** | Alembic | 版本化 Schema 管理 |
| **缓存/消息队列** | Redis 7.4 | Celery Broker + 缓存 |
| **异步任务** | Celery 5.4+ | 分布式任务队列，支持重试和幂等 |
| **对象存储** | MinIO | 兼容 S3 的文件存储 |
| **PDF 解析** | PyMuPDF (fitz) + pdfplumber | 文本提取、页面渲染 |
| **OCR** | PaddleOCR 3（可选） | 低文本覆盖页的光学字符识别 |
| **LLM** | Qwen / DeepSeek（可选） | OpenAI 兼容 API，视觉+文本模型 |
| **Excel 生成** | openpyxl | 固定模板渲染 |
| **配置管理** | Pydantic Settings + python-dotenv | 环境变量类型安全 |
| **结构化日志** | structlog | JSON 格式日志 |
| **HTTP 客户端** | httpx | 异步 HTTP 请求 |
| **反向代理** | Nginx 1.27 | 限流、请求转发、大文件上传 |
| **监控** | Prometheus 3.3 + Grafana 11.6 | 指标采集与可视化 |
| **容器化** | Docker + Docker Compose | 开发环境一键启动 |
| **构建系统** | hatchling (pyproject.toml) | Python 包构建 |
| **代码质量** | Ruff + mypy + pytest | Lint、类型检查、测试 |
| **轻量前端** | HTML5 / CSS / JavaScript | 单文件上传、进度展示、Excel 下载 |
| **完整前端（规划中）** | Vue 3 / TypeScript / Vite / PDF.js | Phase C 计划 |

---

## 三、目录结构

```
bid-review/
├── Makefile                      # 构建/测试/运行快捷命令
├── README.md                     # 项目概览与快速上手
├── docker-compose.yml            # 开发环境 7 服务拓扑
├── .env.example                  # 环境变量模板
├── frontend/                     # 当前轻量静态前端（由当前 FastAPI 托管）
│
├── backend/                      # Python 后端
│   ├── pyproject.toml            # 包配置、依赖声明、工具配置
│   ├── Dockerfile                # 后端容器镜像
│   ├── alembic.ini               # Alembic 配置
│   ├── alembic/                  # 数据库迁移脚本
│   │   └── versions/             # 迁移版本文件
│   ├── app/                      # 应用源代码
│   │   ├── main.py               # FastAPI 应用入口、中间件
│   │   ├── api/                  # API 路由层
│   │   │   ├── router.py         # 路由聚合
│   │   │   ├── v1/health.py      # 健康检查端点
│   │   │   └── v1/review.py      # PDF页数、单文件审查与Excel下载
│   │   ├── core/                 # 核心配置
│   │   │   ├── config.py         # Pydantic Settings（BID_REVIEW_ 前缀）
│   │   │   └── privacy.py        # 敏感数据脱敏（身份证、手机号、银行卡）
│   │   ├── db/                   # 数据库基础
│   │   │   ├── base.py           # SQLAlchemy DeclarativeBase
│   │   │   └── session.py        # 会话工厂与引擎配置
│   │   ├── models/               # 数据模型
│   │   │   └── entities.py       # 24 个领域实体
│   │   ├── schemas/              # Pydantic 数据契约
│   │   ├── parsers/              # PDF 解析器
│   │   │   ├── pdf_parser.py     # PyMuPDF 文本/图片/标题提取
│   │   │   ├── toc_parser.py     # 目录定位与页码映射
│   │   │   ├── text_locator.py   # 正则文本定位与证据生成
│   │   │   ├── ocr_parser.py     # 可选 PaddleOCR
│   │   │   └── page_renderer.py  # PDF 页面渲染为 PNG
│   │   ├── extractors/           # 事实抽取器
│   │   │   ├── basic_facts.py    # 正则抽取 25+ 基础字段
│   │   │   └── personnel.py      # 人员/证书/社保抽取
│   │   ├── llm/                  # LLM 集成
│   │   │   ├── base.py           # 抽象 Provider 接口
│   │   │   ├── openai_compatible.py  # OpenAI 兼容客户端
│   │   │   ├── qwen_provider.py  # 通义千问（视觉+文本）
│   │   │   ├── deepseek_provider.py  # DeepSeek（文本）
│   │   │   ├── router.py         # Provider 路由 + JSON 修复
│   │   │   ├── mock.py           # 测试用 Mock Provider
│   │   │   ├── config_health.py  # 配置健康检查
│   │   │   ├── verification.py   # 连通性验证
│   │   │   └── prompts/          # 版本化提示词模板
│   │   ├── validators/           # 规则引擎
│   │   │   └── single_file.py    # 单文件一致性校验规则
│   │   ├── services/             # 业务编排层
│   │   │   ├── single_file_review.py     # 单文件审查主编排
│   │   │   ├── page_evaluation.py        # 页面级 LLM 评估
│   │   │   └── personnel_table_evaluation.py  # 人员表格 LLM 评估
│   │   ├── excel/                # Excel 输出
│   │   │   ├── contract.py       # 固定 7 表模板契约定义
│   │   │   └── renderer.py       # openpyxl 渲染器
│   │   ├── tasks/                # Celery 异步任务
│   │   │   ├── celery_app.py     # Celery 配置
│   │   │   └── pipeline.py       # 异步处理管线骨架
│   │   ├── audit/                # 审计
│   │   │   └── file_log.py       # 文件式追加审计日志
│   │   └── cli/                  # 命令行接口
│   │       └── main.py           # 9 个子命令
│   ├── tests/                    # 测试（21 个测试文件）
│   │   ├── conftest.py           # 公共 fixtures
│   │   └── test_*.py             # 各模块测试
│   └── requirements/             # 锁定依赖文件
│
├── docs/                         # 项目文档（中文）
│   ├── architecture.md           # 系统架构
│   ├── data-model.md             # 数据模型
│   ├── api.md                    # API 契约
│   ├── security.md               # 安全设计
│   ├── deployment.md             # 部署说明
│   ├── phase-checklist.md        # Phase A-E 执行清单
│   └── page-evaluation.md        # 页面评估文档
│
├── infra/                        # 基础设施配置
│   ├── nginx/nginx.conf          # Nginx 反向代理配置
│   ├── prometheus/prometheus.yml # Prometheus 采集配置
│   └── grafana/                  # Grafana 数据源预配置
│
├── samples/                      # 样例数据（符号链接 + review.json）
├── outputs/                      # 生成的审查输出（Excel、JSON）
├── zzsj619/                      # 真实投标文件 PDF（~25 个大文件）
├── 之前的结果/                    # 历史人工审查 Excel（兼容性基线）
└── scripts/                      # 脚本目录（预留）
```

---

## 四、核心架构

### 4.1 逻辑分层

```text
┌─────────────────────────────────────────────────────────┐
│                Vue 3 / PDF.js（Phase C 规划）             │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                    Nginx 反向代理                         │
│           限流 10r/s · 500MB 上传 · X-Request-ID         │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI API 层                          │
│       认证 · RBAC · 分页 · 统一错误 · 幂等键 · 审计入口    │
└───┬──────────┬──────────┬───────────────────────────────┘
    │          │          │
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────────────────────────────────┐
│PostgreSQL│ │ MinIO  │ │  Redis ──► Celery Worker           │
│  16     │ │  S3    │ │          │                          │
└────────┘ └────────┘ │          ├─► PDF/OCR 解析器          │
                       │          ├─► LLM Provider 路由       │
                       │          ├─► 事实/证据标准化          │
                       │          ├─► Python 规则引擎          │
                       │          └─► Excel/报告渲染           │
                       └────────────────────────────────────┘
```

各层职责：

- **API 层** — 接收请求、认证授权、参数校验、幂等控制、统一错误响应。
- **任务层** — 持久化 `ProcessingRun/ProcessingTask` 后投递 Celery 任务；支持重试和断点恢复。
- **解析层** — PyMuPDF 优先提取文本层，低文本覆盖页自动进入 OCR 通道。
- **模型层** — 通过统一 Provider 接口接入 Qwen/DeepSeek；输出必须通过 Pydantic Schema 校验。
- **领域层** — 事实与证据标准化存储，Python 规则引擎产生 Finding。
- **复核层** — 人工决定以追加方式写入 `ReviewDecision`，不修改模型原始 Finding。
- **交付层** — 版本化 Excel 模板和审计报告写入私有对象存储。

### 4.2 处理管线（单文件审查）

`services/single_file_review.py` 中的 `run_review()` 是核心编排函数，执行以下步骤：

```text
PDF 输入
  │
  ├─ 1. PyMuPDF 解析 ─── 文本、图片、标题、印刷页码（每页）
  │
  ├─ 2. 目录定位 ──────── 扫描前 20 页，目录关键词匹配，页码偏移计算
  │
  ├─ 3. 可选 OCR ──────── 低文本覆盖 + 有图片的页面 → PaddleOCR
  │
  ├─ 4. 基础事实抽取 ──── 正则匹配 25+ 字段（项目名称、投标人、报价、保证金等）
  │
  ├─ 5. 可选 LLM ──────── 候选关键页 → 视觉模型抽取 → JSON 修复 → Pydantic 校验
  │
  ├─ 6. 人员抽取 ──────── 项目管理机构组成表 + 简历页 → 姓名/角色/证书/社保
  │
  ├─ 7. 规则引擎 ──────── 报价一致性 · 保证金一致性 · 人员证书冲突 · 边界声明
  │
  ├─ 8. 构建审查工作簿 ── 7 个语义分区（概览、事实、不可用原因、发现、人员、依据、所需材料）
  │
  ├─ 9. 渲染 Excel ────── openpyxl 输出固定格式，敏感数据强制脱敏
  │
  └─ 10. 写入审计产物 ─── pages.json, toc.json, facts.json, personnel.json,
                           findings.json, review.json, audit_log.json, llm_calls.jsonl
```

### 4.3 降级策略

系统在可选组件不可用时自动降级，保证管线不因单点失败而中断：

```text
视觉模型 → OCR → 文本模型 → 人工复核
```

任何步骤失败都会：
- 记录独立的审计日志和错误码
- 可用的既有事实仍进入规则引擎
- 失败页面标记为"当前材料不足/需人工复核"
- **不会**导致整个 Run 失败

### 4.4 证据链

系统核心设计原则是 **每个结论可溯源**：

```text
ExtractedFact ──► Evidence ◄── FindingEvidence ──► Finding ──► ReviewDecision
```

- `Evidence` 保存：文件路径、PDF 页码、印刷页码、坐标、脱敏文本摘录、截图对象路径、
  提取方法和置信度。
- `FindingEvidence` 是多对多关联表，一个 Finding 可引用多条 Evidence。
- `ReviewDecision` 是追加式人工复核，不修改原始 Finding。
- 报告中每个结论必须能回溯到 Finding → 规则版本 → Evidence。

---

## 五、数据模型

### 5.1 实体总览（24 个领域实体）

所有实体共享 `RecordMixin`：UUID 主键、`created_at`、`updated_at`、`created_source`、
`record_version`。

| 分类 | 实体 | 说明 |
|------|------|------|
| **身份与权限** | `User`, `Role`, `user_roles` (M2M) | 用户和多对多角色 |
| **项目与投标人** | `Project`, `Bidder` | 项目管理和投标人信息 |
| **文档** | `SourceDocument`, `DocumentVersion`, `DocumentPage` | 源文档、版本和页面 |
| **处理** | `ProcessingRun`, `ProcessingTask` | 处理运行和子任务 |
| **事实与证据** | `ExtractedFact`, `Evidence`, `FindingEvidence` (M2M) | 抽取事实和关联证据 |
| **人员** | `PersonnelRecord`, `PersonnelAlias`, `CredentialRecord`, `SocialSecurityReference` | 人员记录、别名、证书和社保 |
| **发现与复核** | `Finding`, `ReviewDecision`, `CrossDocumentMatch` | 审查发现和人工复核 |
| **元数据** | `PromptVersion`, `RuleVersion`, `ModelCallLog`, `GeneratedReport`, `AuditLog` | 版本化元数据和审计 |

### 5.2 隐私设计

敏感数据保护是一等公民：

- **脱敏输出** — `privacy.py` 对身份证号（18 位）、银行卡（16-24 位）、手机号进行
  正则匹配和局部掩码。所有 Excel 输出强制脱敏。
- **HMAC 比对** — 数据库敏感字段使用双列模式：`*_masked` 用于显示，`*_hmac`
  （LargeBinary(32)）用于等值比对，不存储明文。
- **API Key 保护** — 错误消息中自动过滤 API Key。
- **外部处理确认** — LLM 处理需显式 `--confirm-external-processing` 标志。

---

## 六、Phase A 使用指南（CLI 管线：PDF → Excel）

当前 Phase A 的主要交互方式是命令行。所有 CLI 命令通过 `backend/app/cli/main.py` 入口
执行，工作目录需切换到 `backend/`。

### 6.1 环境准备

```bash
# 1. 安装 Python 依赖（推荐 Python 3.11 或 3.12）
make PYTHON=python3 install
# 或手动安装：
cd backend && pip install -e ".[dev]"

# 2. 复制并配置环境变量（可选功能默认关闭）
cp .env.example .env
# 编辑 .env 按需开启 OCR / LLM：
#   BID_REVIEW_ENABLE_OCR=true    （需额外安装 PaddleOCR + PaddlePaddle）
#   BID_REVIEW_ENABLE_LLM=true    （需配置 Qwen 或 DeepSeek API Key）

# 3. 验证安装
make PYTHON=python3 test
```

### 6.2 核心命令：`review`（端到端单文件审查）

这是 Phase A 最核心的命令，输入一个投标 PDF，输出完整的审查 Excel 报告和所有中间
JSON 产物。

```bash
cd backend

python -m app.cli.main review \
  --input "path/to/投标公司名.pdf" \
  --output "path/to/output_dir"
```

**参数说明：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--input` | 是 | 输入的投标 PDF 文件路径 |
| `--output` | 是 | 输出目录路径（自动创建），所有产物写入此目录 |

**执行流程：**

```text
输入 PDF
  │
  ├─ 1. PyMuPDF 解析     → pages.json       每页文本、图片数、标题、印刷页码
  ├─ 2. 目录定位          → toc.json         章节名 → PDF 页码映射
  ├─ 3. 可选 OCR          → (增强低文本页)    需 BID_REVIEW_ENABLE_OCR=true
  ├─ 4. 正则事实抽取      → facts.json       25+ 字段（报价、保证金、投标人等）
  ├─ 5. 可选 LLM 视觉     → llm_calls.jsonl  需 BID_REVIEW_ENABLE_LLM=true
  ├─ 6. 人员/证书抽取     → personnel.json   项目管理机构、证书、社保
  ├─ 7. 规则引擎校验      → findings.json    报价/保证金一致性、人员冲突
  ├─ 8. 构建审查工作簿    → review.json      7 个语义分区汇总
  ├─ 9. 渲染 Excel        → {投标人}投标文件三项审查_提取与判断建议.xlsx
  └─ 10. 写入审计日志     → audit_log.json   全流程追加式审计记录
```

**输出文件清单（写入 `--output` 目录）：**

| 文件 | 说明 |
|------|------|
| `pages.json` | 每页解析结果：文本内容、图片数量、检测到的标题关键词、印刷页码 |
| `toc.json` | 目录定位结果：章节名称、PDF 页码、印刷页码映射 |
| `facts.json` | 基础事实抽取：25+ 字段及其证据（页码、摘录、置信度、提取方法） |
| `personnel.json` | 人员记录：姓名、角色、职称、证书、社保关联、劳动合同 |
| `findings.json` | 规则引擎发现：报价一致性、保证金一致性、人员证书冲突、边界声明 |
| `review.json` | 完整审查工作簿：概览、事实、不可用原因、发现、人员、依据、所需材料 |
| `audit_log.json` | 追加式审计日志：每个处理步骤的时间戳、状态和元数据 |
| `llm_calls.jsonl` | LLM 调用记录（仅启用 LLM 时有内容） |
| `{投标人}投标文件三项审查_提取与判断建议.xlsx` | **最终交付物**：固定 7 表 Excel |

**实际示例：**

```bash
# 使用样例 PDF 执行完整审查
cd backend
python -m app.cli.main review \
  --input "../samples/中和刚大工程顾问有限公司(1)(1).pdf" \
  --output "../outputs/zhgd"

# 使用真实投标文件
python -m app.cli.main review \
  --input "../zzsj619/中兴豫建设管理有限公司(1).pdf" \
  --output "../outputs/zxy"
```

**Excel 输出的 7 个工作表：**

| Sheet | 内容 |
|-------|------|
| 概览 | 源文件、投标人、基础事实数量、人员数量、规则发现数量 |
| 事实 | 每项提取字段的值、证据页码、原文摘录、置信度 |
| 不可用原因 | 无法提取的字段及原因、需补充材料清单 |
| 发现 | 规则引擎判断：一致性结论、风险等级、补充材料清单 |
| 人员 | 人员姓名、角色、职称、证书、社保状态、证据页码 |
| 依据 | 审查规则依据和适用条款 |
| 所需材料 | 缺失材料清单、优先级和获取方式建议 |

### 6.3 辅助命令

**PDF 清点**（仅输出元数据摘要，不输出 PDF 原文内容）：

```bash
python -m app.cli.main inspect-pdf "../zzsj619/中兴豫建设管理有限公司(1).pdf"
# 输出：SHA-256、页数、文本覆盖率、低文本页数量、元数据键
# 可选 --output 将结果写入文件
```

**历史 Excel 兼容性校验**（检查旧 Excel 是否与当前模板兼容）：

```bash
python -m app.cli.main validate-template "../之前的结果/某公司投标文件三项审查_提取与判断建议.xlsx"
# 输出：exact / adaptable / incompatible
```

**从 JSON 重新渲染 Excel**（不重新跑管线，仅从已有 review.json 生成 Excel）：

```bash
python -m app.cli.main render-excel ../outputs/zhgd/review.json ../outputs/zhgd/review.xlsx
```

### 6.4 LLM 相关命令（可选）

需先在 `.env` 中配置 `BID_REVIEW_ENABLE_LLM=true` 及对应的 API Key。

```bash
# 检查 LLM 配置健康状态（脱敏输出）
python -m app.cli.main check-llm-config

# 测试文本模型连通性
python -m app.cli.main verify-llm --provider qwen

# 测试视觉模型连通性（使用合成 PNG）
python -m app.cli.main verify-vision --provider qwen

# 对指定 PDF 页面执行 LLM 评估（需显式确认外部处理授权）
python -m app.cli.main evaluate-pages \
  --input "../samples/中和刚大工程顾问有限公司(1)(1).pdf" \
  --pages "5,6,12" \
  --output "../outputs/eval" \
  --provider qwen \
  --confirm-external-processing

# 检查页面评估结果（不调用模型）
python -m app.cli.main inspect-page-evaluation --input "../outputs/eval"
```

---

## 七、API 端点（当前状态）

目前仅实现 2 个健康检查端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/health/live` | 存活探针，始终返回 200 |
| `GET` | `/api/v1/health/ready` | 就绪探针，校验应用配置 |

Phase B 计划实现：项目 CRUD、文档上传、审查运行、发现查询、人工复核、报告下载、
审计日志等完整 REST API，含 RBAC、幂等键和分页响应。

---

## 八、基础设施与部署

### 8.1 Docker Compose 开发拓扑（7 个服务）

```yaml
services:
  postgres    # PostgreSQL 16-alpine（带健康检查）
  redis       # Redis 7.4-alpine（AOF 持久化）
  minio       # MinIO 对象存储（控制台 :9001）
  backend     # FastAPI（执行 Alembic 迁移后启动 Uvicorn :8000）
  worker      # Celery Worker
  nginx       # Nginx 1.27 反向代理（:8080）
  prometheus  # Prometheus v3.3.0
  grafana     # Grafana 11.6.1（:3000，预配置 Prometheus 数据源）
```

### 8.2 环境变量

所有配置使用 `BID_REVIEW_` 前缀，通过 Pydantic Settings 类型安全加载：

- 基础设施：`POSTGRES_PASSWORD`, `MINIO_ROOT_USER/PASSWORD`, `HTTP_PORT`
- 功能开关：`BID_REVIEW_ENABLE_OCR`（默认 false）, `BID_REVIEW_ENABLE_LLM`（默认 false）
- LLM 配置：`BID_REVIEW_LLM_PROVIDER`（qwen/deepseek）、API Keys、Base URLs、模型名
- 人员表格调优：超时、重试、DPI、最大图片尺寸、JPEG 质量等

### 8.3 Nginx 配置

- IP 限流：10r/s，突发 30
- 客户端请求体限制：500MB
- X-Request-ID 透传
- 反向代理到 FastAPI 后端

---

## 九、测试

使用 pytest 框架，共 21 个测试文件，覆盖：

- API 健康端点和 X-Request-ID 头
- PDF 解析、目录定位、文本提取
- 基础事实抽取和人员抽取
- 报价/保证金/人员一致性规则
- Excel 模板校验和渲染输出
- LLM 配置、路由、集成和连通性验证
- CLI 命令和 Celery 任务骨架
- 全链路端到端测试（含敏感数据泄漏检测）

测试使用 SQLite 内存数据库隔离，真实 PDF 样例作为 fixture。

```bash
make PYTHON=python3 test     # 运行全部测试
```

---

## 十、演进规划

项目按 5 个阶段渐进交付：

```text
Phase A ──► Phase B ──► Phase C ──► Phase D ──► Phase E
  CLI        Web API     完整前端     跨投标人      生产加固
 (近完成)   (单文件可用) (轻量版可用)  (未开始)      (未开始)
```

| 阶段 | 核心目标 | 关键交付物 |
|------|---------|-----------|
| **Phase A** | 单文件 CLI 管线 | PDF 解析、事实抽取、规则引擎、Excel 输出 |
| **Phase B** | Web API + 异步处理 | 上传 API、PostgreSQL 持久化、Celery 异步审查 |
| **Phase C** | Vue 3 前端 | 项目管理、PDF 定位高亮、复核队列、报告下载 |
| **Phase D** | 多投标人比较 | 项目全量材料比对、跨投标人交叉分析 |
| **Phase E** | 生产加固 | TLS、认证、病毒扫描、CI/CD、监控、灾备、黄金样本回归 |

---

## 十一、快速上手

### 本地开发（纯 Python）

```bash
# 安装依赖
make PYTHON=python3 install

# 运行测试
make PYTHON=python3 test

# 启动 API 服务
make PYTHON=python3 api

# 启动 Celery Worker
make worker

# 执行完整单文件审查
cd backend
python -m app.cli.main review \
  --input "../samples/中和刚大工程顾问有限公司(1)(1).pdf" \
  --output "../outputs/zhgd"
```

### Docker Compose 完整环境

```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8080/api/v1/health/live
```

---

## 十二、相关文档

| 文档 | 路径 | 内容 |
|------|------|------|
| 系统架构 | `docs/architecture.md` | 逻辑分层与处理链 |
| 数据模型 | `docs/data-model.md` | 24 个实体详细说明 |
| API 契约 | `docs/api.md` | 当前和规划中的 API 定义 |
| 安全设计 | `docs/security.md` | 数据分级、认证、基础设施安全 |
| 部署说明 | `docs/deployment.md` | Docker Compose 拓扑与运维 |
| Phase 清单 | `docs/phase-checklist.md` | A-E 各阶段详细执行清单 |
| 页面评估 | `docs/page-evaluation.md` | Phase A.1 受控页面评估 |


cd D:\work\bid-review
docker compose ps

docker compose exec backend python -m app.cli.main review \
  --input "/app/samples/中和刚大工程顾问有限公司(1)(1).pdf" \
  --output "/app/outputs/zhgd"
