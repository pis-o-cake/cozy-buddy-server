FROM python:3.10-slim AS base

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Poetry 설치
RUN pip install --no-cache-dir poetry==2.3.2

# 의존성 설치 (캐시 활용)
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# 소스 복사
COPY . .
RUN poetry install --no-interaction --no-ansi

# 로그 디렉토리
RUN mkdir -p logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
