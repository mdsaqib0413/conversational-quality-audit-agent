# Conversational Quality Audit Agent - Production Container
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8501 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Install OS audio libraries and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for caching layers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and required data
COPY app/ ./app/
COPY src/ ./src/
COPY scorecard/ ./scorecard/
COPY data/sops/ ./data/sops/
COPY data/policies/ ./data/policies/
COPY data/rubric.yaml ./data/rubric.yaml
COPY eval_data/ ./eval_data/
COPY eval/ ./eval/
COPY docs/ ./docs/
COPY tests/ ./tests/

# Create runtime directories for traces, cache, and reviews
RUN mkdir -p traces cache data/cache/audits reviews eval/results

# Expose Streamlit default port
EXPOSE 8501

# Container healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Launch application
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]

