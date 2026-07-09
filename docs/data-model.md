# 数据模型

## 1. 通用约定

所有领域实体使用 UUID 主键，并包含 `created_at`、`updated_at`、`created_source` 和
`record_version`。时间按带时区 UTC 存储、展示层转换为本地时区。结构化可变数据使用
JSON，核心查询字段保持独立列和索引。

敏感编号不保存明文：`*_masked` 用于展示，`*_hmac` 使用租户/环境密钥生成固定长度
HMAC 以支持相等比较。HMAC 密钥不得进入数据库或日志。

## 2. 身份与项目

| 实体 | 作用 | 关键约束 |
| --- | --- | --- |
| User | 用户 | username 唯一，密码只存强哈希 |
| Role | 角色及权限集合 | code 唯一，User 与 Role 多对多 |
| Project | 审查项目 | mode 为 single_file/project_full |
| Bidder | 项目内投标人 | project_id + name 唯一 |

## 3. 文档与处理

| 实体 | 作用 | 关键字段 |
| --- | --- | --- |
| SourceDocument | 当前文档逻辑记录 | 类型、SHA-256、大小、页数、版本、上传人、对象路径 |
| DocumentVersion | 不可变文件版本 | version_number、SHA-256、对象路径、变更原因 |
| DocumentPage | 页级解析结果 | 双页码、文本、OCR 文本、图片路径、尺寸、解析状态 |
| ProcessingRun | 一次审查运行 | 模式、状态、幂等键、流水线版本、起止时间 |
| ProcessingTask | 可重试任务 | task_key、类型、尝试次数、进度、trace_id |

`SourceDocument` 不直接存文件；原件、页面图和 OCR 工件进入私有对象存储。

## 4. 事实、人员与证据

| 实体 | 作用 |
| --- | --- |
| ExtractedFact | 类型化事实、标准化值、脱敏显示值、方法、置信度 |
| Evidence | 文件/页码/坐标/摘录/截图路径/提取方法 |
| PersonnelRecord | 项目与投标人范围内的人员主记录 |
| PersonnelAlias | 姓名别名或 OCR 变体，不自动合并身份 |
| CredentialRecord | 证书类型、级别、专业、脱敏编号和有效期 |
| SocialSecurityReference | 缴费单位、账号、期间和核验状态 |

一个 Fact 可有多个 Evidence。人员、证书和社保记录通过 `source_fact_id` 回溯到事实，
再回溯到原始证据。

## 5. 发现、复核与跨文档线索

| 实体 | 作用 |
| --- | --- |
| Finding | 规则产生的不可覆盖原始发现 |
| FindingEvidence | Finding 与 Evidence 的多对多关联及相关性说明 |
| ReviewDecision | 人工确认、驳回、修订和备注的追加记录 |
| CrossDocumentMatch | 文本、报价、人员或元数据的跨文档匹配线索 |

读取 Finding 的“当前人工状态”时，按 `created_at` 取最新 ReviewDecision；历史决定保留。
跨文档结果的默认状态为 `clue`，不得直接映射为违法结论。

## 6. 版本、报告与审计

| 实体 | 作用 |
| --- | --- |
| PromptVersion | Prompt 内容、输出 Schema、校验和与启用状态 |
| RuleVersion | 规则定义、校验和与启用状态 |
| ModelCallLog | Provider、模型、页范围、Prompt、计量、耗时和脱敏错误 |
| GeneratedReport | 报告类型、模板版本、对象路径和摘要 |
| AuditLog | 谁在何时对何资源执行何动作，保存脱敏前后摘要 |

初始迁移位于 `backend/alembic/versions/91928d8bc3eb_initial_schema.py`。后续模型变化必须
新建迁移，不得修改已在环境中执行过的迁移。

