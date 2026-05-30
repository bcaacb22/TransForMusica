# Use an official Python 3.10 slim image
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable stdout/stderr buffering
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required by audio and ML packages
# - build-essential / gcc for building wheels
# - ffmpeg and libsndfile for audio handling
# - libsndfile1-dev, libsndfile1 provide soundfile support
# - git for some packages that may pull from git
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      ffmpeg \
      libsndfile1 \
      libsndfile1-dev \
      liblapack-dev \
      libblas-dev \
      libffi-dev \
      libssl-dev \
      git \
      ca-certificates \
      wget \
    && rm -rf /var/lib/apt/lists/*

# Create a working directory
WORKDIR /app

# Copy only the backend requirements first to leverage Docker layer caching
# NOTE: The repository layout expects backend/requirements.txt to exist.
COPY backend/requirements.txt /app/requirements.txt

# Upgrade pip, setuptools and wheel, then install Python dependencies
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --upgrade cython || true && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy the application code
COPY . /app

# Ensure uploads folder exists
RUN mkdir -p /app/backend/uploads && chown -R root:root /app/backend/uploads

# Expose the default port
EXPOSE 8000

# Provide a healthcheck for the container
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -f http://127.0.0.1:8000/api/ || exit 1

# Default command: run uvicorn serving the backend FastAPI app
# Use --proxy-headers if you front with a proxy/load-balancer in production
CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
