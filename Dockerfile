# Base image
FROM python:3.10-slim

# Install system dependencies (OpenCV requires libGL, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install dependencies first (to leverage Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ensure necessary directories exist
RUN mkdir -p logs models data/samples

# Expose ports for FastAPI (8000) and Streamlit (8501)
EXPOSE 8000
EXPOSE 8501

# The execution command will be overridden by docker-compose
CMD ["bash"]
