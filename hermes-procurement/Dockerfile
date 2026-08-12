FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools && pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir --upgrade --no-deps pyasn1==0.6.3
COPY . .
RUN useradd -m -u 1001 hermes && chown -R hermes:hermes /app
USER hermes
EXPOSE 8004
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
