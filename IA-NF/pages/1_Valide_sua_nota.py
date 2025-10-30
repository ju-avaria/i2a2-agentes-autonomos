# scan_app_xml.py — Somente XML (NF-e) • AV + EXTRAÇÃO COMPLETA + IE por UF
# Compatível com Agente CFOP v1.4 + Classificação/Arquivamento
from __future__ import annotations

import streamlit as st, json, time, io, csv, zipfile, os, re
import urllib.request, urllib.error
from decimal import Decimal, InvalidOperation
from typing import Optional

from core.dashboards import render_dashboards
from mini_av import mini_av_scan_detalhado
from extrair import extract_from_nfe_xml, valida_cnpj, valida_chave_acesso
from core.report_llm_pdf import build_llm_executive_pdf
 
# ======== Auditoria (status visível) ========
AUDITORIA_ERR = ""
try:
    from core.auditoria_inline import auditar_nfe_inline  # cálculos + códigos + pedido CSV
    AUDITORIA_ON = True
except Exception as e:
    auditar_nfe_inline = None
    AUDITORIA_ON = False
    AUDITORIA_ERR = str(e)

# Tenta usar o validador “oficial”; se não houver, cai no fallback leve
try:
    from validadores import valida_ie  # pylint: disable=import-error
except Exception:
    import re as _re
    def valida_ie(uf: str, ie: str):
        """Fallback leve para não quebrar a UI (não substitui regra fiscal real)."""
        uf = (uf or "").strip().upper()
        ie = _re.sub(r"\D+", "", ie or "")
        tamanhos = {
            "AC": 13, "AL": 9,  "AM": 9,  "AP": 9,  "BA": (8,9), "CE": 9, "DF": 13, "ES": 9,
            "GO": 9,  "MA": 9,  "MG": 13, "MS": 9,  "MT": 11,    "PA": 9, "PB": 9, "PE": 14,
            "PI": 9,  "PR": 10, "RJ": 8,  "RN": 10, "RO": (9,14), "RR": 9, "RS": 10, "SC": 9,
            "SE": 9,  "SP": (12,13), "TO": 9
        }
        ok = False
        if uf in tamanhos:
            ts = tamanhos[uf]
            ok = (len(ie) in (ts if isinstance(ts, tuple) else (ts,)))
        return {
            "uf": uf,
            "valida": bool(ok or not ie),  # IE vazia -> consideramos isento/ok para fins de UI
            "dv_calculado": "",
            "dv_real": ie[-1:] if ie else "",
            "motivo": "Validação leve por comprimento (fallback) ou contribuinte isento."
        }

# >>> Classificação + Arquivamento (fallbacks no-code para evitar quebrar)
try:
    from core.classificacao import classificar_nota
except Exception:
    def classificar_nota(extracted: dict, setor=None): return {}
try:
    from core.storage import save_note_bundle
except Exception:
    def save_note_bundle(extracted: dict, classif: dict, xml_bytes: bytes): return
try:
    from core.capitulos import cap_label, ncm_to_capitulo
except Exception:
    def cap_label(x): return ""
    def ncm_to_capitulo(x): return ""

# =================== CONFIG ===================
AGENT_URL = os.getenv("CFOP_AGENT_URL", "").strip()  # deixe vazio para forçar fallback local
AGENT_REQUIRED = os.getenv("CFOP_AGENT_REQUIRED", "false").lower() in {"1","true","yes"}

# === Fallback de alíquotas PIS/COFINS ===
# Observação: a UI (sidebar) pode sobrepor este valor em tempo de execução.
PISCOFINS_REGIME = os.getenv("REGIME_PISCOFINS", "").strip().lower()  # "real" | "presumido" | "" (auto)
PISCOFINS_DEFAULTS = {
    "real":      {"pPIS": Decimal("1.65"), "pCOFINS": Decimal("7.60")},
    "presumido": {"pPIS": Decimal("0.65"), "pCOFINS": Decimal("3.00")},
}

# ---------- Fallback seguro caso to_jsonable não esteja no extrair.py ----------
try:
    from extrair import to_jsonable
except Exception:
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

# ---------- Helpers ----------
def only_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def D(x, default="0"):
    """Decimal seguro."""
    try:
        if x is None or x == "":
            return Decimal(default)
        if isinstance(x, (int, float, Decimal)):
            return Decimal(str(x))
        return Decimal(str(x).replace(",", "."))
    except InvalidOperation:
        return Decimal(default)

def risk_label(score: int):
    if score >= 80: return "🔴 Risco ALTO — BLOQUEADO"
    if score >= 40: return "🟠 Risco MÉDIO — atenção"
    return "🟢 Risco BAIXO"

def _safe_zip_name(name: str) -> str:
    base = os.path.basename(name)
    base_no_ext = os.path.splitext(base)[0]
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in base_no_ext)
    return f"{safe}_scan_report.json"

def _as_str(v):
    if v is None: return ""
    return str(v)

