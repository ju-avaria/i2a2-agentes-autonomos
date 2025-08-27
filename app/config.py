from dataclasses import dataclass
from pathlib import Path
from datetime import date, datetime
import os


@dataclass
class Settings:
    competencia: date
    base_ativos: Path
    base_ferias: Path
    base_desligados: Path
    base_cadastral: Path
    base_sindicato_valor: Path
    calendario_path: Path
    out_dir: Path
    chroma_host: str
    chroma_port: int
    ollama_base_url: str
    ollama_model: str


def load_settings() -> Settings:
    return Settings(
        competencia=datetime.fromisoformat(os.getenv("COMPETENCIA", "2025-05-01")).date(),
        base_ativos=Path(os.getenv("ATIVOS", "/dados/ativos.xlsx")),
        base_ferias=Path(os.getenv("FERIAS", "/dados/ferias.xlsx")),
        base_desligados=Path(os.getenv("DESLIGADOS", "/dados/desligados.xlsx")),
        base_cadastral=Path(os.getenv("CADASTRAL", "/dados/cadastral.xlsx")),
        base_sindicato_valor=Path(os.getenv("SINDICATO_VALOR", "/dados/sindicatos_valores.xlsx")),
        calendario_path=Path(os.getenv("CALENDARIO", "/dados/calendario_feriados.parquet")),
        out_dir=Path(os.getenv("OUT_DIR", "/out")),
        chroma_host=os.getenv("CHROMA_HOST", "chroma"),
        chroma_port=int(os.getenv("CHROMA_PORT", "8000")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_K_M"),
    )
