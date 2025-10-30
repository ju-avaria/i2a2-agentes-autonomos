# agent_cfop_service.py — heurística forte + LLM opcional + CONSENSO + REGRAS DURAS
# v1.4 — se houver CRÍTICO: action="bloquear" + CFOP_sugerido; mantém compat com front antigo.

import os, json, re
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import urllib.request, urllib.error

# ========================= Config =========================
HF_TOKEN = os.getenv("HUGGINGFACE_API_KEY", "")
HF_MODEL = os.getenv("HF_MODEL", "microsoft/Phi-3.5-mini-instruct")
HF_URL   = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HF_TEMPERATURE = float(os.getenv("HF_TEMPERATURE", "0.0"))
HF_MAX_NEW_TOKENS = int(os.getenv("HF_MAX_NEW_TOKENS", "220"))

USE_LLM_DEFAULT = bool(HF_TOKEN)  # se não houver token, LLM fica off por padrão
CFOP_TXT_PATH   = os.getenv("CFOP_TXT_PATH", "cfop.txt")

SERVICE_VERSION = "1.4.0"

# ========================= Schemas =========================
class Item(BaseModel):
    nItem: Optional[int] = None
    xProd: str
    CFOP: str
    NCM: Optional[str] = ""
    ICMS: Dict[str, Any] = Field(default_factory=dict)

class NotaPayload(BaseModel):
    emit_UF: str
    dest_UF: str
    CRT: Optional[str] = ""
    itens: List[Item]
    use_llm: Optional[bool] = None

# ========================= Utils =========================
def _dec(x) -> Decimal:
    try:
        if x is None:
            return Decimal("0")
        s = str(x).replace(",", ".")
        return Decimal(s)
    except Exception:
        return Decimal("0")

def _str(s) -> str:
    return (s or "").strip()

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

# ========================= Catálogo CFOP =========================
_CFOP_MAP: Dict[str, str] = {}

def load_cfop_txt(path: str) -> Dict[str, str]:
    """
    Lê um arquivo texto no formato:
      5101; Venda de produção do estabelecimento
      5102; Venda de mercadoria adquirida/recebida de terceiros
    Retorna dict { "5101": "desc", ... }
    """
    mapping: Dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                parts = [p.strip() for p in re.split(r"[;,\t]\s*", ln, maxsplit=1)]
                if len(parts) == 2 and re.fullmatch(r"\d{4}", parts[0]):
                    mapping[parts[0]] = parts[1]
    except FileNotFoundError:
        # Fallback mínimo para não quebrar sem arquivo
        mapping.update({
            "5101": "Venda de produção do estabelecimento (interna)",
            "5102": "Venda de mercadoria de terceiros (interna)",
            "6101": "Venda de produção do estabelecimento (interestadual)",
            "6102": "Venda de mercadoria de terceiros (interestadual)",
            "5301": "Prestação de serviço de comunicação (interna)",
            "6301": "Prestação de serviço de comunicação (interestadual)",
            "5551": "Venda de bem do ativo imobilizado (interna)",
            "6551": "Venda de bem do ativo imobilizado (interestadual)",
            "5556": "Venda de material de uso e consumo (interna)",
            "6556": "Venda de material de uso e consumo (interestadual)",
            "2910": "Remessa em bonificação/doação",
            "5910": "Remessa em bonificação/doação (interna)",
            "6910": "Remessa em bonificação/doação (interestadual)",
            "2911": "Remessa de amostra",
            "5911": "Remessa de amostra (interna)",
            "6911": "Remessa de amostra (interestadual)",
            "2912": "Remessa para demonstração",
            "5912": "Remessa para demonstração (interna)",
            "6912": "Remessa para demonstração (interestadual)",
            "5251": "Fornecimento de energia elétrica (interna)",
            "2651": "Venda de combustível ou lubrificante (dentro do Estado)",
            "3651": "Venda de combustível ou lubrificante (fora do Estado)",
            "1501": "Entrada de insumo destinado à industrialização",
            "2501": "Entrada de insumo (interestadual) destinado à industrialização",
            "5501": "Remessa para industrialização (interna)",
            "6501": "Remessa para industrialização (interestadual)",
            "7101": "Venda para o exterior",
            "7501": "Exportação direta",
        })
    return mapping

