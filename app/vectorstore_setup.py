from pathlib import Path
import uuid

from chromadb import HttpClient
from chromadb.config import Settings


def get_chroma_collection(host: str, port: int, name: str = "vrva-policies"):
    client = HttpClient(
        host=host,
        port=port,
        settings=Settings(anonymized_telemetry=False),
    )
    coll = client.get_or_create_collection(name=name)
    return coll


def ingest_policies(collection, policies_dir: Path) -> int:
    if not policies_dir.exists():
        return 0

    texts, ids, metadatas = [], [], []
    for p in policies_dir.glob("**/*"):
        if p.is_file() and p.suffix.lower() in {".md", ".txt"}:
            texts.append(p.read_text(encoding="utf-8", errors="ignore"))
            ids.append(str(uuid.uuid4()))
            metadatas.append({"path": str(p)})

    if texts:
        collection.add(documents=texts, ids=ids, metadatas=metadatas)

    return len(texts)
