FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Inter for the screens; DejaVu as fallback.
RUN apt-get update && apt-get install -y --no-install-recommends fonts-inter fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY server ./server
COPY tests/fixtures ./tests/fixtures
ENV PYTHONPATH=/app/server DATA_DIR=/data
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "budget_box.app:app", "--host", "0.0.0.0", "--port", "8000"]
