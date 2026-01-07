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
RUN set -e && \
    if [ -z "$GITHUB_TOKEN" ]; then \
        echo "ERROR: GITHUB_TOKEN not provided. Cannot install private subtribe-ai package." && \
        exit 1; \
    fi && \
    git config --global url."https://${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/" && \
    pip install --no-cache-dir -r requirements.txt && \
    git config --global --unset-all url."https://${GITHUB_TOKEN}@github.com/".insteadOf || true && \
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