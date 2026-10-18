# Multi-stage / lightweight Python 3.11 container for RozgarPay AI
# Optimized for rapid deployment on AMD ROCm-enabled host or standard cloud runners
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies (curl for healthchecks, build tools if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application codebase
COPY . .

# Expose default port (Railway/Render will override via $PORT)
ENV PORT=8501
EXPOSE 8501

# Launch Streamlit server respecting dynamic $PORT from cloud platforms (Railway, Render, etc.)
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false"]
