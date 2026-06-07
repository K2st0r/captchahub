FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for ddddocr
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir ddddocr flask flask-cors pillow

# Copy application
COPY captchahub.py .
COPY static/ static/
RUN mkdir -p static && touch captchahub.db

# Port
EXPOSE 9527

# Run
CMD ["python", "captchahub.py"]