def _cfop_desc(cfop: str) -> str:
    global _CFOP_MAP
    if not _CFOP_MAP:
        try:
            _CFOP_MAP = load_cfop_txt(CFOP_TXT_PATH)
        except Exception:
            _CFOP_MAP = {}
    return _CFOP_MAP.get(cfop, "")

# ========================= Bandeiras (natureza) =========================
def _is_exterior(uf: str) -> bool:
    uf = (uf or "").upper()
    # algumas integrações usam "EX" ou "EXT" para exterior
    return uf in {"EX", "EXT", "EXTERIOR", "ZZ"}

def _is_intra(emit_uf: str, dest_uf: str) -> bool:
    e = (emit_uf or "").upper()
    d = (dest_uf or "").upper()
    if _is_exterior(d):
        return False
    return bool(e and d and e == d)

def _cfop_nature(cfop: str) -> str:
    """
    Retorna "interna" | "inter" | "exterior" | "indef" com base no 1º dígito do CFOP.
    5xxx = interna, 6xxx = interestadual, 7xxx = exterior. Caso contrário "indef".
    """
    cfop = (cfop or "").strip()
    if len(cfop) >= 1 and cfop[0] in {"5", "6", "7"}:
        if cfop[0] == "5":
            return "interna"
        if cfop[0] == "6":
            return "inter"
        if cfop[0] == "7":
            return "exterior"
    return "indef"

def _cfop_sugere_st(cfop: str) -> bool:
    """
    Heurística bem conservadora para indicar que o CFOP costuma aparecer com ST.
    Não é regra oficial; serve apenas para levantar 'atenção' caso os campos ST venham zerados.
    - Muitos CFOPs com ST aparecem em famílias x540, x541, x542... ou com final 'xx40/xx41'
    - Também há operações típicas com combustíveis e energia que podem envolver ST.
    """
    cfop = (cfop or "").strip()
    if not re.fullmatch(r"\d{4}", cfop):
        return False
    # família 54xx/64xx/74xx costuma envolver ST (ex.: 5401, 5403, 5410, etc.)
    if cfop[1] == "4":
        return True
    # combustível e energia: segundo dígito 6 ou 2 + padrões específicos já mapeados
    if cfop in {
        "2651","2652","2653","3651","3652","3653",  # combustíveis
        "5251","5252","5253","5254","5255","5256","5257","5258",  # energia
    }:
        return True
    return False

# ========================= Heurística leve =========================
_HEUR_REGRAS: Dict[str, List[str]] = {
    "imobiliz": ["2551","3551","5551","6551"],
    "ativo imobil": ["2551","3551","5551","6551"],
    "uso e consumo": ["2556","3556","5556","6556"],
    "consumo": ["2556","3556","5556","6556"],
    "energia": ["5251","5252","5253","5254","5255","5256","5257","5258"],
    "combust": ["2651","2652","2653","3651","3652","3653"],
    "bonifica": ["2910","5910","6910"],
    "doaç": ["2910","5910","6910"],
    "amostra": ["2911","5911","6911"],
    "demonstra": ["2912","2913","5912","5913","6912","6913"],
    "devolu": ["5201","5202","3201","3202","5410","5411","2411","2414","2415"],
    "industrial": ["5101","6101","5124","6124"],
    "transfer": ["5151","5152","5155","5156"],
    "exporta": ["5501","5502","7101","7102","7501","7502"],
    "venda": ["5101","5102","6101","6102"],
    "servi": ["5301","5303","5307","6301","6303","6307","7301","7303","7307"],
}

