# API 契约

## 1. 通用规则

- 前缀：`/api/v1`
- 鉴权：Phase B 接入 Bearer Token；健康检查匿名可用。
- 分页：`page` 从 1 开始，`page_size` 最大 100。
- 写接口支持 `Idempotency-Key`；相同用户、资源和请求体返回原结果。
- 时间使用 ISO 8601，ID 使用 UUID。
- 不返回模型思考过程，只返回任务事件、结构化事实、Finding 和证据。

统一错误：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数校验失败",
    "request_id": "uuid",
    "details": {}
  }
}
```

分页响应：

```json
{"items": [], "meta": {"page": 1, "page_size": 20, "total": 0}}
```

## 2. 已实现接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/health/live` | 进程存活探针 |
| GET | `/api/v1/health/ready` | 就绪探针；当前仅校验配置 |

## 3. Phase B/C 目标接口

| 方法 | 路径 | 权限 | 核心响应/行为 |
| --- | --- | --- | --- |
| POST | `/projects` | project:create | 创建单文件或全量项目 |
| GET | `/projects` | project:read | 分页项目列表 |
| GET | `/projects/{project_id}` | project:read | 项目摘要、状态、投标人统计 |
| POST | `/projects/{project_id}/documents` | document:upload | multipart 上传、类型、bidder_id；返回 202 |
| GET | `/projects/{project_id}/documents` | document:read | 文档、版本、扫描和解析状态 |
| POST | `/projects/{project_id}/runs` | run:start | 创建幂等审查 Run，返回 202 |
| GET | `/runs/{run_id}` | run:read | Run 总状态和任务统计 |
| GET | `/runs/{run_id}/events` | run:read | 可审计事件分页；后续可扩展 SSE |
| GET | `/projects/{project_id}/findings` | finding:read | 按状态、类别、等级筛选 |
| GET | `/findings/{finding_id}` | finding:read | Finding、Evidence、复核历史 |
| POST | `/findings/{finding_id}/reviews` | finding:review | 追加人工决定，使用版本号防并发覆盖 |
| POST | `/projects/{project_id}/reports` | report:create | 创建 Excel/报告任务，返回 202 |
| GET | `/reports/{report_id}/download` | report:download | 返回短时效签名 URL 或受控下载 |
| GET | `/projects/{project_id}/audit-logs` | audit:read | 分页审计日志 |

## 4. 关键请求示例

创建项目：

```json
{"name": "某项目", "code": "P-2026-001", "mode": "single_file"}
```

启动审查：

```json
{
  "mode": "single_file",
  "document_ids": ["uuid"],
  "pipeline_version": "phase-a.1",
  "rule_version": "single-file.1"
}
```

人工复核：

```json
{
  "action": "confirm",
  "finding_version": 1,
  "revised_risk_level": "medium",
  "comment": "证据页码已人工核对"
}
```

允许的 action 为 `confirm`、`reject`、`revise`、`request_material`。服务端始终新增
ReviewDecision；不更新或删除历史决定。

## 5. 状态码

- `200/201`：同步成功；`202`：异步任务已接受。
- `400`：业务参数不合法；`401/403`：未认证/无权限。
- `404`：资源不存在或用户无权获知其存在。
- `409`：幂等键冲突、版本冲突或非法状态迁移。
- `413/415`：文件过大/类型不支持；`422`：Schema 校验失败。
- `429`：限流；`503`：依赖未就绪。

