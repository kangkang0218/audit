# 部署说明

## 1. 当前开发拓扑

`docker-compose.yml` 提供 PostgreSQL、Redis、MinIO、FastAPI、Celery Worker、Nginx、
Prometheus 和 Grafana 骨架。默认仅 Nginx `8080`、MinIO 控制台 `9001` 和 Grafana
`3000` 暴露到宿主机；数据库和 Redis 仅在 Compose 网络内。

```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8080/api/v1/health/live
docker compose logs -f backend worker
docker compose down
```

启动时 backend 执行 `alembic upgrade head`。本地不使用容器时：

```bash
make install
make test
make api
```

## 2. 配置

应用环境变量统一使用 `BID_REVIEW_` 前缀，关键项包括：

- `DATABASE_URL`、`REDIS_URL`
- `CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND`
- `OBJECT_STORAGE_ENDPOINT/BUCKET/ACCESS_KEY/SECRET_KEY`
- `MAX_UPLOAD_BYTES`、`SENSITIVE_HMAC_KEY`

`.env` 仅限本地开发。预发布和生产环境必须使用 Secret Manager、Kubernetes Secret
或等价平台能力，并对 Secret 轮换和访问进行审计。

## 3. 迁移与发布

1. 在备份成功后，由单独迁移 Job 执行 `alembic upgrade head`。
2. 迁移成功后滚动发布 API，再发布 Worker。
3. Worker 版本通过 `pipeline_version` 与旧任务隔离；发布期间不复用不兼容任务。
4. 通过 live/ready 探针和错误率观察发布；数据库破坏性变更采用 expand/contract。
5. 回滚应用镜像时不自动 downgrade 数据库；迁移回滚需单独评审。

Compose 适用于开发与试点，不是高可用生产编排。生产建议使用托管 PostgreSQL、对象
存储和 Redis，API/Worker 多副本，任务队列按 OCR、模型、报告拆分。

## 4. 监控与日志

当前已预置 Prometheus/Grafana 容器和数据源。Phase E 接入：

- API 请求量、延迟、错误码、限流、活跃任务。
- 队列长度、任务耗时、重试、失败和 Worker 心跳。
- PDF 页数、OCR 比例、模型耗时/计量/失败率。
- PostgreSQL 连接池、Redis、MinIO 容量与错误。
- OpenTelemetry Trace 贯穿 request_id、run_id、task_id 和 model call。

日志输出 JSON，敏感字段进入统一过滤器；生产 `/metrics` 仅监控网络可访问。

## 5. 备份和恢复

- PostgreSQL：每日全备、连续 WAL、异地副本；目标 RPO 15 分钟、RTO 4 小时，试点后确认。
- MinIO/S3：版本化、生命周期规则、跨区域复制或独立备份。
- 配置：Prompt、规则、模板随制品版本化；Secret 单独备份和轮换。
- Redis：只保留队列状态，任务真相在 PostgreSQL；Redis 丢失后由恢复作业重投未完成任务。

## 6. 已知限制

- readiness 尚未探测 PostgreSQL/Redis，开启依赖检查时明确返回 503。
- 尚未提供 MinIO 初始化桶、ClamAV、TLS、认证和生产指标端点。
- 当前 Compose 密码仅为开发默认值，不能用于共享或生产环境。
- PaddleOCR 依赖和模型文件将在 Phase A 的 OCR 子阶段按运行环境单独封装。

