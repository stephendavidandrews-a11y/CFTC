FROM python:3.11-slim

# Install system deps for PDF processing (tesseract, poppler)
RUN apt-get update && apt-get install -y --no-install-recommends     tesseract-ocr     poppler-utils     gcc     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create directories
RUN mkdir -p /app/pdf_storage /app/data

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
