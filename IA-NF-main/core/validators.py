from __future__ import annotations
from typing import Dict, Any, List, Tuple
from decimal import Decimal

TOL = Decimal("0.05")  # tolerância de centavos

def is_cnpj(s: str) -> bool:
    c = "".join(ch for ch in (s or "") if ch.isdigit())
    return len(c) == 14

def is_chave_44(s: str) -> bool:
    c = "".join(ch for ch in (s or "") if ch.isdigit())
    return len(c) == 44

def check_totals(doc: Dict[str, Any]) -> List[Tuple[str,str]]:
    errs = []
    itens = doc.get("itens", [])
    tot = doc.get("totais", {})
    vProd_decl = tot.get("vProd") or Decimal("0")
    vNF_decl   = tot.get("vNF") or Decimal("0")

    vProd_calc = sum((it.get("vProd") or Decimal("0")) for it in itens)
    if (vProd_calc - vProd_decl).copy_abs() > TOL:
        errs.append(("TOTAL_VPROD_DIVERGENTE",
                     f"vProd soma itens={vProd_calc} ≠ declarado={vProd_decl}"))

    # regra simples para vNF (depende de impostos/deduções)
    # aqui validamos apenas que vNF >= vProd - tolerância (ajuste conforme seu cenário)
    if vNF_decl + TOL < vProd_decl:
        errs.append(("VNF_MENOR_QUE_VPROD",
                     f"vNF={vNF_decl} < vProd={vProd_decl} (tolerância {TOL})"))

    return errs

def check_cfop_uf(doc: Dict[str, Any]) -> List[Tuple[str,str]]:
    errs = []
    ide = doc.get("ide", {})
    dest = doc.get("dest", {}) or {}
    uf_dest = dest.get("enderDest",{}).get("UF") or dest.get("UF","")

    # pega CFOP do 1º item como referência (ou valide todos)
    itens = doc.get("itens", [])
    if not itens: 
        return errs
    cfop = (itens[0].get("CFOP") or "").strip()

    if not cfop:
        return errs

    # regra de exemplo (simplificada):
    # CFOP 5.xxx → operação dentro do estado, 6.xxx → fora do estado
    if cfop.startswith("5") and uf_dest and uf_dest != ide.get("UF",""):
        errs.append(("CFOP_UF_INCONSISTENTE", f"CFOP {cfop} sugere operação interna, UF destino={uf_dest}"))

    if cfop.startswith("6") and uf_dest and uf_dest == ide.get("UF",""):
        errs.append(("CFOP_UF_INCONSISTENTE", f"CFOP {cfop} sugere operação interestadual, UF destino={uf_dest}"))

    return errs

def audit_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retorna { ok: bool, issues: [(codigo,descr)], checks: {...} }
    """
    issues: List[Tuple[str,str]] = []
    tipo = doc.get("tipo")

    # cabeçalhos
    emit_cnpj = (doc.get("emit",{}).get("CNPJ") or "").strip()
    dest_cnpj = (doc.get("dest",{}).get("CNPJ") or "").strip()
    dest_cpf  = (doc.get("dest",{}).get("CPF")  or "").strip()

    if not is_cnpj(emit_cnpj):
        issues.append(("EMIT_CNPJ_INVALIDO", f"CNPJ emitente inválido: {emit_cnpj}"))

    # NF-e: chave 44; NFSe: geralmente sem essa chave
    if tipo == "NFe":
        chave = (doc.get("chave_acesso") or "").strip()
        if not is_chave_44(chave):
            issues.append(("CHAVE_44_INVALIDA", "Chave de acesso não possui 44 dígitos."))

    # destinatário pode ser CNPJ ou CPF
    if dest_cnpj and not is_cnpj(dest_cnpj):
        issues.append(("DEST_CNPJ_INVALIDO", f"CNPJ destinatário inválido: {dest_cnpj}"))
    if not dest_cnpj and (dest_cpf and len("".join(ch for ch in dest_cpf if ch.isdigit())) != 11):
        issues.append(("DEST_CPF_INVALIDO", f"CPF destinatário inválido: {dest_cpf}"))

    issues += check_totals(doc)
    issues += check_cfop_uf(doc)

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "checks": {
            "emit_cnpj": emit_cnpj,
            "dest_doc":  dest_cnpj or dest_cpf or "",
        }
    }
