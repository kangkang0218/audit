# 系统架构

## 1. 目标与边界

系统支持“单文件审查”和“项目全量审查”两种模式，两者共享文档、事实、证据、
规则、人工复核和报告能力。系统只输出风险线索、证据不足和人工复核建议，不作
违法、串通、虚假材料、废标或中标无效等法律定性。

当前仓库已包含生产化工程底座，以及 Phase A 单文件 CLI 的文本层解析、目录定位、
事实/人员提取、Python 规则、可选 OCR/模型增强和固定 Excel 输出。前端、完整上传
API 和跨投标人比对尚未实现。

## 2. 逻辑分层

```text
Vue/PDF.js（Phase C）
        |
Nginx -> FastAPI API -> PostgreSQL
                  | -> MinIO/S3
                  | -> Redis -> Celery Worker
                               | -> PDF/OCR parsers
                               | -> LLM Provider Router
                               | -> Fact/Evidence normalizer
                               | -> Python Rule Engine
                               | -> Excel/Report renderer
```

- API 层：认证、RBAC、分页、统一错误、幂等键、审计入口。
- 任务层：持久化 `ProcessingRun/ProcessingTask` 后投递；任务可重试、可恢复。
- 解析层：PyMuPDF/pdfplumber 优先提取文本，低文本覆盖页进入 OCR。
- 模型层：只通过 Provider 接口接入 Qwen、DeepSeek 等；输出必须通过 Pydantic。
- 领域层：事实与证据标准化，Python 规则引擎产生 Finding。
- 复核层：人工决定追加到 `ReviewDecision`，不修改模型原始 Finding。
- 交付层：版本化 Excel 模板、报告和审计证据包写入私有对象存储。

## 3. 处理链与降级

```text
上传 -> MIME/大小校验 -> 病毒扫描 -> SHA-256 去重/版本化
-> PDF 文本与页面渲染 -> OCR 按需处理 -> 章节/关键页路由
-> 视觉/文本模型抽取 -> Pydantic 校验 -> Evidence 标准化
-> 规则引擎 -> 人工复核队列 -> Excel/报告
```

降级顺序为“视觉模型 -> OCR -> 文本模型 -> 人工复核”。任何步骤失败都记录独立
任务状态和错误码；可用的既有事实仍进入规则引擎，失败页面生成“当前材料不足/
需人工复核”，而不是让整个 Run 失败。

## 4. 一致性和幂等

- 上传以 `project_id + sha256 + version_number` 约束版本。
- Run 使用全局唯一 `idempotency_key`，Task 使用 `run_id + task_key`。
- 对象路径包含项目、文档、版本和内容摘要，重复执行覆盖同一逻辑产物或生成新版本。
- 任务先写状态再执行，重试只读取已提交输入；外部调用使用确定性调用键。
- Finding 固定记录规则版本；Prompt、模型配置、规则和 Excel 均记录版本。

## 5. 证据链

`ExtractedFact -> Evidence <- FindingEvidence -> Finding -> ReviewDecision`

Evidence 保存文件、PDF 页码、印刷页码、坐标、脱敏摘录、截图对象路径、方法和置信度。
图片不进入数据库 Base64。报告中每个结论必须能回溯到 Finding、规则版本和 Evidence。

## 6. 模块演进

- Phase A：CLI 完成文本/OCR、章节定位、事实抽取、规则和兼容 Excel。
- Phase B：上传 API、PostgreSQL、MinIO、Redis/Celery 和单文件异步审查。
- Phase C：Vue 前端、PDF 定位、进度、复核与下载。
- Phase D：项目全量材料和跨投标人比较器。
- Phase E：安全、监控、备份、灾备、黄金样本回归和试点上线。

详细执行清单见 [phase-checklist.md](phase-checklist.md)。
