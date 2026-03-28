# ECS/Fargate container for Brain Tumor MRI inference (Flask + PyTorch CPU)

FROM python:3.11-slim

WORKDIR /app

# System dependencies for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install numpy from PyPI first (pre-built wheel)
RUN pip install --no-cache-dir "numpy<2"

# Install CPU-only PyTorch first (separate layer for Docker cache efficiency)
RUN pip install --no-cache-dir \
    torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir \
    Pillow boto3 flask gunicorn

# Copy application code
COPY app.py .

EXPOSE 8080

CMD ["gunicorn", "--workers=2", "--bind=0.0.0.0:8080", "--timeout=120", "app:app"]
