# Phase A-E 执行清单

## Phase A：单文件 CLI

- [x] 固定 Excel v1 契约、历史模板校验器和脱敏渲染器。
- [x] PDF SHA-256、页数、文本覆盖率清点命令。
- [x] 文本层、印刷页码、标题检测和按需页面图片产物。
- [x] 可选 PaddleOCR 路由；缺少依赖时可记录并降级。
- [x] 目录/正文关键词定位、关键页路由和 Qwen/DeepSeek Provider 抽象。
- [x] facts/personnel/findings/review Pydantic 契约与本阶段单文件规则。
- [x] 中和刚大真实样例 PDF 端到端生成 Excel 并执行黄金字段回归。
- [ ] 三份样例 PDF 全量逐项人工基线回归（当前仅有两份 PDF，历史 Excel 位于 `之前的结果/`）。
- [ ] 明确误报、漏报、耗时、OCR 和模型调用成本基线。

退出标准：三份样例可重复运行；证据可定位；失败可降级；Excel 契约回归通过。

## Phase B：单文件 Web API

- [x] SQLAlchemy 模型、Alembic 初始迁移、FastAPI/Celery 骨架。
- [ ] OIDC/RBAC、项目/文档/Run/Findings/报告 API。
- [ ] MIME、大小、魔数、病毒扫描和隔离区。
- [ ] MinIO 私有桶、签名 URL、上传和产物存储。
- [ ] PostgreSQL 状态机、Redis 队列、幂等与失败恢复。
- [ ] Provider 路由、限流、熔断、模型调用审计。
- [ ] API 与任务集成测试。

退出标准：通过 API 上传单 PDF，可异步完成 Phase A 全链路并下载同等 Excel。

## Phase C：前端

- [ ] Vue 3/TypeScript/Vite 工程和登录。
- [ ] 项目、上传、类型选择、投标人和任务进度。
- [ ] PDF.js 页码跳转、坐标高亮、截图和证据摘录。
- [ ] Finding 筛选、追加式人工复核和并发版本提示。
- [ ] Excel/报告下载与审计日志。
- [ ] 桌面和移动关键视口的端到端测试。

退出标准：审计人员无需 CLI 即可完成单文件上传、复核和导出。

## Phase D：项目全量模式

- [ ] 项目材料完整性和时间链规则。
- [ ] 多投标人报价、单价、文本、目录和元数据比较器。
- [ ] 人员、证书、劳动合同和社保缴费单位交叉比对。
- [ ] 阈值校准、线索聚合和证据包。
- [ ] 项目级报告和跨投标人黄金样本。

退出标准：结果只表述线索/疑点，所有跨文档发现均可回溯双方证据。

## Phase E：生产加固与试点

- [ ] TLS、Secret Manager、密钥轮换、SAST/SCA/SBOM 和镜像扫描。
- [ ] Prometheus 指标、Grafana 告警、OpenTelemetry Trace 和结构化日志。
- [ ] PostgreSQL PITR、对象存储版本化、恢复演练和容量计划。
- [ ] 高可用部署、资源限额、自动扩缩、队列隔离和灾难恢复。
- [ ] 全量回归、性能、并发、故障注入和安全测试。
- [ ] 试点运行手册、值班、问题分级、验收与回退方案。

退出标准：完成安全评审、恢复演练、试点验收和生产上线审批。
