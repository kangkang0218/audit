FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/pyproject.toml backend/requirements ./
COPY backend/app ./app
COPY frontend /app/frontend
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic

RUN pip install --upgrade pip \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install -e . \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
