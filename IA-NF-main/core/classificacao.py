# core/classificacao.py
from __future__ import annotations

import re
from collections import Counter
from typing import Optional

from core.ncm_taxonomy import inferir_setor_e_cc_por_ncm, inferir_tipo_basico
from core.capitulos import cap_label, ncm_to_capitulo

# --- helpers básicos ---
def _low(s): return (s or "").lower().strip()
def _only_digits(s): return re.sub(r"\D+", "", s or "")

# --- Palavras-chave úteis ---
KW_TI = ("servidor","notebook","desktop","teclado","mouse","roteador","switch","ssd","hd","fonte","placa-mãe","gpu","ram","licença","software","antivírus","firewall")
KW_OFICINA = ("óleo","pneu","amortecedor","pastilha","disco de freio","correia","filtro","bomba","embreagem","diagnóstico","alinhamento","balanceamento","mão de obra")
KW_LIMPEZA = ("detergente","desinfetante","álcool","papel toalha","sabonete","esponja","saco de lixo")
KW_ESCRITORIO = ("papel","caneta","grampeador","post-it","toner","cartucho")
KW_PRODUCAO = ("matéria-prima","insumo","bobina","resina","granulado","lingote","pigmento","chapas","lote químico","produto intermediário")
KW_AGRO = ("sementes","adubo","fertilizante","defensivo","calcário","ração","agro","agropecuário")
KW_SERVICO = ("serviço","instalação","manutenção","consultoria","assessoria","licença","suporte")

# --- Família CFOP -> tipo documento ---
def tipo_por_cfop(cfop: str) -> str:
    cf = (cfop or "").strip()
    if not cf: return "desconhecido"
    f = cf[0]
    if f in ("1","2"): return "compra"       # entradas
    if f in ("5","6"):
        if cf[1:3] == "30": return "serviço" # saídas de serviço
        return "venda"                       # saídas mercadoria
    if f == "7": return "exportacao"
    return "desconhecido"

# --- Fallback usando tpNF e descrição do produto ---
def tipo_por_contexto(tpNF: str|int, xprod: str) -> str:
    p = _low(xprod)
    if any(k in p for k in KW_SERVICO): return "serviço"
    if str(tpNF) == "0": return "compra"
    if str(tpNF) == "1": return "venda"
    return "desconhecido"

# --- Centro de custos (ajuste os mapas ao seu gosto) ---
CENTROS_REGRAS = [
    ("TI", KW_TI, (84,85)),                # 84/85 máquinas/eletrônicos
    ("Oficina", KW_OFICINA, (87,)),        # veículos/peças
    ("Limpeza", KW_LIMPEZA, (34,)),        # sabões/limpeza
    ("Escritório", KW_ESCRITORIO, (48,)),  # papelaria
    ("Produção", KW_PRODUCAO, (72,39,29)), # metal, plásticos, químicos
    ("Agro", KW_AGRO, (31,)),              # fertilizantes
]

def centro_custo_por_item(xprod: str, ncm: str) -> str:
    p = _low(xprod)
    cap = ncm_to_capitulo(ncm)
    for nome, kw_tuple, ncm_roots in CENTROS_REGRAS:
        if any(k in p for k in kw_tuple) or (cap in ncm_roots if cap is not None else False):
            return nome
    if any(k in p for k in KW_SERVICO):
        return "Servicos_Gerais"
    return "Geral"

# --- Policies por setor (agronegócio, automotivo, indústria) ---
class PolicyResult(dict): pass

def policy_agro(item) -> PolicyResult:
    cfop = (item.get("CFOP") or "").strip()
    xprod = _low(item.get("xProd"))
    ach = []
    agro_cfops_ok = {"5102","6102","5101","6101","1551","2551","5551","6551"}
    if any(s in xprod for s in ("sement","fertiliz","defensiv")) and cfop and cfop not in agro_cfops_ok:
        ach.append({"nivel":"ATENCAO","regra":"AGRO_CFOP_ATIPICO","msg":f"CFOP {cfop} fora do conjunto típico agro."})
    return PolicyResult({"setor":"agronegocio","achados":ach})

def policy_automotivo(item) -> PolicyResult:
    xprod = _low(item.get("xProd"))
    cfop = (item.get("CFOP") or "")
    ach = []
    if any(k in xprod for k in ("alinhamento","balanceamento","mão de obra","diagnóstico")) and cfop[:2] in ("51","61"):
        ach.append({"nivel":"CRITICO","regra":"AUTO_SERVICO_COM_CFOP_MERCADORIA","msg":"Serviço automotivo com CFOP de mercadoria; usar 53xx/63xx."})
    return PolicyResult({"setor":"automotivo","achados":ach})

