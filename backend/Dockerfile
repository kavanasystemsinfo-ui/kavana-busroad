# Dockerfile for Kavana BusRoad backend (FastAPI)
# Use official Python slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if any) - currently none needed beyond pip
# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY app ./app

# Expose port (default 8000, can be overridden by PORT env var)
EXPOSE 8000

# Environment variable for Python to avoid buffering
ENV PYTHONUNBUFFERED=1

# Run the application
# Use uvicorn with host 0.0.0.0 and port from env PORT (default 8000)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]