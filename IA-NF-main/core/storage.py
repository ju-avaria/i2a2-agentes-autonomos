# core/storage.py
import os, csv, json, datetime, re
from typing import Dict, Any, Optional

# tenta reutilizar o to_jsonable do seu extrair.py
try:
    from extrair import to_jsonable
except Exception:
    from decimal import Decimal
    def to_jsonable(obj):
        if isinstance(obj, dict):
            return {k: to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [to_jsonable(v) for v in obj]
        if isinstance(obj, Decimal):
            return format(obj, "f")
        if obj is None:
            return ""
        return obj

def _only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def _slug(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9\-_\.]+", "_", s)
    return s[:120] or "nota"

def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

def _ym_from_extracted(ex: Dict[str, Any]) -> str:
    # tenta dhEmi (YYYY-MM-DD...)
    dh = (ex.get("ide") or {}).get("dhEmi") or ""
    m = re.search(r"(\d{4})-(\d{2})", dh)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # fallback: hoje
    now = datetime.datetime.now()
    return f"{now.year:04d}-{now.month:02d}"

def _pick_chave(ex: Dict[str, Any]) -> str:
    ch = (ex or {}).get("chave_acesso") or ""
    if ch: return ch
    # fallback combina emit + nNF + serie
    ide = ex.get("ide") or {}
    emit = ex.get("emit") or {}
    return f"{_only_digits(emit.get('CNPJ') or emit.get('CPF') or 'x')}_{ide.get('nNF','0')}_{ide.get('serie','0')}"

def save_note_bundle(extracted: Dict[str, Any],
                     classif: Dict[str, Any],
                     xml_bytes: bytes,
                     base_dir: str = "data") -> Dict[str, str]:
    """
    Estrutura de pastas:
    data/{tipo}/{YYYY-MM}/{emit_cnpj}/chave/
      - nota.json
      - original.xml
    E index global em data/index.csv
    """
    tipo = (classif.get("tipo") or "indefinido").lower()
    ym = _ym_from_extracted(extracted)
    emit = extracted.get("emit") or {}
    emit_doc = _only_digits(emit.get("CNPJ") or emit.get("CPF") or "sem_emit")
    chave = _slug(_pick_chave(extracted))

    folder = os.path.join(base_dir, tipo, ym, emit_doc, chave)
    _ensure_dir(folder)

    # nota.json (extracted + classif) — SEMPRE via to_jsonable
    bundle = {
        "extracted": extracted,
        "classificacao": classif,
    }
    with open(os.path.join(folder, "nota.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(to_jsonable(bundle), ensure_ascii=False, indent=2))

    # original.xml
    with open(os.path.join(folder, "original.xml"), "wb") as fxml:
        fxml.write(xml_bytes or b"")

    # index.csv (append)
    _ensure_dir(base_dir)
    index_path = os.path.join(base_dir, "index.csv")
    header = [
        "tipo","ano_mes","emit_doc","chave",
        "numero","serie","vNF","vProd","vICMS","vIPI",
        "primeiro_cfop","primeiro_desc"
    ]
    write_header = not os.path.exists(index_path)
    ide = extracted.get("ide") or {}
    tot = extracted.get("totais") or {}
    itens = extracted.get("itens") or []
    cfop1 = (itens[0].get("prod") or {}).get("CFOP","") if itens else ""
    desc1 = (itens[0].get("prod") or {}).get("xProd","") if itens else ""
    row = {
        "tipo": tipo,
        "ano_mes": ym,
        "emit_doc": emit_doc,
        "chave": chave,
        "numero": (ide.get("nNF") or ""),
        "serie": (ide.get("serie") or ""),
        "vNF": str(tot.get("vNF") or ""),
        "vProd": str(tot.get("vProd") or ""),
        "vICMS": str(tot.get("vICMS") or ""),
        "vIPI": str(tot.get("vIPI") or ""),
        "primeiro_cfop": cfop1,
        "primeiro_desc": desc1[:120],
    }
    # escreve/append
    with open(index_path, "a", newline="", encoding="utf-8") as csvf:
        w = csv.DictWriter(csvf, fieldnames=header)
        if write_header:
            w.writeheader()
        w.writerow(row)

    return {"folder": folder, "index": index_path}