def policy_industria(item) -> PolicyResult:
    xprod = _low(item.get("xProd"))
    cfop = (item.get("CFOP") or "")
    ach = []
    if any(k in xprod for k in ("matéria-prima","materia-prima","insumo","granulado","resina","bobina","pigmento","chapas","lote químico")) and cfop in ("5101","6101","5102","6102"):
        ach.append({"nivel":"ATENCAO","regra":"IND_INSUMO_VENDA_COMUM","msg":"Parece insumo; validar CFOP de industrialização (x501/x124/x125)."})
    return PolicyResult({"setor":"industria","achados":ach})

POLICIES = {
    "agronegocio": policy_agro,
    "automotivo": policy_automotivo,
    "industria": policy_industria,
}

# --- Função principal (UNIFICADA) ---
def classificar_nota(extracted: dict, setor: str | None = None) -> dict:
    """
    Consolida: heurística CFOP/descrição + inferência por NCM + capítulo.
    Retorna dict pronto para a UI.
    """
    ide = extracted.get("ide", {}) or {}
    tpNF = ide.get("tpNF", "")

    itens = extracted.get("itens", []) or []
    if not itens:
        return {
            "tipo": "desconhecido",
            "centros_custo": ["Geral"],
            "setor": setor or "",
            "achados_setor": [],
            "capitulo": None,
            "capitulo_label": "",
            "ncm_mais_frequente": "",
        }

    # 1) Inferência por NCM do 1º item (sinal fraco) + consenso por frequência
    ncms = [_only_digits((it.get("prod") or {}).get("NCM") or "") for it in itens if (it.get("prod") or {}).get("NCM")]
    ncm_freq = Counter([n for n in ncms if len(n) >= 2])
    ncm_top = ncm_freq.most_common(1)[0][0] if ncm_freq else (_only_digits((itens[0].get("prod") or {}).get("NCM") or "") if itens else "")

    setor_auto, cc_auto = inferir_setor_e_cc_por_ncm(ncm_top or "")
    setor_final = setor or setor_auto or ""

    cap = ncm_to_capitulo(ncm_top)
    cap_lbl = cap_label(cap) if cap else ""

    # 2) Tipo: combina CFOP/descrição com fallback do tpNF e inferência básica por NCM
    tipo = "desconhecido"
    for it in itens:
        p = it.get("prod", {}) or {}
        cfop = (p.get("CFOP") or "").strip()
        xprod = p.get("xProd", "")
        t = tipo_por_cfop(cfop)
        if t == "desconhecido":
            t = tipo_por_contexto(tpNF, xprod)
        if t != "desconhecido":
            tipo = t
            break

    # Fallback final por NCM
    if tipo == "desconhecido":
        tipo = inferir_tipo_basico(cap) if cap else "indefinido"
        if tipo not in ("compra","venda","serviço","exportacao"):
            tipo = tipo_por_contexto(tpNF, (itens[0].get("prod") or {}).get("xProd",""))

    # 3) Centros de custo por item + os sugeridos pela taxonomia de NCM
    centros = set(cc_auto or [])
    for it in itens:
        p = it.get("prod", {}) or {}
        centros.add(centro_custo_por_item(p.get("xProd",""), p.get("NCM","")))
    centros = sorted([c for c in centros if c]) or ["Geral"]

    # 4) Policies por setor
    achados_setor = []
    if setor_final in POLICIES:
        for it in itens:
            prod = (it.get("prod") or {})
            ach = POLICIES[setor_final]({"xProd": prod.get("xProd",""), "CFOP": (prod.get("CFOP") or "")}).get("achados", [])
            achados_setor.extend(ach)

    # 5) Correção “instrumentos musicais vs. médico (cap. 92 vs 90)”
    if cap == 92:
        achados_setor = [a for a in achados_setor if a.get("regra") != "MED_INSTRUMENTO_INDEVIDO"]

    return {
        "tipo": tipo or "desconhecido",
        "centros_custo": centros,
        "setor": setor_final,
        "achados_setor": achados_setor,
        "capitulo": cap,
        "capitulo_label": cap_lbl,
        "ncm_mais_frequente": ncm_top,
    }
