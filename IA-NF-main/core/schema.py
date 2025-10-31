from __future__ import annotations
from typing import Dict, Any, List
from decimal import Decimal

def _as_decimal(x) -> Decimal:
    try:
        return Decimal(str(x).replace(",", "."))
    except Exception:
        return Decimal("0")

def normalize_extracted(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Padroniza a estrutura para NF-e e NFSe.
    Campos principais:
      tipo: "NFe" | "NFSe"
      ide: {...}
      emit: {...}
      dest: {...}
      itens: [ {xProd, qCom, vUnCom, vProd, NCM, CFOP, CST...}, ... ]  # NFSe: pode ser []
      totais: {vProd, vNF, vICMS, vIPI, vPIS, vCOFINS, ...}
    """
    d = {**doc}

    d.setdefault("ide", {})
    d.setdefault("emit", {})
    d.setdefault("dest", {})
    d.setdefault("itens", [])
    d.setdefault("totais", {})

    # converte números para Decimal (quando fizer contas)
    for k in ("vProd", "vNF", "vICMS", "vIPI", "vPIS", "vCOFINS"):
        if k in d["totais"]:
            d["totais"][k] = _as_decimal(d["totais"][k])

    for it in d["itens"]:
        for k in ("qCom", "vUnCom", "vProd"):
            if k in it:
                it[k] = _as_decimal(it[k])

    return d
