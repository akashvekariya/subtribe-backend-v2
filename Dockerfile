# Use official Python runtime
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies (including git for private repo access)
RUN apt-get update && apt-get install -y \
    postgresql-client \
    git \
    && rm -rf /var/lib/apt/lists/*

# GitHub token for private repo access (passed as build arg)
ARG GITHUB_TOKEN
ENV GITHUB_TOKEN=${GITHUB_TOKEN}

# Copy requirements and install Python dependencies
COPY requirements.txt .

# Install base requirements (without subtribe-ai)
RUN pip install --no-cache-dir -r requirements.txt

# Install subtribe-ai with baml_client generation
RUN set -e && \
    if [ -z "$GITHUB_TOKEN" ]; then \
        echo "ERROR: GITHUB_TOKEN not provided. Cannot install private subtribe-ai package." && \
        exit 1; \
    fi && \
    echo "Installing baml-py to get baml-cli..." && \
    pip install --no-cache-dir baml-py==0.216.0 && \
    echo "Cloning subtribe-ai repository..." && \
    git clone https://${GITHUB_TOKEN}@github.com/thesubtribe/subtribe-ai.git /tmp/subtribe-ai && \
    cd /tmp/subtribe-ai && \
    echo "Generating BAML client..." && \
    baml-cli generate --from src/subtribe_ai/baml_src && \
    echo "Installing subtribe-ai package..." && \
    pip install --no-cache-dir . && \
    cd / && \
    rm -rf /tmp/subtribe-ai && \
    unset GITHUB_TOKEN

# Copy application code
COPY app/ ./app/
COPY database/ ./database/
COPY alembic.ini .

# Expose port (Cloud Run uses PORT env var)
ENV PORT=8080
EXPOSE 8080

# Run the application
# --no-access-log: Disable uvicorn access logs (we use our logging middleware instead)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --no-access-log"]