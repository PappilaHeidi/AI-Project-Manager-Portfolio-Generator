FROM python:3.11-slim

WORKDIR /app

# Copy shared database module first
COPY shared /app/shared

# Copy service requirements and install
COPY services/portfolio-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/portfolio-service/app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]