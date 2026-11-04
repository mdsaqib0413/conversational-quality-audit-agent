
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    STREAMLIT_SERVER_PORT=7860 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    USE_EMBEDDINGS=0 \
    VECTOR_STORE=numpy

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY src/ ./src/
COPY agents/ ./agents/
COPY scorecard/ ./scorecard/
COPY .streamlit/ ./.streamlit/

COPY data/audio/ ./data/audio/
COPY data/demo_cache/ ./data/demo_cache/
COPY data/transcripts/ ./data/transcripts/
COPY data/live_calls/ ./data/live_calls/
COPY data/policies/ ./data/policies/
COPY data/sops/ ./data/sops/
COPY data/expected/ ./data/expected/
COPY data/rubric.yaml ./data/rubric.yaml

RUN mkdir -p traces cache data/cache/audits data/index_cache reviews eval/results

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl --fail http://localhost:7860/_stcore/health || exit 1

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=7860", "--server.address=0.0.0.0"]
