# Production Dockerfile for AniFilter AI
FROM python:3.11-slim

WORKDIR /app

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY run.py .

# Expose port (default 8080 or PORT env var)
EXPOSE 8080

# Run uvicorn on container start
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
