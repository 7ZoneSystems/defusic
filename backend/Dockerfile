FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ src/

# Create output directory
RUN mkdir -p /app/outputs

EXPOSE 8000

# Cohesivity auth + frontend URL (set at runtime via env vars or docker run -e)
# COHESIVITY_TENANT_ID=golden-squid-braving
# COHESIVITY_MANAGEMENT_KEY=coh_man_xxx
# COHESIVITY_APPLICATION_KEY=coh_app_xxx
# FRONTEND_URL=https://defusic.vercel.app

CMD ["uvicorn", "hearbeat.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
