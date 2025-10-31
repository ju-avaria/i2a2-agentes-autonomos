# === core/impostos.py — helpers unificados para cálculos e coerência PIS/COFINS ===
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from typing import Optional

# ---------- Conversores ----------

def D(x, default: str = "0") -> Decimal:
    try:
        if x is None or x == "":
            return Decimal(default)
        if isinstance(x, (int, float, Decimal)):
            return Decimal(str(x))
        return Decimal(str(x).replace(",", "."))
    except InvalidOperation:
        return Decimal(default)


def fmt2(x: Decimal) -> str:
    return f"{x.quantize(Decimal('0.01'))}"


def isclose(a: Decimal, b: Decimal, rel_tol: float = 0.01, abs_tol: float = 0.01) -> bool:
    # tolerância de 1% ou 0,01 absoluto
    da = Decimal(str(rel_tol))
    dt = (abs(b) * da)
    return abs(a - b) <= max(dt, Decimal(str(abs_tol)))


# ---------- Política de fallback (PIS/COFINS) ----------
# Respeita o mesmo contrato do scan_app: usa env opcional e ignora Simples (CRT 1/2)
PISCOFINS_DEFAULTS = {
    "real":      {"pPIS": Decimal("1.65"), "pCOFINS": Decimal("7.60")},
    "presumido": {"pPIS": Decimal("0.65"), "pCOFINS": Decimal("3.00")},
}


def _fallback_pis_cofins_rates(emit: dict) -> Optional[tuple[Decimal, Decimal]]:
    crt = str((emit or {}).get("CRT", "")).strip()
    if crt in {"1", "2"}:  # Simples Nacional
        return None

    regime = os.getenv("REGIME_PISCOFINS", "").strip().lower()
    if regime not in {"real", "presumido"}:
        return None

    d = PISCOFINS_DEFAULTS[regime]
    return d["pPIS"], d["pCOFINS"]


# ---------- Bases de cálculo ----------
# Mesma fórmula usada no scan_app_xml.py

def _calc_pis_cofins_base(prod: dict, ipi: dict | None = None) -> Decimal:
    vProd = D((prod or {}).get("vProd"))
    vDesc = D((prod or {}).get("vDesc"))
    vFrete = D((prod or {}).get("vFrete"))
    vSeg = D((prod or {}).get("vSeg"))
    vOutro = D((prod or {}).get("vOutro"))
    vIPI = D((ipi or {}).get("vIPI")) if ipi else Decimal("0")
    base = (vProd - vDesc + vFrete + vSeg + vOutro + vIPI)
    return base if base >= 0 else Decimal("0")


# === core/auditoria_inline.py — refeito para usar os mesmos helpers ===
from typing import Any, Dict, List, Optional

# importe local (mesmo pacote core)
from .impostos import D, fmt2, isclose, _calc_pis_cofins_base, _fallback_pis_cofins_rates


def _auditar_impostos_item(item: dict, emit: dict | None = None) -> List[Dict[str, Any]]:
    """
    Espera o item no formato extraído pelo app (scan_app):
    {
      'nItem': '1',
      'prod': {...},
      'imposto': {
         'PIS': {'vBC':'', 'pPIS':'', 'vPIS':'', 'qPIS':'', 'vAliqProd':''},
         'COFINS': {'vBC':'', 'pCOFINS':'', 'vCOFINS':'', 'qCOFINS':'', 'vAliqProd':''},
         'IPI': {...}
      }
    }
    """
    achados: List[Dict[str, Any]] = []

    prod = (item.get("prod") or {})
    imp = (item.get("imposto") or {})
    ipi = (imp.get("IPI") or {})

    # PIS
    pis = (imp.get("PIS") or {})
    vBC_pis = D(pis.get("vBC"))
    qPIS = D(pis.get("qPIS"))
    vAliqPIS = D(pis.get("vAliqProd"))
    pPIS = D(pis.get("pPIS"))
    vPIS_xml = D(pis.get("vPIS"))

    # COFINS
    cof = (imp.get("COFINS") or {})
    vBC_cof = D(cof.get("vBC"))
    qCOF = D(cof.get("qCOFINS"))
    vAliqCOF = D(cof.get("vAliqProd"))
    pCOF = D(cof.get("pCOFINS"))
    vCOF_xml = D(cof.get("vCOFINS"))

    # Fallback de alíquota quando aplicável (não SN e sem p informado)
    if emit is not None:
        fb = _fallback_pis_cofins_rates(emit)
        if fb:
            fb_pis, fb_cof = fb
            if pPIS <= 0:
                pPIS = fb_pis
            if pCOF <= 0:
                pCOF = fb_cof

    # Cálculo PIS (alíquota ad valorem ou por unidade)
    if qPIS > 0 and vAliqPIS > 0:
        base_p = qPIS
        vPIS_calc = (qPIS * vAliqPIS).quantize(Decimal("0.01"))
    else:
        base_p = vBC_pis if vBC_pis > 0 else _calc_pis_cofins_base(prod, ipi)
        vPIS_calc = (base_p * (pPIS/Decimal("100"))).quantize(Decimal("0.01"))

    if vPIS_xml > 0 and not isclose(vPIS_xml, vPIS_calc):
        achados.append({
            "tipo": "pis_incorreto",
            "msg": f"PIS informado {fmt2(vPIS_xml)} difere do calculado {fmt2(vPIS_calc)} (base {fmt2(base_p)}; aliq {pPIS}%)",
        })

    # Cálculo COFINS
    if qCOF > 0 and vAliqCOF > 0:
        base_c = qCOF
        vCOF_calc = (qCOF * vAliqCOF).quantize(Decimal("0.01"))
    else:
        base_c = vBC_cof if vBC_cof > 0 else _calc_pis_cofins_base(prod, ipi)
        vCOF_calc = (base_c * (pCOF/Decimal("100"))).quantize(Decimal("0.01"))

    if vCOF_xml > 0 and not isclose(vCOF_xml, vCOF_calc):
        achados.append({
            "tipo": "cofins_incorreto",
            "msg": f"COFINS informado {fmt2(vCOF_xml)} difere do calculado {fmt2(vCOF_calc)} (base {fmt2(base_c)}; aliq {pCOF}%)",
        })

    # Coesão PIS×COFINS: se ambos usam base vBC vazia, garantimos mesma base calculada
    if (vBC_pis <= 0 and vBC_cof <= 0) and not isclose(base_p, base_c):
        achados.append({
            "tipo": "bases_divergentes",
            "msg": f"Base PIS ({fmt2(base_p)}) e COFINS ({fmt2(base_c)}) divergiram; unifique campos vBC no XML ou regras de desconto/frete.",
        })

    return achados