_TERMS_ATIVO = ("máquina","equip","veículo","imobiliz","mobiliár","servidor","notebook",
                "desktop","cadeira","mesa","impressora","roteador","switch","rack","no-break","nobreak")
_TERMS_CONSUMO = ("descartável","papel","tinta","cartucho","caneta","parafuso","detergente",
                  "limpeza","copinho","copo","café","pano","sabonete")
_TERMS_BONIF  = ("bonific","brinde","doaç","gratuito","sem custo","sem valor")
_TERMS_AMOST  = ("amostra","sample")
_TERMS_DEMONS = ("demonstra","demo")
_TERMS_ENERG  = ("energia","kwh","energia elétrica","tarifa")
_TERMS_COMB   = ("diesel","gasolina","etanol","gás veicular","gnv","combust")
_TERMS_SERV   = ("serviç","instala","manuten","assessoria","consultoria","licença","suporte")

_TERMS_PROD_ACAB = (
    "fonte","monitor","teclado","mouse","gabinete","ssd","hd","hdd","placa de vídeo",
    "gpu","placa-mãe","motherboard","memória","ram","switch","roteador","notebook",
    "desktop","cpu","processador","cooler","headset","webcam"
)
_TERMS_INDUSTRIAL = (
    "matéria-prima","materia-prima","mp","insumo","granulado","resina","bobina",
    "lingote","barra bruta","chapas","lote químico","composto químico","produto intermediário",
    "pigmento","aditivo","pellet","partida","base química"
)

def _naturalidade_compat(emit_uf: str, dest_uf: str, cfop: str) -> bool:
    nat = _cfop_nature(cfop)
    if nat.endswith("interna") and not _is_intra(emit_uf, dest_uf):
        return False
    if nat.endswith("inter") and _is_intra(emit_uf, dest_uf):
        return False
    if nat.endswith("exterior") and not _is_exterior(dest_uf):
        return False
    return True

def _hints_cfop_by_ncm(ncm: str, xprod: str) -> List[str]:
    ncm = (ncm or "").strip()
    prod = _norm(xprod)
    hints: List[str] = []
    if len(ncm) >= 2 and ncm[:2] in {"84","85"} and any(t in prod for t in _TERMS_ATIVO):
        hints += ["2551","3551","5551","6551"]
    return hints

def _heuristica_item(emit_uf: str, dest_uf: str, xprod: str, ncm: str, cfop: str) -> Dict[str, Any]:
    prod = _norm(xprod)
    sinais: List[str] = []
    coerente = False

    for termo, grupos in _HEUR_REGRAS.items():
        if termo in prod:
            if any(cfop.startswith(g[:2]) or cfop == g for g in grupos):
                coerente = True
                sinais.append(f"ok:{termo}→{grupos}")
            else:
                sinais.append(f"sugere:{termo}→{grupos}, cfop={cfop}")

    hints = _hints_cfop_by_ncm(ncm, xprod)
    if hints:
        if any(cfop.startswith(h[:2]) or cfop == h for h in hints):
            coerente = True
            sinais.append(f"ok:NCM→{hints}")
        else:
            sinais.append(f"sugere:NCM→{hints}, cfop={cfop}")

    nat_ok = _naturalidade_compat(emit_uf, dest_uf, cfop)
    if not nat_ok:
        sinais.append("nat:incompatível (UF × CFOP)")
    else:
        sinais.append("nat:ok")

    return {
        "coerente": coerente and nat_ok,
        "sinais": sinais,
        "nat_ok": nat_ok,
        "cfop_desc": _cfop_desc(cfop),
    }

