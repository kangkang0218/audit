# 投标文件三项审查前端

该目录由旧资料包中经过确认的静态前端抽出，只保留 HTML、CSS 和 JavaScript。
页面由当前 `backend/app/main.py` 直接托管，不依赖或导入旧资料包后端。

## 本地启动

```bash
cd backend
/home/dzr/miniconda3/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000
```

浏览器打开 `http://127.0.0.1:8000/`。

页面使用当前后端接口：

- `POST /api/v1/pdf-info`：读取 PDF 实际页数；
- `POST /api/v1/bid-review`：执行当前纯本地单文件审查并返回七表 Excel。

网页上传不会自动调用 Qwen、DeepSeek、OCR 或其他外部服务。