def auditar_totais(totais: dict, soma_itens_vprod: Decimal) -> List[Dict[str, Any]]:
    achados: List[Dict[str, Any]] = []
    vNF = D((totais or {}).get("vNF"))
    if not isclose(vNF, soma_itens_vprod):
        achados.append({
            "tipo": "total_incoerente",
            "msg": f"vNF {fmt2(vNF)} difere da soma dos itens (vProd) {fmt2(soma_itens_vprod)}",
        })
    return achados


def auditar_nfe_inline(
    extracted: dict,
    uf_emit: str,
    uf_dest: str,
    pedido_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    achados_itens: List[Dict[str, Any]] = []
    diffs_pedido: List[Dict[str, Any]] = []

    emit = extracted.get("emit", {}) or {}
    itens = extracted.get("itens", []) or []   # <<== padronizado com o app
    totais = extracted.get("totais", {}) or {}  # <<== padronizado com o app

    # Itens
    for it in itens:
        achados_itens.extend(_auditar_impostos_item(it, emit=emit))

    # Totais
    soma_itens_vprod = sum([D((it.get("prod") or {}).get("vProd")) for it in itens])
    achados_totais = auditar_totais(totais, soma_itens_vprod)

    # Pedido (opcional): compara por codigo/descricao aproximado
    if pedido_rows:
        norm = lambda s: (s or "").strip().lower()
        for row in pedido_rows:
            alvo_desc = norm(row.get("descricao"))
            alvo_cod = norm(row.get("codigo"))
            encontrado = False
            for it in itens:
                p = it.get("prod", {}) or {}
                if norm(p.get("cProd")) == alvo_cod or alvo_desc in norm(p.get("xProd")):
                    encontrado = True
                    try:
                        v_xml = D(p.get("vProd"))
                        v_ped = D(row.get("vunit", row.get("valor"))) * D(row.get("quantidade", "1"))
                        if not isclose(v_xml, v_ped):
                            diffs_pedido.append({
                                "tipo": "valor_divergente",
                                "msg": f"{p.get('xProd','')} diverge do pedido (XML {fmt2(v_xml)} × Pedido {fmt2(v_ped)})",
                                "xml": {"xProd": p.get("xProd"), "vProd": fmt2(v_xml)},
                                "pedido": {"descricao": row.get("descricao"), "valor": str(row.get("vunit"))},
                            })
                    except Exception:
                        pass
            if not encontrado:
                diffs_pedido.append({
                    "tipo": "produto_nao_encontrado",
                    "msg": f"Item de pedido '{row.get('descricao')}' não encontrado na NF-e",
                })

    total_achados = len(achados_itens) + len(achados_totais) + len(diffs_pedido)
    score = "BAIXO" if total_achados <= 3 else ("MÉDIO" if total_achados <= 10 else "ALTO")

    return {
        "itens": achados_itens,
        "totais": achados_totais,
        "pedido": diffs_pedido,
        "score": score,
    }


