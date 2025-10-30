# core/auditoria_inline.py — compatível com scan_app_xml.py (itens/totais)
from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

# ---- helpers locais caso core.impostos não exista ----
def _D(x, default="0") -> Decimal:
    try:
        if x is None or x == "":
            return Decimal(default)
        if isinstance(x, (int, float, Decimal)):
            return Decimal(str(x))
        return Decimal(str(x).replace(",", "."))
    except InvalidOperation:
        return Decimal(default)

def _pct(x) -> Decimal:
    return _D(x, "0")

def _isclose(a: Decimal, b: Decimal, *, rel_tol: float = 0.01) -> bool:
    if a == b:
        return True
    if a == 0 and b == 0:
        return True
    diff = abs(a - b)
    base = max(abs(a), abs(b), Decimal("1.00"))
    return diff <= (base * Decimal(str(rel_tol)))

# === Fallback PIS/COFINS por regime (igual ao scan) ===
_PISCOFINS_REGIME_ENV = os.getenv("REGIME_PISCOFINS", "").strip().lower()  # "real" | "presumido" | "" (auto)
_PISCOFINS_DEFAULTS = {
    "real":      {"pPIS": Decimal("1.65"), "pCOFINS": Decimal("7.60")},
    "presumido": {"pPIS": Decimal("0.65"), "pCOFINS": Decimal("3.00")},
}

def _fallback_pis_cofins_rates(emit: dict) -> Optional[tuple[Decimal, Decimal]]:
    """
    Decide alíquotas padrão quando o XML não traz pPIS/pCOFINS.
    - Se CRT in {"1","2"} (Simples): não aplica fallback (retorna None).
    - Se REGIME_PISCOFINS estiver definido (real/presumido): usa esse.
    - Caso contrário, None (preferir o que vier no XML).
    """
    crt = str((emit or {}).get("CRT", "")).strip()
    if crt in {"1", "2"}:
        return None
    regime = _PISCOFINS_REGIME_ENV if _PISCOFINS_REGIME_ENV in {"real", "presumido"} else ""
    if not regime:
        return None
    d = _PISCOFINS_DEFAULTS[regime]
    return d["pPIS"], d["pCOFINS"]

# === Mesma base usada no Recalculo (PIS/COFINS) ===
def _calc_pis_cofins_base(prod: dict, ipi: dict | None = None) -> Decimal:
    vProd = _D(prod.get("vProd"))
    vDesc = _D(prod.get("vDesc"))
    vFrete = _D(prod.get("vFrete"))
    vSeg = _D(prod.get("vSeg"))
    vOutro = _D(prod.get("vOutro"))
    vIPI = _D(ipi.get("vIPI")) if ipi else Decimal("0")
    base = (vProd - vDesc + vFrete + vSeg + vOutro + vIPI)
    return base if base >= 0 else Decimal("0")

# === Auditoria por item – PIS/COFINS (compatível com extrair/scan novos) ===
def _auditar_impostos_item_compat(item: dict, emit: dict | None = None) -> Dict[str, Any]:
    """
    item no formato do scan atual:
      { "nItem":..., "prod": {...}, "imposto": {"IPI": {...}, "PIS": {...}, "COFINS": {...}, "ICMS": {...}} }
    """
    prod = item.get("prod", {}) or {}
    imp  = item.get("imposto", {}) or {}
    ipi  = imp.get("IPI", {}) or {}

    pis = imp.get("PIS", {}) or {}
    cof = imp.get("COFINS", {}) or {}

    # Suporta tributação por quantidade (qPIS/vAliqProd ou qCOFINS/vAliqProd)
    qPIS = _D(pis.get("qPIS"))
    vAliqP = _D(pis.get("vAliqProd"))
    qCOF = _D(cof.get("qCOFINS"))
    vAliqC = _D(cof.get("vAliqProd"))

    achados: List[Dict[str, Any]] = []

    # ----- PIS -----
    if qPIS > 0 and vAliqP > 0:
        base_p = qPIS
        vPIS_calc = (qPIS * vAliqP).quantize(Decimal("0.01"))
        pPIS_txt = f"{vAliqP}/un"
    else:
        base_p = _D(pis.get("vBC")) if pis.get("vBC") not in (None, "", "0") else _calc_pis_cofins_base(prod, ipi)
        pPIS = _D(pis.get("pPIS"))
        # Fallback se necessário
        if pPIS <= 0 and emit:
            fb = _fallback_pis_cofins_rates(emit)
            if fb:
                pPIS = fb[0]
        vPIS_calc = (base_p * (pPIS / Decimal("100"))).quantize(Decimal("0.01"))
        pPIS_txt = f"{pPIS}"

    vPIS_xml = _D(pis.get("vPIS"))
    if base_p > 0 and not _isclose(vPIS_xml, vPIS_calc, rel_tol=0.01):
        achados.append({
            "tipo": "pis_incorreto",
            "msg": f"PIS {vPIS_xml:.2f} difere do esperado {vPIS_calc:.2f} (base {base_p:.2f}, aliq {pPIS_txt})",
            "sugestao": {"vPIS_esperado": f"{vPIS_calc:.2f}", "vBC_utilizada": f"{base_p:.2f}", "aliquota": pPIS_txt},
        })

    # ----- COFINS -----
    if qCOF > 0 and vAliqC > 0:
        base_c = qCOF
        vCOF_calc = (qCOF * vAliqC).quantize(Decimal("0.01"))
        pCOF_txt = f"{vAliqC}/un"
    else:
        base_c = _D(cof.get("vBC")) if cof.get("vBC") not in (None, "", "0") else _calc_pis_cofins_base(prod, ipi)
        pCOF = _D(cof.get("pCOFINS"))
        if pCOF <= 0 and emit:
            fb = _fallback_pis_cofins_rates(emit)
            if fb:
                pCOF = fb[1]
        vCOF_calc = (base_c * (pCOF / Decimal("100"))).quantize(Decimal("0.01"))
        pCOF_txt = f"{pCOF}"

    vCOF_xml = _D(cof.get("vCOFINS"))
    if base_c > 0 and not _isclose(vCOF_xml, vCOF_calc, rel_tol=0.01):
        achados.append({
            "tipo": "cofins_incorreto",
            "msg": f"COFINS {vCOF_xml:.2f} difere do esperado {vCOF_calc:.2f} (base {base_c:.2f}, aliq {pCOF_txt})",
            "sugestao": {"vCOFINS_esperado": f"{vCOF_calc:.2f}", "vBC_utilizada": f"{base_c:.2f}", "aliquota": pCOF_txt},
        })

    return {"achados": achados}

