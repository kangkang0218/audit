# 投标文件三项审查系统

MinerU OCR + DeepSeek LLM 驱动的投标文件智能审查系统，支持纯文本/半扫描/纯扫描 PDF 自动分类与全量事实提取。

## 核心管线

```
PDF → 判别器(TEXT/MIXED/SCANNED) → MinerU OCR(hybrid-engine/3x3090) → Markdown
  → 按页分片 → DeepSeek V4 Pro 并行提取 → 事实归并 → 一致性校验 → 7表 Excel
```

| 阶段 | 引擎 | 说明 |
|------|------|------|
| 判别 | PyMuPDF | <0.5s 文本覆盖率检测，三分类路由 |
| 纯文本 PDF | PyMuPDF 直读 | 跳过 OCR，直接生成 Markdown |
| 扫描 PDF | MinerU hybrid-engine | VLM + 传统 OCR 混合，GPU 0/1/2 并行 |
| 事实提取 | DeepSeek V4 Pro | 按页分片 → N 个 Agent 并行 → 归并去重 |
| 一致性 | DeepSeek + 规则 | 报价/保证金/人员交叉验证 |
| 输出 | openpyxl | 固定 7 表 Excel，敏感数据脱敏 |

## 快速开始

```bash
# 1. 配置 API Key
echo "BID_REVIEW_DEEPSEEK_API_KEY=sk-xxx" >> .env

# 2. 构建 MinerU 镜像（首次 ~30min）
cd mineru && docker build -t mineru:latest .

# 3. 启动全部服务
docker compose up -d

# 4. 访问前端
open http://localhost:58080
```

## 大文件上传

前端自动检测文件大小，≥50MB 自动切片上传（30MB/片，CF 隧道兼容）：

```
前端 File.slice(30MB) → 逐片 POST /upload/init → /chunks/{n} → /complete
  → POST /upload-review/start → 轮询 /status → /result → 下载 Excel
```

切片上传支持断点续传、MD5 校验、冲突检测。

## 异步审查 + 实时进度

审查 API 只接受极短 HTTP 请求，后端异步处理，前端 500ms 轮询进度：

```
POST /upload-review/start  → {runId}        (50ms)
GET  /upload-review/{id}/status → {stage,progress,elapsed}  (每500ms轮询)
GET  /upload-review/{id}/result → Excel      (完成后下载)
```

## API 端点

| 端点 | 说明 |
|------|------|
| `POST /api/v1/upload/init` | 初始化切片上传 |
| `POST /api/v1/upload/{id}/chunks/{n}` | 上传第 n 片 |
| `POST /api/v1/upload/{id}/complete` | 合并分片，MD5 校验 |
| `POST /api/v1/upload-review/start` | 发起异步审查 |
| `GET /api/v1/upload-review/{id}/status` | 查询审查进度 |
| `GET /api/v1/upload-review/{id}/result` | 下载 Excel 结果 |
| `POST /api/v1/local-review` | 直接审查服务器已有文件 |
| `GET /api/v1/local-files` | 列出服务器已有 PDF |

## 服务拓扑

| 服务 | 端口 | 说明 |
|------|------|------|
| backend | 8000 | FastAPI + 审查管线 |
| nginx | 58080 | 反向代理 |
| mineru-api | 8000 (内部) | MinerU OCR 引擎，GPU 0/1/2 |
| postgres | 5432 | 数据库 |
| redis | 6379 | Celery 队列 |
| minio | 9001 | 对象存储 |
| prometheus | 9090 | 监控 |
| grafana | 3001 | 仪表盘 |

## 环境变量

```env
BID_REVIEW_DEEPSEEK_API_KEY=sk-xxx
BID_REVIEW_DEEPSEEK_BASE_URL=https://api.deepseek.com
BID_REVIEW_DEEPSEEK_MODEL=deepseek-chat
BID_REVIEW_MAP_REDUCE_CONCURRENCY=5
```

## 项目结构

```
zzaudt/
├── backend/
│   └── app/
│       ├── pipeline/         # 核心管线
│       │   ├── discriminator.py  # PDF 类型判别
│       │   ├── ocr.py            # MinerU OCR 调用
│       │   ├── splitter.py       # Markdown 分片
│       │   ├── llm_agent.py      # DeepSeek Agent
│       │   ├── map_reduce.py     # 并行提取 + 归并
│       │   └── prompts/          # LLM Prompt 模板
│       ├── api/v1/               # REST API
│       ├── services/             # 异步审查引擎
│       └── core/                 # 配置
├── frontend/                 # 静态前端
├── infra/                    # nginx/prometheus/grafana
├── mineru/                   # MinerU Dockerfile
├── docker-compose.yml        # 服务编排
└── docs/                     # 设计文档
```
