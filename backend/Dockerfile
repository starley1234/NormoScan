FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 poppler-utils tesseract-ocr tesseract-ocr-rus \
    && rm -rf /var/lib/apt/lists/*

ARG WITH_VLM=false
COPY requirements.txt .
COPY requirements-vlm.txt .
RUN pip install --no-cache-dir --default-timeout=100 --retries 5 --prefer-binary -r requirements.txt && \
    if [ "$WITH_VLM" = "true" ]; then pip install --no-cache-dir --default-timeout=100 --retries 5 --prefer-binary -r requirements-vlm.txt; fi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
