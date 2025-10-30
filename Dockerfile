FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema (opcional, mas ajuda em libs nativas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Vars padrão (podem ser sobrescritas nos Secrets do Space)
ENV CFOP_TXT_PATH=/app/cfop.txt
ENV HF_MODEL=microsoft/Phi-3.5-mini-instruct
ENV PORT=7860

# Use a PORT do ambiente (Spaces define PORT)
CMD ["sh", "-c", "uvicorn agent_cfop_service:app --host 0.0.0.0 --port ${PORT}"]
