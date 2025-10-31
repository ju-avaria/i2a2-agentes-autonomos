# core/report_llm_pdf.py
from __future__ import annotations
import os, json, time, re
from io import BytesIO
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from collections import Counter
from datetime import datetime

# ==== .env (mesmo se rodar de /pages) ====
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(), override=False)
except Exception:
    pass

# ==== HTTP (Hugging Face) ====
import urllib.request, urllib.error

# ==== PDF (somente TEXTO) ====
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ===================== HF config (.env) =====================
HF_TOKEN = os.getenv("HUGGINGFACE_API_KEY", "") or os.getenv("HF_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", "microsoft/Phi-3.5-mini-instruct")
HF_URL   = os.getenv("HF_URL", f"https://api-inference.huggingface.co/models/{HF_MODEL}")
HF_TEMPERATURE = float(os.getenv("HF_TEMPERATURE", "0.0"))
HF_MAX_NEW_TOKENS = int(os.getenv("HF_MAX_NEW_TOKENS", "320"))

# ===================== Utils / KPIs =====================
_cfop_rx = re.compile(r"\bcfop\b", re.I)

def _emit_uf(r: dict) -> str:
    return (((r.get("extraction") or {}).get("emit") or {}).get("enderEmit") or {}).get("UF", "") or ""

def _dest_uf(r: dict) -> str:
    return (((r.get("extraction") or {}).get("dest") or {}).get("enderDest") or {}).get("UF", "") or ""

def _norm_cfop(tipo: str, regra: str, msg: str) -> str:
    """Normaliza qualquer referência a CFOP para 'cfop_incoerente'."""
    if _cfop_rx.search(tipo or "") or _cfop_rx.search(regra or "") or _cfop_rx.search(msg or ""):
        return "cfop_incoerente"
    return (tipo or "").strip().lower()

def _collect_achados(r: dict) -> List[Dict[str, Any]]:
    """Une achados da auditoria e do agente (se houver), já normalizados."""
    out: List[Dict[str, Any]] = []
    aud = r.get("auditoria") or {}

    # auditoria.itens
    for it in aud.get("itens") or []:
        for h in (it.get("achados") or []):
            tipo = _norm_cfop(h.get("tipo", ""), "", h.get("msg", ""))
            out.append({
                "tipo": tipo,
                "nivel": "item",
                "imposto": (h.get("imposto") or "").strip().lower(),
                "msg": h.get("msg") or "",
            })

    # auditoria.totais
    for t in aud.get("totais") or []:
        tipo = _norm_cfop(t.get("tipo", ""), "", t.get("msg", ""))
        if not tipo:
            tipo = "total_incoerente"
        out.append({"tipo": tipo, "nivel": "totais", "imposto": "", "msg": t.get("msg") or ""})

    # auditoria.pedido
    for d in aud.get("pedido") or []:
        tipo = _norm_cfop(d.get("tipo", ""), "", d.get("msg", ""))
        out.append({"tipo": tipo, "nivel": "pedido", "imposto": "", "msg": d.get("msg") or ""})

    # agente (CFOP etc.)
    ag = r.get("agente") or {}
    for ai in (ag.get("itens") or ag.get("resultados") or []):
        for h in ai.get("achados") or []:
            regra = (h.get("regra") or "").strip()
            tipo  = _norm_cfop(h.get("tipo", ""), regra, h.get("msg", ""))
            out.append({"tipo": tipo or regra.lower(), "nivel": "agente", "imposto": "", "msg": h.get("msg") or ""})
    return out

@dataclass
class KPI:
    total_notas: int
    aprovadas: int
    bloqueadas: int
    aprovadas_pct: float
    bloqueadas_pct: float
    achados_totais: int
    notas_com_achado: int
    notas_com_achado_pct: float
    cfop_count: int
    gerado_em: str

def _pct(part: int, total: int) -> float:
    total = max(total, 1)
    return round((part / total) * 100.0, 1)

def _compute_kpis(results: List[dict]) -> Tuple[KPI, Dict[str, Any]]:
    total = len(results)
    aprovadas = sum(1 for r in results if r.get("ok"))
    bloqueadas = total - aprovadas

    tipos, emit_uf, dest_uf = Counter(), Counter(), Counter()
    notas_com_achado = 0
    achados_totais = 0

    for r in results:
        emit_uf[_emit_uf(r) or "—"] += 1
        dest_uf[_dest_uf(r) or "—"] += 1
        ach = _collect_achados(r)
        achados_totais += len(ach)
        if ach:
            notas_com_achado += 1
        for a in ach:
            tipos[a.get("tipo", "")] += 1

    # robusto para qualquer variação contendo "cfop"
    cfop_count = sum(v for k, v in tipos.items() if "cfop" in (k or ""))

    kpi = KPI(
        total_notas=total,
        aprovadas=aprovadas,
        bloqueadas=bloqueadas,
        aprovadas_pct=_pct(aprovadas, total),
        bloqueadas_pct=_pct(bloqueadas, total),
        achados_totais=achados_totais,
        notas_com_achado=notas_com_achado,
        notas_com_achado_pct=_pct(notas_com_achado, total),
        cfop_count=cfop_count,
        gerado_em=datetime.utcnow().isoformat() + "Z",
    )
    brk = {
        "tipos": tipos.most_common(),
        "emit_uf": emit_uf.most_common(),
        "dest_uf": dest_uf.most_common(),
    }
    return kpi, brk

