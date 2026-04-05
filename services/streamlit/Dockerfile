FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /root/.streamlit

COPY .streamlit/config.toml /root/.streamlit/config.toml

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
 CMD curl -f http://localhost:8501/_stcore/health || exit 1 

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]