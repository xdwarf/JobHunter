# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies for web scraping
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/src/
COPY evaluate_job.mcp /app/

# Set Python to run in unbuffered mode for better Docker logging
ENV PYTHONUNBUFFERED=1

# Default command: run the main script
CMD ["python", "/app/src/run.py"]
