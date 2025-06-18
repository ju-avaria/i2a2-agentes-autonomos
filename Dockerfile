FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Instala dependências de compilação necessárias para o llama-cpp-python
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia tudo para o container
COPY . .

# Atualiza pip e instala dependências
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta do Streamlit
EXPOSE 8501

# Comando para rodar o Streamlit apontando para seu script principal
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]

