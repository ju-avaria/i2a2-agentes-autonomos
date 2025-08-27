# Automação da compra de VR/VA

Pipeline determinística que **consolida bases**, **valida** dados, **aplica exclusões** (férias/afastamentos/estágio/aprendiz/diretoria), **conta dias úteis** por sindicato/UF/município e **calcula os valores** de VR/VA por colaborador.  
A saída é um Excel padronizado na pasta out.

> **Documentação geral**: na **raiz deste projeto** você encontra um PDF com visão geral e instruções que facilitam a execução dos projetos.

---
## Pré-requisitos

- **Docker** (Docker Engine no Linux / Docker Desktop no Windows)  
- **Docker Compose v2**  
- Portas livres: **11434** (Ollama) e **8000** (Chroma)

  
## Como rodar

### 🐧 Linux
```bash
cd VR_CH
mkdir -p app dados out ollama

# (opcional) exportar UID/GID para alinhar permissões
export UID=$(id -u) GID=$(id -g)

# ajuste app/.env.example e rode:
docker compose up -d --build

# acompanhar logs
docker logs -f vrva-agent

# resultado
ls out/
# → VR Mensal mm.AAAA.xlsx
```
### 🪟 Windows

```bash
cd VR_CH
mkdir app,dados,out,ollama

# ajuste app\.env.example e rode:
docker compose -f docker-compose.windows.yml up -d --build

# logs
docker logs -f vrva-agent

# resultado em .\out\

```