# ===================== Hugging Face Inference =====================
def _hf_generate(prompt: str) -> str:
    if not HF_TOKEN:
        return ""
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": HF_TEMPERATURE,
            "max_new_tokens": HF_MAX_NEW_TOKENS,
            "return_full_text": False
        }
    }
    data = json.dumps(payload).encode("utf-8")

    backoff = 1.0
    for _ in range(4):
        req = urllib.request.Request(
            HF_URL, data=data, method="POST",
            headers={"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read().decode("utf-8")
                try:
                    obj = json.loads(raw)
                except Exception:
                    return raw
                if isinstance(obj, list) and obj and "generated_text" in obj[0]:
                    return obj[0]["generated_text"]
                if isinstance(obj, dict) and "generated_text" in obj:
                    return obj["generated_text"]
                if isinstance(obj, dict) and obj.get("choices"):
                    return obj["choices"][0].get("text", "")
                if isinstance(obj, dict) and obj.get("error", "").lower().find("loading") >= 0:
                    time.sleep(backoff); backoff *= 2; continue
                return ""
        except urllib.error.HTTPError as e:
            if e.code in (503, 529):
                time.sleep(backoff); backoff *= 2; continue
            return ""
        except Exception:
            time.sleep(backoff); backoff *= 2
    return ""

# ===================== Helpers de texto =====================
def _pairs_as_sentence(pairs: List[Tuple[str, int]], max_items: int = 20, empty_sym: str = "—") -> str:
    """
    Converte [('SP',10),('BA',7)] -> 'SP: 10; BA: 7'
    """
    if not pairs:
        return empty_sym
    return "; ".join([f"{(k or empty_sym)}: {v}" for k, v in pairs[:max_items]])

def _total_ufs(pairs: List[Tuple[str, int]]) -> int:
    return len([k for k, _ in pairs if k and k != "—"])

# ===================== Texto (prompt e deterministic) =====================
def _build_prompt_text(kpi: KPI, br: Dict[str, Any], org: str | None) -> str:
    emit_tx = _pairs_as_sentence(br["emit_uf"])
    dest_tx = _pairs_as_sentence(br["dest_uf"])
    tipos_tx = _pairs_as_sentence(br["tipos"])
    cfop_flag = "SIM" if kpi.cfop_count > 0 else "NÃO"
    emit_qtd = _total_ufs(br["emit_uf"])
    dest_qtd = _total_ufs(br["dest_uf"])

    return f"""
Você é analista sênior. Escreva UM RELATÓRIO GERENCIAL EM TEXTO PLANO (sem markdown), em até 600 palavras.
Divida em 5 seções com títulos em maiúsculo: CONTEXTO, INDICADORES, RISCOS E ACHADOS, INTERPRETAÇÃO GERENCIAL, RECOMENDAÇÕES.
Seja direto, assertivo e evite jargão. Cite explicitamente as UFs (emitente e destinatário) com contagens.

Dados:
Organização: {org or '—'}
Total de notas: {kpi.total_notas}
Aprovadas: {kpi.aprovadas} ({kpi.aprovadas_pct}%)
Bloqueadas: {kpi.bloqueadas} ({kpi.bloqueadas_pct}%)
Notas com achados: {kpi.notas_com_achado} ({kpi.notas_com_achado_pct}%)
Achados totais: {kpi.achados_totais}
CFOP presente? {cfop_flag} (contagem: {kpi.cfop_count})
UF do emitente (total {emit_qtd}): {emit_tx}
UF do destinatário (total {dest_qtd}): {dest_tx}
Principais tipos de achado: {tipos_tx}

Regras de saída:
- Texto plano, sem bullets, sem markdown e sem HTML.
- Se houver CFOP, trate como risco priorizado; se não houver, deixe claro que o cenário está limpo.
- Indique próximos passos práticos na seção RECOMENDAÇÕES.
"""

def _deterministic_text(kpi: KPI, br: Dict[str, Any], org: str | None) -> str:
    emit_tx  = _pairs_as_sentence(br["emit_uf"])
    dest_tx  = _pairs_as_sentence(br["dest_uf"])
    tipos_tx = _pairs_as_sentence(br["tipos"])
    emit_qtd = _total_ufs(br["emit_uf"])
    dest_qtd = _total_ufs(br["dest_uf"])

    if kpi.cfop_count > 0:
        cfop_line = f"Foram identificados {kpi.cfop_count} apontamentos de CFOP, que devem ser priorizados."
        recomend = ("Conferir CFOP nos itens sinalizados; revisar cadastros; atualizar playbooks; "
                    "acompanhar as recorrências por UF e fornecedor.")
    else:
        cfop_line = "Não foram identificados apontamentos de CFOP nesta sessão."
        recomend = "Manter o fluxo atual; instituir amostragem periódica; monitorar tendências por UF e fornecedores."

    return (
        "CONTEXTO\n"
        f"Relatório gerencial da sessão de validação de NF-e para {org or '—'}.\n\n"
        "INDICADORES\n"
        f"Total de notas: {kpi.total_notas}. Aprovadas: {kpi.aprovadas} ({kpi.aprovadas_pct}%). "
        f"Bloqueadas: {kpi.bloqueadas} ({kpi.bloqueadas_pct}%). Notas com achados: "
        f"{kpi.notas_com_achado} ({kpi.notas_com_achado_pct}%). Achados totais: {kpi.achados_totais}.\n"
        f"UF do emitente ({emit_qtd}): {emit_tx}.\n"
        f"UF do destinatário ({dest_qtd}): {dest_tx}.\n\n"
        "RISCOS E ACHADOS\n"
        f"{cfop_line} Principais tipos de achado: {tipos_tx}.\n\n"
        "INTERPRETAÇÃO GERENCIAL\n"
        "O conjunto de notas indica o nível de conformidade e a distribuição por UF. "
        "Foque nos itens com achados reincidentes e nos fluxos UF→UF mais frequentes, "
        "pois concentram maior impacto operacional/fiscal.\n\n"
        "RECOMENDAÇÕES\n"
        f"{recomend}\n"
    )

# ===================== PDF (somente texto) =====================
def build_llm_executive_pdf(
    results: List[dict],
    org_name: str | None = None,
    logo_path: str | None = None  # mantido por compatibilidade; ignorado
) -> bytes:
    """
    Gera um PDF EXECUTIVO **apenas TEXTO**, sem gráficos.
    - Texto determinístico sempre presente (claro, conciso e didático).
    - Se houver HF_TOKEN, adiciona seção 'Análise LLM (opcional)' com narrativa da Hugging Face.
    """
    # Fonte com acentos
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        base_font = "DejaVu"
    except Exception:
        base_font = "Helvetica"

    kpi, br = _compute_kpis(results)

    deterministic = _deterministic_text(kpi, br, org_name)
    llm_text = ""
    if HF_TOKEN:
        prompt = _build_prompt_text(kpi, br, org_name)
        llm_text = (_hf_generate(prompt) or "").strip()

    buf_pdf = BytesIO()
    doc = SimpleDocTemplate(
        buf_pdf, pagesize=A4,
        rightMargin=2.0*cm, leftMargin=2.0*cm, topMargin=1.8*cm, bottomMargin=1.5*cm
    )
    styles = getSampleStyleSheet()

    # Estilos com Nomes Únicos (evita "already defined")
    if "TitleNF" not in styles.byName:
        styles.add(ParagraphStyle(name="TitleNF", fontName=base_font, fontSize=16,
                                  leading=20, textColor=colors.HexColor("#0B2A4A"), spaceAfter=10))
    if "MetaNF" not in styles.byName:
        styles.add(ParagraphStyle(name="MetaNF", fontName=base_font, fontSize=9.8,
                                  leading=12, textColor=colors.grey, spaceAfter=6))
    if "BodyNF" not in styles.byName:
        styles.add(ParagraphStyle(name="BodyNF", fontName=base_font, fontSize=11.0, leading=15))
    if "H2NF" not in styles.byName:
        styles.add(ParagraphStyle(name="H2NF", fontName=base_font, fontSize=13, leading=16,
                                  textColor=colors.HexColor("#0B2A4A"), spaceBefore=8, spaceAfter=6))

    flow = []
    flow.append(Paragraph("Relatório Executivo — NF-e (Sessão Atual)", styles["TitleNF"]))
    if org_name:
        flow.append(Paragraph(f"Organização: {org_name}", styles["MetaNF"]))
    flow.append(Paragraph(f"Gerado em: {kpi.gerado_em}", styles["MetaNF"]))
    flow.append(Spacer(1, 6))

    # Texto determinístico didático
    for line in deterministic.split("\n"):
        l = line.strip()
        if not l:
            flow.append(Spacer(1, 4))
        else:
            # Seção em maiúsculas = subtítulo
            if l.isupper() and 2 <= len(l) <= 30:
                flow.append(Paragraph(l, styles["H2NF"]))
            else:
                flow.append(Paragraph(l, styles["BodyNF"]))

    # Narrativa opcional (LLM / HF)
    if llm_text:
        flow.append(Spacer(1, 10))
        flow.append(Paragraph("Análise LLM (opcional)", styles["H2NF"]))
        for line in llm_text.split("\n"):
            l = line.strip()
            if not l:
                flow.append(Spacer(1, 3))
            else:
                flow.append(Paragraph(l, styles["BodyNF"]))

    doc.build(flow)
    buf_pdf.seek(0)
    return buf_pdf.read()
