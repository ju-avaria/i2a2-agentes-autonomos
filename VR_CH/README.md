# Automação da compra de VR/VA

Este projeto é fruto do **Desafio 04** e tem como objetivo **automatizar o processo mensal de compra de VR (Vale Refeição)**, garantindo que cada colaborador receba o valor correto considerando **ausências, férias, datas de admissão/desligamento** e **calendário de feriados**.

Construímos uma **pipeline determinística** que:
- **Consolida bases** (ativos, férias, desligados, cadastral, sindicato/valor);
- **Valida** dados (pré-verificações);
- **Aplica exclusões** (férias, afastamentos, estágio, aprendiz, diretoria/executivos etc.);
- **Conta dias úteis** por **sindicato/UF/município**;
- **Calcula os valores** de VR/VA por colaborador.

**Saída:** um Excel padronizado gerado em `./out/` 

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

# ajuste app\.env.example e rode:
docker compose -f docker-compose.windows.yml up -d --build

# logs
docker logs -f vrva-agent

# resultado em .\out\

```

