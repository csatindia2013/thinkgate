# Base image with Python and Linux
FROM python:3.10-slim

# Install required OS packages including Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy your code
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port for Render
ENV PORT 10000
EXPOSE 10000

# Start the app
CMD ["python", "app.py"]
