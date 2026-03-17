FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Create data and uploads dirs
RUN mkdir -p /app/data /app/uploads

ENV PYTHONUNBUFFERED=1
ENV TRACKER_DB_PATH=/app/data/tracker.db
ENV TRACKER_UPLOAD_DIR=/app/uploads

EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
