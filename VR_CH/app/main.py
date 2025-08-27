from pathlib import Path
import time
import requests
from dotenv import load_dotenv

from config import load_settings
from agentes import build_graph, make_llm
from vectorstore_setup import get_chroma_collection, ingest_policies


def ensure_model(base_url: str, model: str) -> None:
    """Puxa o modelo no Ollama caso ainda não exista localmente."""
    try:
        requests.post(f"{base_url}/api/pull", json={"name": model}, timeout=5)
    except Exception:
        pass
    time.sleep(3)


def main() -> None:
    settings = load_settings()

    coll = get_chroma_collection(settings.chroma_host, settings.chroma_port)
    ingest_policies(coll, Path("/app/policies"))

    ensure_model(settings.ollama_base_url, settings.ollama_model)

    llm = make_llm(settings.ollama_base_url, settings.ollama_model)
    graph = build_graph(llm)

    state = {
        "settings": settings,
        "docs_ctx": "",
        "dfs": {},
        "erros": None,
        "avisos": None,
        "df_final": None,
        "export_path": "",
    }

    result = graph.invoke(state)
    print({"export": result.get("export_path")})


if __name__ == "__main__":
    load_dotenv()
    main()