def _explica_passos(nome: str) -> str:
    textos = {
        "MIME sniff": "Detecta o tipo real (ex.: application/xml).",
        "XML seguro": "Parseia o XML de forma segura.",
        "Executável/Scripts": "Bloqueia arquivos executáveis e scripts.",
        "Compactados": "Evita zip-bomb e paths perigosos.",
        "Entropia": "Sinaliza conteúdo ofuscado.",
        "YARA": "Compara com regras/assinaturas de segurança.",
    }
    return textos.get(nome, "—")

def _safe_key(prefix: str, name: str, idx: int | None = None) -> str:
    base = os.path.basename(name)
    base_no_ext = os.path.splitext(base)[0]
    safe = re.sub(r'[^A-Za-z0-9_-]+', '_', base_no_ext)[:40]
    return f"{prefix}_{idx}_{safe}" if idx is not None else f"{prefix}_{safe}"

# ===== Tabelas CST/CSOSN (resumo útil para decisão de cálculo) =====
CST_ISENTOS_NT_SUSP = {"40", "41", "50"}          # isenta / não tributada / suspensão
CSOSN_ISENTOS_NT = {"103", "300", "400", "500"}   # faixas SN imune/NT/ST/antecip

# ==================== Funções utilitárias do Agente (locais) ====================
def _http_post_json(url: str, payload: dict, timeout: float = 10.0) -> dict:
    body = json.dumps(to_jsonable(payload), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _is_intra(uf1: str, uf2: str) -> bool:
    return (uf1 or "").strip().upper() == (uf2 or "").strip().upper()

def _is_exterior(uf: str) -> bool:
    return (uf or "").strip().upper() in {"EX", "EXTERIOR", "XX"}

def _cfop_nature(cfop: str) -> str:
    cfop = (cfop or "").strip()
    if not cfop: return "desconhecida"
    if cfop[0] == "5": return "interna"
    if cfop[0] == "6": return "interestadual"
    if cfop[0] == "7": return "exterior"
    return "desconhecida"

def _cfop_sugere_st(cfop: str) -> bool:
    return (cfop or "").startswith(("5","6")) and (cfop[1:3] in {"40","41","60","61","65","66"})

def _agent_healthcheck() -> tuple[bool, str]:
    if not AGENT_URL:
        return False, "AGENT_URL vazio"
    try:
        ping_payload = {"emit_UF": "SP", "dest_UF": "SP", "CRT": "", "use_llm": False,
                        "itens": [{"nItem": 1, "xProd": "ping", "CFOP": "5101", "NCM": "", "ICMS": {}}]}
        _ = _http_post_json(AGENT_URL, ping_payload, timeout=5.0)
        return True, "OK"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"URL_ERROR: {e.reason}"
    except Exception as e:
        return False, f"GENERIC_ERROR: {e}"

def _avaliar_produto_cfop_local(emit_UF: str, dest_UF: str, itens: list[dict]) -> dict:
    out, total = [], 0
    for it in itens or []:
        p = (it.get("prod") or {})
        imp = (it.get("imposto") or {})
        icms = (imp.get("ICMS") or {})
        xprod = (p.get("xProd") or "")
        cfop  = (p.get("CFOP") or "")
        ncm   = (p.get("NCM") or "")

        achados = []
        nat = _cfop_nature(cfop)
        if nat == "interna" and not _is_intra(emit_UF, dest_UF):
            achados.append({"nivel":"CRITICO","regra":"CFOP_INCONSISTENTE_UF","msg":"CFOP interno mas UF diferente"})
        if nat == "interestadual" and _is_intra(emit_UF, dest_UF):
            achados.append({"nivel":"CRITICO","regra":"CFOP_INCONSISTENTE_UF","msg":"CFOP interestadual mas mesma UF"})
        if nat == "exterior" and not _is_exterior(dest_UF):
            achados.append({"nivel":"CRITICO","regra":"CFOP_EXTERIOR_INCOMPATIVEL","msg":"CFOP exterior mas destino não é exterior"})

        if _cfop_sugere_st(cfop):
            vBCST = (icms.get("vBCST") or "0")
            vICMSST = (icms.get("vICMSST") or "0")
            if str(vBCST) in {"","0","0.0"} or str(vICMSST) in {"","0","0.0"}:
                achados.append({"nivel":"ALERTA","regra":"ST_POSSIVEL_SEM_CAMPOS","msg":"CFOP sugere ST mas campos ST ausentes/zerados"})

        if any(a["nivel"] == "CRITICO" for a in achados): badge, item_score = "INCOERENTE", 40
        elif any(a["nivel"] == "ALERTA" for a in achados): badge, item_score = "ATENÇÃO", 15
        else: badge, item_score = "COERENTE", 0
        total += item_score

        out.append({
            "nItem": it.get("nItem"),
            "xProd": xprod,
            "NCM": ncm,
            "CFOP_informado": cfop,
            "CFOP_escolhido": cfop,
            "CFOP_sugerido": "",
            "cfop_desc": "",
            "decision": {"action": "rever" if badge != "COERENTE" else "manter", "confidence": 0.0, "reasons": ["fallback_local"]},
            "achados": achados, "badge": badge, "score": item_score
        })
    return {"use_llm": False, "score": total, "itens": out}

def _consultar_agente_coerencia(ender_emit: dict, ender_dest: dict, emit: dict, itens: list, use_llm: bool = True):
    emit_UF = (ender_emit or {}).get("UF", "") or ""
    dest_UF = (ender_dest or {}).get("UF", "") or ""

    agent_up, reason = _agent_healthcheck()
    st.caption(f"Agente CFOP: {'🟢 online' if agent_up else '🔴 offline'} ({reason})")

    payload = {
        "emit_UF": emit_UF, "dest_UF": dest_UF,
        "CRT": (emit or {}).get("CRT", "") or "",
        "use_llm": bool(use_llm), "itens": []
    }
    for it in itens or []:
        p = (it.get("prod") or {}) if isinstance(it, dict) else {}
        icms = ((it.get("imposto") or {}).get("ICMS") or {}) if isinstance(it, dict) else {}
        payload["itens"].append({
            "nItem": it.get("nItem"),
            "xProd": p.get("xProd", ""), "CFOP":  p.get("CFOP", ""),
            "NCM":   p.get("NCM", ""),
            "ICMS": {
                "CST": icms.get("CST",""), "CSOSN": icms.get("CSOSN",""),
                "vBC": icms.get("vBC",""), "pICMS": icms.get("pICMS",""),
                "vICMS": icms.get("vICMS",""), "pRedBC": icms.get("pRedBC",""),
                "vBCST": icms.get("vBCST",""), "pICMSST": icms.get("pICMSST",""),
                "vICMSST": icms.get("vICMSST",""),
            }
        })

    if agent_up and AGENT_URL:
        try:
            return _http_post_json(AGENT_URL, payload, timeout=15.0)
        except Exception as e:
            if AGENT_REQUIRED:
                return {"error": f"AGENT_REQUIRED_FAIL: {e}"}
            return _avaliar_produto_cfop_local(emit_UF, dest_UF, itens)
    else:
        if AGENT_REQUIRED:
            return {"error": f"AGENT_REQUIRED_FAIL: {reason}"}
        return _avaliar_produto_cfop_local(emit_UF, dest_UF, itens)

# ======== Fallback PIS/COFINS por regime ========
def _fallback_pis_cofins_rates(emit: dict) -> Optional[tuple[Decimal, Decimal]]:
    """
    Decide alíquotas padrão quando o XML não traz pPIS/pCOFINS.
    - Se CRT in {"1","2"} (Simples): não aplica fallback (retorna None).
    - Se PISCOFINS_REGIME estiver definido (real/presumido): usa esse.
    - Caso contrário, None (preferir o que vier no XML).
    """
    crt = str((emit or {}).get("CRT","")).strip()
    if crt in {"1","2"}:
        return None
    regime = PISCOFINS_REGIME if PISCOFINS_REGIME in {"real","presumido"} else ""
    if not regime:
        return None
    d = PISCOFINS_DEFAULTS[regime]
    return d["pPIS"], d["pCOFINS"]

# ===== Recálculo de impostos (próximo do real) =====
def _calc_icms_base(prod: dict, icms: dict, ipi: dict) -> Decimal:
    vbc_xml = D(icms.get("vBC"))
    if vbc_xml > 0:
        base = vbc_xml
    else:
        vProd = D(prod.get("vProd")); vDesc = D(prod.get("vDesc"))
        vFrete = D(prod.get("vFrete")); vSeg = D(prod.get("vSeg")); vOutro = D(prod.get("vOutro"))
        base = (vProd - vDesc + vFrete + vSeg + vOutro)
        vIPI = D((ipi or {}).get("vIPI"))
        if vIPI > 0:
            base += vIPI
    pRed = D(icms.get("pRedBC"))
    if pRed > 0:
        base = base * (Decimal("1") - (pRed/Decimal("100")))
    return base if base >= 0 else Decimal("0")

def _calc_pis_cofins_base(prod: dict, ipi: dict | None = None) -> Decimal:
    """Base **idêntica** para PIS e COFINS quando vBC não vier no XML."""
    vProd = D(prod.get("vProd"))
    vDesc = D(prod.get("vDesc"))
    vFrete = D(prod.get("vFrete"))
    vSeg = D(prod.get("vSeg"))
    vOutro = D(prod.get("vOutro"))
    vIPI = D(ipi.get("vIPI")) if ipi else Decimal("0")
    base = (vProd - vDesc + vFrete + vSeg + vOutro + vIPI)
    return base if base >= 0 else Decimal("0")

def _format_money(x: Decimal) -> str:
    return f"{x.quantize(Decimal('0.01'))}"

def _cst_csosn_rotulo(icms: dict) -> str:
    cst = (icms.get("CST") or "").strip()
    csn = (icms.get("CSOSN") or "").strip()
    return f"CST {cst}" if cst else (f"CSOSN {csn}" if csn else "")

def _is_isento_nt_susp(icms: dict) -> bool:
    cst = (icms.get("CST") or "").strip()
    csn = (icms.get("CSOSN") or "").strip()
    if cst in CST_ISENTOS_NT_SUSP: return True
    if csn in CSOSN_ISENTOS_NT: return True
    return False

def _build_recalculo_rows(itens: list[dict], emit: dict | None = None) -> tuple[list[dict], bool]:
    rows, any_diff = [], False
    ppis_fallback, pcof_fallback = (None, None)
    if emit is not None:
        fb = _fallback_pis_cofins_rates(emit)
        if fb:
            ppis_fallback, pcof_fallback = fb

    for it in itens or []:
        prod = it.get("prod", {}) or {}
        imp  = it.get("imposto", {}) or {}
        icms = imp.get("ICMS", {}) or {}
        ipi  = imp.get("IPI", {}) or {}
        pis  = imp.get("PIS", {}) or {}
        cof  = imp.get("COFINS", {}) or {}

        xProd = prod.get("xProd","")
        nItem = it.get("nItem","")
        rotulo_icms = _cst_csosn_rotulo(icms)

        # Base única derivada para PIS/COFINS quando vBC está ausente
        _base_pc_derivada = _calc_pis_cofins_base(prod, ipi)

        # === ICMS ===
        if _is_isento_nt_susp(icms) or icms.get("vICMS") in (None, ""):
            rows.append({
                "nItem": nItem, "Produto": xProd, "Tributo": f"ICMS ({rotulo_icms or '-'})",
                "vBC(calc)": "-", "Alíquota(%)": "-", "Valor calc.": "-",
                "Valor XML": icms.get("vICMS","-"), "Diferença": "-", "Obs": "Isento/NT/Susp. ou não informado"
            })
        else:
            base_icms = _calc_icms_base(prod, icms, ipi)
            pICMS = D(icms.get("pICMS"))
            vICMS_calc = (base_icms * (pICMS/Decimal("100"))).quantize(Decimal("0.01"))
            vICMS_xml  = D(icms.get("vICMS"))
            dif = (vICMS_calc - vICMS_xml).quantize(Decimal("0.01"))
            any_diff = any_diff or (abs(dif) != Decimal("0.00"))
            rows.append({
                "nItem": nItem, "Produto": xProd, "Tributo": f"ICMS ({rotulo_icms or '-'})",
                "vBC(calc)": _format_money(base_icms), "Alíquota(%)": f"{pICMS}",
                "Valor calc.": _format_money(vICMS_calc), "Valor XML": _format_money(vICMS_xml),
                "Diferença": _format_money(dif), "Obs": ""
            })

        # === PIS ===
        if pis.get("vPIS") in (None, ""):
            rows.append({
                "nItem": nItem, "Produto": xProd, "Tributo": "PIS",
                "vBC(calc)": "-", "Alíquota(%)": "-", "Valor calc.": "-",
                "Valor XML": pis.get("vPIS","-"), "Diferença": "-", "Obs": "Não informado/monofásico/0"
            })
        else:
            qPIS = D(pis.get("qPIS")); vAliqProd = D(pis.get("vAliqProd"))
            if qPIS > 0 and vAliqProd > 0:
                vPIS_calc = (qPIS * vAliqProd).quantize(Decimal("0.01"))
                base_p = qPIS; aliq_txt = f"{vAliqProd}/un"
            else:
                base_p = D(pis.get("vBC")) if pis.get("vBC") not in (None, "", "0") else _base_pc_derivada
                pPIS = D(pis.get("pPIS"))
                if pPIS <= 0 and ppis_fallback is not None:
                    pPIS = ppis_fallback
                vPIS_calc = (base_p * (pPIS/Decimal("100"))).quantize(Decimal("0.01"))
                aliq_txt = f"{pPIS}"
            vPIS_xml = D(pis.get("vPIS"))
            dif = (vPIS_calc - vPIS_xml).quantize(Decimal("0.01"))
            any_diff = any_diff or (abs(dif) != Decimal("0.00"))
            rows.append({
                "nItem": nItem, "Produto": xProd, "Tributo": "PIS",
                "vBC(calc)": _format_money(base_p) if isinstance(base_p, Decimal) else str(base_p),
                "Alíquota(%)": aliq_txt,
                "Valor calc.": _format_money(vPIS_calc), "Valor XML": _format_money(vPIS_xml),
                "Diferença": _format_money(dif), "Obs": ""
            })

        # === COFINS ===
        if cof.get("vCOFINS") in (None, ""):
            rows.append({
                "nItem": nItem, "Produto": xProd, "Tributo": "COFINS",
                "vBC(calc)": "-", "Alíquota(%)": "-", "Valor calc.": "-",
                "Valor XML": cof.get("vCOFINS","-"), "Diferença": "-", "Obs": "Não informado/monofásico/0"
            })
        else:
            qC = D(cof.get("qCOFINS")); vAliqC = D(cof.get("vAliqProd"))
            if qC > 0 and vAliqC > 0:
                vCOF_calc = (qC * vAliqC).quantize(Decimal("0.01"))
                base_c = qC; aliq_txt = f"{vAliqC}/un"
            else:
                base_c = D(cof.get("vBC")) if cof.get("vBC") not in (None, "", "0") else _base_pc_derivada
                pC = D(cof.get("pCOFINS"))
                if pC <= 0 and pcof_fallback is not None:
                    pC = pcof_fallback
                vCOF_calc = (base_c * (pC/Decimal("100"))).quantize(Decimal("0.01"))
                aliq_txt = f"{pC}"
            vCOF_xml = D(cof.get("vCOFINS"))
            dif = (vCOF_calc - vCOF_xml).quantize(Decimal("0.01"))
            any_diff = any_diff or (abs(dif) != Decimal("0.00"))
            rows.append({
                "nItem": nItem, "Produto": xProd, "Tributo": "COFINS",
                "vBC(calc)": _format_money(base_c) if isinstance(base_c, Decimal) else str(base_c),
                "Alíquota(%)": aliq_txt,
                "Valor calc.": _format_money(vCOF_calc), "Valor XML": _format_money(vCOF_xml),
                "Diferença": _format_money(dif), "Obs": ""
            })
    return rows, any_diff

# ==================== UI helpers ====================
def _status_icon(ok: bool, score: int | None = None) -> str:
    if not ok: return "❌"
    if score is None: return "✅"
    return "🟢" if score < 40 else ("🟠" if score < 80 else "🔴")

def _chip(texto: str) -> str:
    return f"<span style='padding:.25rem .6rem;border:1px solid #2F4F75;border-radius:999px;margin-right:.35rem;display:inline-block'>{texto}</span>"

# =============================== UI ===============================
st.set_page_config(page_title="🛡️ NF-e (XML)", layout="wide")
st.title("Valide sua NF-e | XML")
st.caption(f"Auditoria: {'🟢 ativa' if AUDITORIA_ON else '🔴 indisponível'}" + (f" — {AUDITORIA_ERR}" if AUDITORIA_ERR else ""))

# Sidebar: seletor de fallback do regime PIS/COFINS
with st.sidebar:
    regime_ui = st.selectbox(
        "Regime PIS/COFINS (fallback)",
        ["auto","real","presumido"],
        index={"":0,"real":1,"presumido":2}.get(PISCOFINS_REGIME,0),
        help="Usado apenas quando o XML não vier com pPIS/pCOFINS e o emitente não for Simples."
    )
# Aplicar override local (somente quando não houver pPIS/pCOFINS e não for Simples)
PISCOFINS_REGIME = "" if regime_ui == "auto" else regime_ui

# Botão para limpar sessão
if st.button("🗑️ Limpar resultados", help="Remove resultados carregados e recomeça", key="btn_clear"):
    for k in list(st.session_state.keys()):
        if k.startswith("nfe_"):
            del st.session_state[k]
    st.experimental_rerun()

# ======== Pedido CSV (opcional) ========
pedido_file = st.file_uploader(
    "Opcional: envie o **Pedido de Compra (CSV)** para reconciliação",
    type=["csv"], accept_multiple_files=False,
    help="Colunas: codigo,descricao,ncm,cfop,quantidade,vunit"
)
pedido_rows = []
if pedido_file is not None:
    try:
        reader = csv.DictReader(io.StringIO(pedido_file.read().decode("utf-8")))
        for row in reader:
            pedido_rows.append({k.strip().lower(): (v or "").strip() for k, v in row.items()})
        st.success(f"Pedido carregado com {len(pedido_rows)} linha(s).")
    except Exception as e:
        st.warning(f"Falha ao ler o pedido CSV: {e}")

files = st.file_uploader(
    "Envie 1 ou mais arquivos **XML** de NF-e (procNFe/NFe)",
    type=["xml"], accept_multiple_files=True
)
run = st.button("🔍 Escanear e Extrair (XML)", type="primary", use_container_width=True, key="btn_run")

# =================== PROCESSAMENTO ===================
if run:
    if not files:
        st.error("Envie pelo menos um arquivo XML de NF-e.")
        st.stop()

    overall = st.progress(0, text="Preparando…")
    all_results = []
    zipped_reports = io.BytesIO()
    zipbuf = zipfile.ZipFile(zipped_reports, mode="w", compression=zipfile.ZIP_DEFLATED)

    for idx, f in enumerate(files, start=1):
        name = f.name
        data = f.read()

        with st.status(f"Escaneando **{name}**…", expanded=True) as status:
            st.write("1) Lendo o arquivo…")
            time.sleep(0.05)

            report = mini_av_scan_detalhado(name, data)

            for step in report.get("steps", []):
                ok = step["ok"]; icon = "✅" if ok else "❌"
                header = f"{icon} **{step['name']}** — {step['detail']}"
                with st.expander(header, expanded=not ok):
                    st.caption(_explica_passos(step["name"]))
                time.sleep(0.01)

            passed = report.get("ok", False)
            if passed:
                status.update(label=f"{name}: aprovado ✅ — iniciando extração…", state="complete", expanded=True)
            else:
                status.update(label=f"{name}: BLOQUEADO ❌", state="error", expanded=False)

        per_file = {
            "arquivo": name, "mime": report.get("mime"), "score": report.get("score"),
            "ok": passed, "reasons": report.get("reasons", []), "steps": report.get("steps", []),
            "extraction": {}, "validations": {}, "agente": {}, "classif": {}, "auditoria": {},
        }

        extracted = {}
        if passed:
            try:
                extracted = extract_from_nfe_xml(data)
            except Exception as e:
                st.error(f"{name}: falha ao extrair dados do XML — {e}")

            if extracted:
                ide  = extracted.get("ide", {}) or {}
                emit = extracted.get("emit", {}) or {}
                dest = extracted.get("dest", {}) or {}
                itens = extracted.get("itens", []) or []

                ender_emit = emit.get("enderEmit", {}) if emit else {}
                ender_dest = dest.get("enderDest", {}) if dest else {}

                chave = (extracted.get("chave_acesso") or "").strip()
                v_chave = len(chave) == 44 and valida_chave_acesso(chave)

                emit_cnpj = only_digits(emit.get("CNPJ"))
                dest_cnpj = only_digits(dest.get("CNPJ"))
                dest_cpf  = only_digits(dest.get("CPF"))

                v_emit_cnpj = bool(emit_cnpj) and valida_cnpj(emit_cnpj)
                v_dest_doc  = (bool(dest_cnpj) and valida_cnpj(dest_cnpj)) or (len(dest_cpf) == 11)

                uf_emit = (ender_emit.get("UF") or "").strip()
                uf_dest = (ender_dest.get("UF") or "").strip()
                ie_emit = (emit.get("IE") or "").strip()
                ie_dest = (dest.get("IE") or "").strip()

                ie_emit_res = valida_ie(uf_emit, ie_emit) if (uf_emit and ie_emit) else {
                    "uf": uf_emit or "", "valida": True if not ie_emit else False,
                    "dv_calculado": "", "dv_real": ie_emit[-1:] if ie_emit else "",
                    "motivo": "Contribuinte isento ou IE ausente",
                }
                ie_dest_res = valida_ie(uf_dest, ie_dest) if (uf_dest and ie_dest) else {
                    "uf": uf_dest or "", "valida": True if not ie_dest else False,
                    "dv_calculado": "", "dv_real": ie_dest[-1:] if ie_dest else "",
                    "motivo": "Contribuinte isento ou IE ausente",
                }

                per_file["validations"] = {
                    "modelo": ide.get("mod", ""), "chave_acesso_ok": v_chave,
                    "cnpj_emitente_ok": v_emit_cnpj, "dest_ok": v_dest_doc,
                    "IE_emit": ie_emit_res, "IE_dest": ie_dest_res,
                }

                if auditar_nfe_inline:
                    try:
                        per_file["auditoria"] = auditar_nfe_inline(
                            extracted,
                            uf_emit=(ender_emit or {}).get("UF",""),
                            uf_dest=(ender_dest or {}).get("UF",""),
                            pedido_rows=pedido_rows or None
                        )
                    except Exception as e:
                        per_file["auditoria"] = {"error": f"auditoria_fail: {e}"}

                try:
                    per_file["agente"] = _consultar_agente_coerencia(ender_emit, ender_dest, emit, itens, use_llm=True)
                except Exception as e:
                    per_file["agente"] = {"error": f"agent_fail: {e}"}

                try:
                    per_file["classif"] = classificar_nota(extracted, setor=None)
                except Exception as e:
                    per_file["classif"] = {"error": f"classif_fail: {e}"}

                try:
                    save_note_bundle(extracted, per_file["classif"], data)
                except Exception as e:
                    st.warning(f"Falha ao arquivar/indexar: {e}")

        per_file["extraction"] = extracted or {}
        zipbuf.writestr(
            _safe_zip_name(name),
            json.dumps(to_jsonable(per_file), ensure_ascii=False, indent=2)
        )
        all_results.append(per_file)
        overall.progress(idx / len(files), text=f"Processados {idx}/{len(files)}")

    zipbuf.close()
    zipped_reports.seek(0)

    st.session_state["nfe_results"] = all_results
    st.session_state["nfe_zip"] = zipped_reports.getvalue()
    st.session_state["nfe_sel_name"] = all_results[0]["arquivo"] if all_results else None
    st.success("Varredura concluída (somente XML).")

# =================== RENDERIZAÇÃO (sempre que houver sessão) ===================
st.markdown("---")
if st.session_state.get("nfe_results"):
    st.subheader("Notas carregadas")
    st.download_button(
        "⬇️ Baixar relatórios (ZIP)",
        data=st.session_state.get("nfe_zip", b""),
        file_name="nfe_relatorios.zip",
        mime="application/zip",
        key="btn_relatorios_zip",
    )

    all_results = st.session_state["nfe_results"]
    opcoes = [f"{_status_icon(r.get('ok'), r.get('score'))}  {r.get('arquivo')}" for r in all_results]

    sel_name_prev = st.session_state.get("nfe_sel_name")
    sel_index = 0
    if sel_name_prev:
        for i, r in enumerate(all_results):
            if r.get("arquivo") == sel_name_prev:
                sel_index = i; break

    sel = st.radio("Selecione uma nota para ver os detalhes:",
                   opcoes, index=sel_index, label_visibility="collapsed", key="nfe_radio")
    sel_name = sel.split("  ", 1)[1] if "  " in sel else sel
    st.session_state["nfe_sel_name"] = sel_name

    selecionada = next((r for r in all_results if r.get("arquivo")==sel_name), None)
    if selecionada:
        with st.container(border=True):
            # ======= RENDER DETALHE =======
            extracted  = selecionada.get("extraction", {}) or {}
            validations= selecionada.get("validations", {}) or {}
            classif    = selecionada.get("classif", {}) or {}
            ag_resp    = selecionada.get("agente", {}) or {}
            auditoria  = selecionada.get("auditoria", {}) or {}
            report  = {"mime": selecionada.get("mime"), "score": selecionada.get("score"), "ok": selecionada.get("ok")}

            name =SelecionadaName= selecionada.get("arquivo","—")
            st.markdown(f"### {SelecionadaName}")

            cols = st.columns([1,1,1,1])
            with cols[0]: st.metric("Status AV", "Aprovado" if report["ok"] else "Bloqueado")
            with cols[1]: st.metric("MIME", report.get("mime","—"))
            with cols[2]: st.metric("Score AV", report.get("score","—"))
            with cols[3]: st.metric("Severidade", ("Baixa" if (report.get("score",0)<40) else ("Média" if report.get("score",0)<80 else "Alta")))

            emit = extracted.get("emit", {}) or {}
            dest = extracted.get("dest", {}) or {}
            e = emit.get("enderEmit", {}) if emit else {}
            d = dest.get("enderDest", {}) if dest else {}
            with st.expander("🧾 Emitente & Destinatário", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### Emitente")
                    st.write(
                        f"**{emit.get('xNome','—')}**  \n"
                        f"CNPJ/CPF: {emit.get('CNPJ') or emit.get('CPF','—')}  \n"
                        f"IE: {emit.get('IE','—')}  \n"
                        f"{e.get('xMun','')}/{e.get('UF','')}"
                    )
                with c2:
                    st.markdown("#### Destinatário")
                    st.write(
                        f"**{dest.get('xNome','—')}**  \n"
                        f"CNPJ/CPF: {dest.get('CNPJ') or dest.get('CPF','—')}  \n"
                        f"IE: {dest.get('IE','—')}  \n"
                        f"{d.get('xMun','')}/{d.get('UF','')}"
                    )

            with st.expander("🧪 Validações (Chave/CNPJ/IE)", expanded=False):
                st.json(validations)

            itens = extracted.get("itens", []) or []
            if itens:
                linhas = []
                for it in itens:
                    p = it.get("prod", {}) or {}
                    linhas.append({
                        "nItem": it.get("nItem",""), "xProd": p.get("xProd",""),
                        "CFOP":  p.get("CFOP",""), "NCM":   p.get("NCM",""),
                        "qCom":  p.get("qCom",""),  "uCom":  p.get("uCom",""),
                        "vUnCom":p.get("vUnCom",""), "vProd": p.get("vProd",""),
                    })
                with st.expander("📦 Itens", expanded=False):
                    st.dataframe(linhas, use_container_width=True, hide_index=True)

                # Impostos por item
                imp_rows = []
                for it in itens:
                    imp = it.get("imposto", {}) or {}
                    icms = imp.get("ICMS", {}) or {}
                    ipi  = imp.get("IPI", {}) or {}
                    pis  = imp.get("PIS", {}) or {}
                    cof  = imp.get("COFINS", {}) or {}
                    imp_rows.append({
                        "nItem": it.get("nItem",""),
                        "ICMS_CST/CSOSN": icms.get("CST") or icms.get("CSOSN",""),
                        "ICMS_vBC": icms.get("vBC",""), "ICMS_pICMS": icms.get("pICMS",""),
                        "ICMS_vICMS": icms.get("vICMS",""), "ICMS_pRedBC": icms.get("pRedBC",""),
                        "IPI_CST": ipi.get("CST",""), "IPI_vIPI": ipi.get("vIPI",""),
                        "PIS_CST": pis.get("CST",""),
                        "PIS_pPIS": pis.get("pPIS",""), "PIS_qPIS": pis.get("qPIS",""), "PIS_vAliqProd": pis.get("vAliqProd",""),
                        "PIS_vPIS": pis.get("vPIS",""),
                        "COFINS_CST": cof.get("CST",""),
                        "COFINS_pCOFINS": cof.get("pCOFINS",""), "COFINS_qCOFINS": cof.get("qCOFINS",""), "COFINS_vAliqProd": cof.get("vAliqProd",""),
                        "COFINS_vCOFINS": cof.get("vCOFINS",""),
                    })
                if any(imp_rows):
                    with st.expander("🧾 Impostos por item (ICMS, IPI, PIS, COFINS)", expanded=False):
                        st.dataframe(imp_rows, use_container_width=True, hide_index=True)

                # ===== Recalculo próximo do real =====
                rec_rows, any_diff = _build_recalculo_rows(itens, emit=extracted.get("emit") or {})
                with st.expander("🔁 Recalculo de Impostos (comparativo por item)", expanded=True):
                    if rec_rows:
                        st.dataframe(rec_rows, use_container_width=True, hide_index=True)
                        if any_diff:
                            st.warning("Foram encontradas diferenças entre os valores calculados e os informados no XML.")
                        else:
                            st.success("Os valores calculados coincidem com os informados no XML.")
                    else:
                        st.info("Sem itens para recalcular.")

            totais = extracted.get("totais", {}) or {}
            if totais:
                with st.expander("🧮 Totais da NF-e", expanded=False):
                    st.json({k: str(v) for k, v in totais.items()})

            # ======== Auditoria (sempre mostra o bloco) ========
            with st.expander("🧯 Sugestões de correção", expanded=False):
                if not AUDITORIA_ON:
                    st.info("Auditoria indisponível: módulo não carregado. Verifique `core/auditoria_inline.py` e o import.")
                else:
                    if not auditoria:
                        st.info("Sem achados nesta nota (ou XML não possui campos suficientes para auditoria).")
                    else:
                        a_itens = auditoria.get("itens") or []
                        a_totais = auditoria.get("totais") or []
                        a_pedido = auditoria.get("pedido") or []

                        if a_itens:
                            st.markdown("**Por item (cálculo/códigos):**")
                            rows = []
                            for a in a_itens:
                                rows.append({
                                    "nItem": a.get("nItem"),
                                    "Produto": a.get("xProd"),
                                    "Tipo": a.get("tipo"),
                                    "Mensagem": a.get("msg"),
                                })
                            if rows:
                                st.dataframe(rows, hide_index=True, use_container_width=True)

                        if a_totais:
                            st.markdown("**Totais:**")
                            for t in a_totais:
                                st.write(f"• {t.get('msg')}")

                        if a_pedido:
                            st.markdown("**Divergências vs. Pedido de Compra:**")
                            rows = []
                            for d in a_pedido:
                                rows.append({
                                    "Tipo": d.get("tipo"),
                                    "Mensagem": d.get("msg"),
                                    "Item NF": (d.get("xml") or {}).get("xProd") if d.get("xml") else "",
                                    "Item Pedido": (d.get("pedido") or {}).get("descricao") if d.get("pedido") else ""
                                })
                            st.dataframe(rows, hide_index=True, use_container_width=True)

            # Parecer do agente
            if isinstance(ag_resp, dict):
                entries = ag_resp.get("itens") or ag_resp.get("resultados") or []
                with st.expander("🤖 Parecer da LLM — Produto × CFOP", expanded=False):
                    rows = []
                    for r in entries:
                        decis = r.get("decision", {}) or {}
                        badge = (r.get("badge","") or "").upper()
                        selo = "🔴 INCOERENTE" if "INCOER" in badge else ("🟠 ATENÇÃO" if "ATEN" in badge else "🟢 COERENTE")
                        rows.append({
                            "Item": r.get("nItem","—"),
                            "Produto": r.get("xProd") or r.get("produto",""),
                            "CFOP (informado)": r.get("CFOP_informado") or r.get("cfop",""),
                            "Selo": selo,
                            "Ação": (decis.get("action","") or "").upper(),
                            "CFOP sugerido": r.get("CFOP_sugerido",""),
                            "Justificativa": " | ".join(decis.get("reasons", []))[:1000]
                        })
                    if rows:
                        st.dataframe(rows, hide_index=True, use_container_width=True)
                    else:
                        st.info("Sem itens para avaliar.")

            if classif:
                with st.expander("🧭 Classificação automática (tipo, centros, tags)", expanded=False):
                    tipo   = (classif.get("tipo") or "—")
                    setor  = (classif.get("setor") or "—")
                    conf   = classif.get("confidence") or classif.get("conf")
                    centros = [c for c in (classif.get("centros_custo") or []) if c]
                    tags    = list(dict.fromkeys(classif.get("tags", [])))
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Tipo", tipo); c2.metric("Setor", setor); c3.metric("Confiança", f"{conf*100:.1f}%" if isinstance(conf,(int,float)) else "—")
                    if centros:
                        st.markdown("Centros de custo:")
                        st.markdown(" ".join(_chip(c) for c in centros), unsafe_allow_html=True)
                    if tags:
                        st.caption("Tags: " + ", ".join(f"`{t}`" for t in tags))

            with st.popover("🔧 Debug bruto (opcional)"):
                st.json(extracted)
    else:
        st.info("Selecione uma nota para visualizar os detalhes.")

    # ===== Dashboards gerenciais (todas as notas carregadas) =====
    st.markdown("---")
    render_dashboards(st.session_state["nfe_results"])
else:
    st.info("Carregue notas para habilitar os detalhes e os dashboards.")

st.markdown("---")
st.subheader("Relatório executivo (LLM/Hugging Face)")

org_name = st.text_input("Nome da organização (opcional)", value="")

col_pdf1, col_pdf2 = st.columns([1,2])
with col_pdf1:
    if st.session_state.get("nfe_results"):
        if st.button("🧠 Gerar PDF com LLM (HF)", type="primary", use_container_width=True, key="btn_llm_pdf"):
            try:
                pdf_bytes = build_llm_executive_pdf(
                    st.session_state["nfe_results"],
                    org_name=org_name or None,
                    logo_path="static/logo.png"  # ajuste se quiser
                )
                st.download_button(
                    "⬇️ Baixar Relatório (PDF - LLM)",
                    data=pdf_bytes,
                    file_name="relatorio_executivo_llm.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                st.success("PDF gerado pela LLM com sucesso.")
            except Exception as e:
                st.error(f"Falha ao gerar PDF (LLM): {e}")
    else:
        st.info("Carregue notas para habilitar o relatório.")
with col_pdf2:
    st.caption("O texto do relatório é redigido pela LLM configurada via Hugging Face Inference API.")
