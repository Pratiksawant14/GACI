FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (UID 1000) for Hugging Face Spaces compatibility
RUN useradd -m -u 1000 user

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Normalize line endings and permissions on startup script
RUN sed -i 's/\r$//' /app/start.sh && \
    chmod +x /app/start.sh && \
    chown -R user:user /app

USER user

EXPOSE 7860

CMD ["/app/start.sh"]