# ========================= LLM =========================
def _hf_call(prompt: str) -> str:
    if not HF_TOKEN:
        raise RuntimeError("HUGGINGFACE_API_KEY ausente")
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": HF_MAX_NEW_TOKENS, "temperature": HF_TEMPERATURE}}
    req = urllib.request.Request(
        HF_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    if isinstance(data, list) and data and "generated_text" in data[0]:
        return data[0]["generated_text"]
    if isinstance(data, dict) and "generated_text" in data:
        return data["generated_text"]
    return json.dumps(data)

def _prompt_llm(payload: Dict[str, Any], item: Item, candidates: List[str]) -> str:
    cfop_desc = {c: _cfop_desc(c) for c in candidates}
    rules = (
        "Regras DURAS (siga à risca):\n"
        "- 5xxx: operação interna; 6xxx: interestadual; 7xxx: exterior.\n"
        "- x551 (ativo imobilizado) exige bem durável.\n"
        "- x556 (uso/consumo) não deve aparentar ativo.\n"
        "- x501 (industrialização) requer termos de insumo/matéria-prima; NÃO aceite produto acabado.\n"
        "- 5101/5102/6101/6102 = venda/compra comum; não aceite serviço puro nem ativo imobilizado.\n"
        "- 53xx/63xx/73xx = serviços; precisa termos de serviço.\n"
        "- 2910/5910/6910 bonificação/doação; 2911/5911/6911 amostra; 2912/2913/59xx/69xx demonstração.\n"
        "- 525x energia; 265x/365x combustíveis.\n"
        "- Não presuma ST sem evidência."
    )
    j = {
        "emit_UF": payload["emit_UF"],
        "dest_UF": payload["dest_UF"],
        "CRT": payload.get("CRT",""),
        "item": {"xProd": item.xProd, "NCM": item.NCM, "CFOP_informado": item.CFOP, "ICMS": item.ICMS},
        "candidates": [{"cfop": c, "desc": cfop_desc.get(c,"")} for c in candidates],
        "saida": {"coerente":"bool","gravidade":"COERENTE|ATENCAO|INCOERENTE","conf":"0..1","motivos":"[str]"}
    }
    return (
        "Você é AUDITOR FISCAL. Analise o JSON e decida a COERÊNCIA do CFOP informado frente ao produto.\n"
        "Responda APENAS com um JSON de uma linha:\n"
        "{\"coerente\":true|false,\"gravidade\":\"COERENTE|ATENCAO|INCOERENTE\",\"conf\":0.0,\"motivos\":[\"...\",\"...\"]}\n\n"
        f"{rules}\n\nJSON:\n{json.dumps(j, ensure_ascii=False)}"
    )

def _build_candidates(emit_uf: str, dest_uf: str, xprod: str, ncm: str, cfop_inf: str) -> List[str]:
    base: List[str] = []
    if _is_exterior(dest_uf):
        fams = ("7",)
    elif _is_intra(emit_uf, dest_uf):
        fams = ("5",)
    else:
        fams = ("6",)
    for fam in fams:
        base += [c for c in _cfop_keys() if c.startswith(fam)]

    prod = _norm(xprod)
    sugest: List[str] = []
    for termo, grupos in _HEUR_REGRAS.items():
        if termo in prod:
            sugest += grupos
    sugest += _hints_cfop_by_ncm(ncm, xprod)

    inter = [c for c in sugest if c in base]
    cand = inter or base
    uniq: List[str] = []
    for c in cand:
        if c not in uniq:
            uniq.append(c)
        if len(uniq) >= 25:
            break
    if cfop_inf and cfop_inf not in uniq:
        uniq.insert(0, cfop_inf)
    return uniq

def _cfop_keys() -> List[str]:
    if not _CFOP_MAP:
        try:
            _CFOP_MAP.update(load_cfop_txt(CFOP_TXT_PATH))
        except Exception:
            pass
    return list(_CFOP_MAP.keys())

def _run_llm(payload: Dict[str, Any], item: Item, candidates: List[str]) -> Dict[str, Any]:
    try:
        out = _hf_call(_prompt_llm(payload, item, candidates))
        m = re.search(r'\{.*\}', out, flags=re.S)
        txt = m.group(0) if m else out
        data = json.loads(txt)
        return {
            "coerente": bool(data.get("coerente", False)),
            "gravidade": (data.get("gravidade") or "").upper(),
            "conf": float(data.get("conf", 0.0)),
            "motivos": data.get("motivos", []),
            "raw": out[:800]
        }
    except Exception as e:
        return {"coerente": False, "gravidade": "ATENCAO", "conf": 0.0, "motivos": [f"LLM_ERROR:{e}"], "raw": ""}

# ========================= Regras Duras (server-side) =========================
_CFOP_ATIVO = {"1551","2551","3551","5551","6551"}
_CFOP_CONS  = {"1556","2556","3556","5556","6556"}
_CFOP_BONIF = {"2910","5910","6910"}
_CFOP_AMOST = {"2911","5911","6911"}
_CFOP_DEMON = {"2912","2913","5912","5913","6912","6913"}
_CFOP_ENERG = {"5251","5252","5253","5254","5255","5256","5257","5258"}
_CFOP_COMB  = {"2651","2652","2653","3651","3652","3653"}

_CFOP_INDUSTRIAL_X501 = {"1501","2501","3501","5501","6501"}
_CFOP_VENDA_COMUM     = {"5101","5102","6101","6102"}

def _apply_hard_rules(emit_uf: str, dest_uf: str, it: Item) -> List[Dict[str,str]]:
    ach: List[Dict[str,str]] = []
    cfop = _str(it.CFOP)
    prod = _norm(it.xProd)

    if not _naturalidade_compat(emit_uf, dest_uf, cfop):
        ach.append({"nivel":"CRITICO","regra":"CFOP_INCONSISTENTE_UF","msg":"CFOP conflita com a natureza da operação (UF × CFOP)."})

    if cfop in _CFOP_ATIVO and not any(t in prod for t in _TERMS_ATIVO):
        ach.append({"nivel":"CRITICO","regra":"CFOP_X551_ATIVO_INVEROSSIMIL","msg":"x551: descrição não aparenta bem de ativo imobilizado."})

    if cfop in _CFOP_CONS:
        if any(t in prod for t in _TERMS_ATIVO):
            ach.append({"nivel":"CRITICO","regra":"CFOP_X556_PARECE_ATIVO","msg":"x556: uso/consumo mas descrição aparenta ativo."})
        elif not any(t in prod for t in _TERMS_CONSUMO) and len(prod) < 6:
            ach.append({"nivel":"ALERTA","regra":"CFOP_X556_DESC_POBRE","msg":"x556: descrição pobre para uso/consumo."})

    if cfop in _CFOP_BONIF and not any(t in prod for t in _TERMS_BONIF):
        ach.append({"nivel":"ALERTA","regra":"CFOP_59_69_BONIF_TERMO_AUSENTE","msg":"Bonificação/doação sem termos típicos."})
    if cfop in _CFOP_AMOST and not any(t in prod for t in _TERMS_AMOST):
        ach.append({"nivel":"ALERTA","regra":"CFOP_59_69_AMOSTRA_TERMO_AUSENTE","msg":"Amostra sem termo 'amostra'."})
    if cfop in _CFOP_DEMON and not any(t in prod for t in _TERMS_DEMONS):
        ach.append({"nivel":"ALERTA","regra":"CFOP_59_69_DEMONS_TERMO_AUSENTE","msg":"Demonstração sem indicar demonstração."})

    if cfop in _CFOP_ENERG and not any(t in prod for t in _TERMS_ENERG):
        ach.append({"nivel":"CRITICO","regra":"CFOP_525X_NAO_PARECE_ENERGIA","msg":"525x: não aparenta energia elétrica."})
    if cfop in _CFOP_COMB and not any(t in prod for t in _TERMS_COMB):
        ach.append({"nivel":"CRITICO","regra":"CFOP_26_36XX_NAO_PARECE_COMBUSTIVEL","msg":"26/36xx: não aparenta combustível."})

    if cfop and cfop[0] in {"5","6","7"} and cfop[1:3] == "30":
        if not any(t in prod for t in _TERMS_SERV):
            ach.append({"nivel":"CRITICO","regra":"CFOP_53_63_73XX_SERVICO_TERMO_AUSENTE","msg":"Serviço sem termos típicos de serviço."})

    if cfop in _CFOP_INDUSTRIAL_X501:
        if any(t in prod for t in _TERMS_PROD_ACAB) and not any(t in prod for t in _TERMS_INDUSTRIAL):
            ach.append({"nivel":"CRITICO","regra":"CFOP_X501_NAO_PARECE_INSUMO","msg":"x501: parece produto acabado, não insumo."})

    if cfop in _CFOP_VENDA_COMUM:
        if any(t in prod for t in _TERMS_SERV):
            ach.append({"nivel":"CRITICO","regra":"CFOP_5101_6101_SERVICO_INADEQUADO","msg":"Venda comum mas descrição aparenta serviço."})
        if any(t in prod for t in _TERMS_ATIVO):
            ach.append({"nivel":"ALERTA","regra":"CFOP_5101_6101_PARECE_ATIVO","msg":"Parece ativo; avaliar x551."})

    return ach

# ========================= ST severity =========================
def _avaliar_st(icms: Dict[str,Any], cfop: str) -> Dict[str, Any]:
    if not _cfop_sugere_st(cfop):
        return {"nivel":"OK","msg":"—"}
    vBCST = _dec(icms.get("vBCST")); pICMSST = _dec(icms.get("pICMSST")); vICMSST = _dec(icms.get("vICMSST"))
    cst = _str(icms.get("CST")) + _str(icms.get("CSOSN"))
    evidencia_st = any(c in cst for c in ("60","70","201","202","203","500"))
    falta_st = (vBCST <= 0 or pICMSST <= 0 or vICMSST <= 0)
    if evidencia_st and falta_st:
        return {"nivel":"CRITICO","msg":"Sinais de ST, mas campos ST ausentes/zerados."}
    if (not evidencia_st) and falta_st:
        return {"nivel":"ALERTA","msg":"CFOP sugere ST, mas sem evidência tributária de ST."}
    return {"nivel":"OK","msg":"—"}

def _nota_item_score(achados: List[Dict[str,str]]) -> int:
    score = 0
    for a in achados:
        if a["nivel"] == "CRITICO": score += 40
        elif a["nivel"] == "ALERTA": score += 15
    return score

# ========================= Sugestão de CFOP =========================
def _sugerir_cfop(emit_uf: str, dest_uf: str, prod_low: str) -> str:
    intra = _is_intra(emit_uf, dest_uf)
    if any(t in prod_low for t in _TERMS_ATIVO):
        return "5551" if intra else "6551"
    if any(t in prod_low for t in _TERMS_SERV):
        return "5301" if intra else "6301"
    if any(t in prod_low for t in _TERMS_PROD_ACAB):
        return "5102" if intra else "6102"
    return "5101" if intra else "6101"

# ========================= API =========================
app = FastAPI(title="Agente CFOP (heurística + LLM + regras duras)", version=SERVICE_VERSION)

# CORS para dev local (ajuste se necessário)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "use_llm_default": USE_LLM_DEFAULT, "model": HF_MODEL if HF_TOKEN else None}

@app.get("/version")
def version():
    return {"version": SERVICE_VERSION}

@app.post("/classify")
def classify(nota: NotaPayload):
    if not nota.itens:
        return {"use_llm": bool(nota.use_llm), "score": 0, "itens": [], "error": "NO_ITEMS_IN_PAYLOAD"}

    emit_UF = _str(nota.emit_UF); dest_UF = _str(nota.dest_UF)
    use_llm = USE_LLM_DEFAULT if nota.use_llm is None else bool(nota.use_llm)
    # se não tiver token, força LLM off
    if use_llm and not HF_TOKEN:
        use_llm = False

    itens_out: List[Dict[str, Any]] = []
    total_score = 0

    for it in nota.itens:
        cfop_inf = _str(it.CFOP)
        xprod = _str(it.xProd)
        ncm = _str(it.NCM)
        icms = it.ICMS or {}

        heur = _heuristica_item(emit_UF, dest_UF, xprod, ncm, cfop_inf)

        llm = {"coerente": False, "gravidade": "ATENCAO", "conf": 0.0, "motivos": [], "raw": ""}
        cands = _build_candidates(emit_UF, dest_UF, xprod, ncm, cfop_inf)
        if use_llm and HF_TOKEN:
            llm = _run_llm(nota.model_dump(), it, cands)

        hard = _apply_hard_rules(emit_UF, dest_UF, it)

        st_eval = _avaliar_st(icms, cfop_inf)
        if st_eval["nivel"] != "OK":
            hard.append({"nivel": st_eval["nivel"], "regra": "CFOP_ST_CAMPOS", "msg": st_eval["msg"]})

        chosen = cfop_inf
        decision_action = "manter"
        reasons: List[str] = []

        has_hard_crit = any(a.get("nivel") == "CRITICO" for a in hard)
        has_hard_alt  = any(a.get("nivel") == "ALERTA" for a in hard)

        prod_low = xprod.lower()
        cfop_sugerido = ""

        if has_hard_crit:
            decision_action = "bloquear"
            cfop_sugerido = _sugerir_cfop(emit_UF, dest_UF, prod_low)
            reasons.append("Regras duras: conflito grave")
        elif llm["gravidade"] == "INCOERENTE" or (llm["coerente"] is False and llm["conf"] >= 0.6):
            decision_action = "rever"
            reasons.append("LLM indica incoerência com confiança moderada")
        elif heur["coerente"]:
            decision_action = "manter"
            reasons.append("Heurística: coerente e natureza ok")
        else:
            decision_action = "rever"
            if has_hard_alt or llm["gravidade"] == "ATENCAO" or llm["conf"] < 0.6:
                reasons.append("Sinais fracos/ambíguos — atenção")

        achados = hard[:]
        if not heur["nat_ok"] and not any(a.get("regra") == "CFOP_INCONSISTENTE_UF" for a in achados):
            achados.append({"nivel":"ALERTA","regra":"CFOP_INCONSISTENTE_UF","msg":"CFOP conflita com a natureza da operação (UF × CFOP)."})

        if any(a["nivel"] == "CRITICO" for a in achados):
            final_badge = "INCOERENTE"
        elif any(a["nivel"] == "ALERTA" for a in achados):
            final_badge = "ATENÇÃO"
        else:
            final_badge = "COERENTE"

        item_score = _nota_item_score(achados)
        total_score += item_score

        itens_out.append({
            "nItem": it.nItem,
            "xProd": xprod,
            "NCM": ncm,
            "CFOP_informado": cfop_inf,
            "CFOP_escolhido": chosen,
            "CFOP_sugerido": cfop_sugerido,      # << NOVO
            "cfop_desc": _cfop_desc(chosen),
            "decision": {
                "action": decision_action,       # manter | rever | bloquear
                "confidence": round(float(llm.get("conf", 0.0)), 2),
                "reasons": reasons,
                "heuristica": {"coerente": heur["coerente"], "sinais": heur["sinais"]},
                "llm": {"used": bool(use_llm and HF_TOKEN), "raw_excerpt": (llm.get("raw","")[:240] if llm else "")}
            },
            "achados": achados,
            "badge": final_badge,
            "score": item_score
        })

    return {"use_llm": bool(use_llm and HF_TOKEN), "score": total_score, "itens": itens_out}

# ========================= Run (opcional via uvicorn) =========================
# Execução sugerida:
#   uvicorn agent_cfop_service:app --host 0.0.0.0 --port 8010 --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent_cfop_service:app", host="0.0.0.0", port=int(os.getenv("PORT", "8010")), reload=True)
