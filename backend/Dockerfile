# backend/Dockerfile
FROM python:3.12-slim

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Ensure logs appear immediately
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements ./requirements

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements/production.txt

# Copy project files
COPY . .

# Create directories for static and media
RUN mkdir -p /app/staticfiles /app/media

# Expose Django port
EXPOSE 8000

# Start with Gunicorn
CMD ["gunicorn", "vyapar_margadarshan.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "1", \
     "--threads", "4", \
     "--timeout", "120"]