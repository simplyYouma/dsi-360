# Image API DSI 360 (FastAPI). Dev : code source monté en volume + install éditable.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e ".[dev]"

COPY src ./src

EXPOSE 8000
CMD ["uvicorn", "dsi360.interface.app:app", "--host", "0.0.0.0", "--port", "8000"]
