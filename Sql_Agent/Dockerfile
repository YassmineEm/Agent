FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8006

# ← port 8006 au lieu de 8000
CMD ["uvicorn", "sqlAgent:app", "--host", "0.0.0.0", "--port", "8006"]