# === Auditoria dos totais ===
def auditar_totais(totais: dict, soma_itens_vprod: Decimal) -> List[Dict[str, Any]]:
    achados: List[Dict[str, Any]] = []

    # 1) vProd (totais) vs soma de vProd dos itens
    vProd_total = _pct(totais.get("vProd"))
    if vProd_total and not _isclose(vProd_total, soma_itens_vprod, rel_tol=0.01):
        achados.append({
            "tipo": "vprod_incoerente",
            "msg": f"vProd total {vProd_total:.2f} difere da soma dos itens {soma_itens_vprod:.2f}",
        })

    # 2) vNF reconstituído (sinalização informativa)
    vNF   = _pct(totais.get("vNF"))
    vDesc = _pct(totais.get("vDesc"))
    vFrete= _pct(totais.get("vFrete"))
    vSeg  = _pct(totais.get("vSeg"))
    vOutro= _pct(totais.get("vOutro"))
    vIPI  = _pct(totais.get("vIPI"))

    if vNF or vProd_total:
        vNF_recomp = (vProd_total - vDesc + vFrete + vSeg + vOutro + vIPI)
        if not _isclose(vNF, vNF_recomp, rel_tol=0.01):
            achados.append({
                "tipo": "vnf_diverge_recomposicao",
                "msg": f"vNF {vNF:.2f} difere do valor recomposto {vNF_recomp:.2f} "
                       f"(vProd - vDesc + vFrete + vSeg + vOutro + vIPI).",
            })
    return achados

# === Reconciliação com pedido (opcional, simples) ===
def _auditar_pedido(itens: List[dict], pedido_rows: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    if not pedido_rows:
        return []
    out: List[Dict[str, Any]] = []
    # Normaliza chaves de item
    norm = []
    for it in itens:
        p = it.get("prod", {}) or {}
        norm.append({
            "xml": it,
            "cProd": str(p.get("cProd") or "").strip(),
            "cEAN":  str(p.get("cEAN") or "").strip(),
            "xProd": str(p.get("xProd") or "").strip(),
            "vProd": _D(p.get("vProd")),
        })
    for row in pedido_rows:
        cod = str(row.get("codigo") or row.get("cprod") or "").strip()
        desc= str(row.get("descricao") or "").strip()
        vunit = _D(row.get("vunit") or row.get("valor") or "0")
        qtd   = _D(row.get("quantidade") or "0")
        vtotal= (vunit * qtd).quantize(Decimal("0.01")) if (vunit>0 and qtd>0) else None

        match = next((x for x in norm if x["cProd"] == cod or (cod and x["cEAN"] == cod)), None)
        if not match:
            out.append({"tipo": "produto_nao_encontrado", "msg": f"Produto do pedido '{desc or cod}' não encontrado na NF"})
            continue
        if vtotal is not None and not _isclose(match["vProd"], vtotal, rel_tol=0.01):
            out.append({
                "tipo": "valor_divergente",
                "msg": f"Produto '{match['xProd']}' com vProd {match['vProd']:.2f} difere do pedido {vtotal:.2f}",
                "xml": {"xProd": match["xProd"]},
                "pedido": {"descricao": desc, "valor_total": f"{vtotal:.2f}"},
            })
    return out

# === Função principal, compatível com scan_app_xml ===
def auditar_nfe_inline(
    extracted: dict,
    uf_emit: str,
    uf_dest: str,
    pedido_rows: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    emit  = extracted.get("emit", {}) or {}
    itens = extracted.get("itens", []) or []   # <— usa 'itens' (novo)
    totais= extracted.get("totais", {}) or {}  # <— usa 'totais' (novo)

    itens_out: List[Dict[str, Any]] = []
    soma_itens_vprod = Decimal("0.00")

    for it in itens:
        prod = it.get("prod", {}) or {}
        soma_itens_vprod += _D(prod.get("vProd"))

        res = _auditar_impostos_item_compat(it, emit=emit)
        # modelo para a UI do scan: cada item com nItem/xProd/achados
        itens_out.append({
            "nItem": it.get("nItem"),
            "xProd": prod.get("xProd"),
            "achados": res.get("achados", []),
        })

    achados_totais = auditar_totais(totais, soma_itens_vprod)
    diffs_pedido   = _auditar_pedido(itens, pedido_rows)

    total_flags = sum(len(i["achados"]) for i in itens_out) + len(achados_totais) + len(diffs_pedido)
    score = "BAIXO"
    if total_flags > 10:
        score = "ALTO"
    elif total_flags > 3:
        score = "MÉDIO"

    return {
        "itens": itens_out,
        "totais": achados_totais,
        "pedido": diffs_pedido,
        "score": score,
    }
