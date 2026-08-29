FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY size_note ./size_note

RUN pip install --no-cache-dir .

RUN mkdir -p /data

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn size_note.main:app --host 0.0.0.0 --port 8000"]
