# core/dashboards.py
from __future__ import annotations
import streamlit as st
import pandas as pd
import altair as alt
from decimal import Decimal
from typing import List, Dict, Any

# -------------- Helpers de dados --------------
def _D(x) -> Decimal:
    try:
        if x in (None, "", "-"):
            return Decimal("0")
        return Decimal(str(x).replace(",", "."))
    except Exception:
        return Decimal("0")

def _safe(d: dict, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur if cur is not None else default

def _emit_uf(r: dict) -> str:
    return _safe(r, "extraction", "emit", "enderEmit", "UF", default="") or ""

def _dest_uf(r: dict) -> str:
    return _safe(r, "extraction", "dest", "enderDest", "UF", default="") or ""

def _itens(r: dict) -> list:
    return _safe(r, "extraction", "itens", default=[]) or []

def _achados_itens(r: dict) -> list:
    return _safe(r, "auditoria", "itens", default=[]) or []

def _achados_totais(r: dict) -> list:
    return _safe(r, "auditoria", "totais", default=[]) or []

def _achados_pedido(r: dict) -> list:
    return _safe(r, "auditoria", "pedido", default=[]) or []

# -------------- Flatten p/ DataFrames --------------
def _df_notas(results: List[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        totais = _safe(r, "extraction", "totais", default={}) or {}
        rows.append({
            "arquivo": r.get("arquivo"),
            "ok": bool(r.get("ok")),
            "score_av": r.get("score", 0) or 0,
            "emit_UF": _emit_uf(r),
            "dest_UF": _dest_uf(r),
            "vNF": str(totais.get("vNF","")),
            "vProd": str(totais.get("vProd","")),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["score_av"] = pd.to_numeric(df["score_av"], errors="coerce").fillna(0)
    return df

def _df_items(results: List[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        arq = r.get("arquivo")
        euf, duf = _emit_uf(r), _dest_uf(r)
        for it in _itens(r):
            p = it.get("prod", {}) or {}
            imp = it.get("imposto", {}) or {}
            icms = imp.get("ICMS", {}) or {}
            rows.append({
                "arquivo": arq,
                "emit_UF": euf,
                "dest_UF": duf,
                "nItem": it.get("nItem"),
                "xProd": p.get("xProd",""),
                "CFOP": p.get("CFOP",""),
                "CST_CSOSN": icms.get("CST") or icms.get("CSOSN",""),
            })
    return pd.DataFrame(rows)

def _df_achados(results: List[dict]) -> pd.DataFrame:
    """
    Normaliza achados de:
      • auditoria.itens/totais/pedido
      • agente.itens[*].achados (regras do CFOP)
    Remove ruído (campos vazios) e duplicatas.
    """
    RULE_MAP = {
        "CFOP_INCONSISTENTE_UF": "cfop_incoerente",
        "CFOP_EXTERIOR_INCOMPATIVEL": "cfop_exterior_incomp",
        "ST_POSSIVEL_SEM_CAMPOS": "st_campo_faltando",
    }

    rows = []
    for r in results:
        arq = r.get("arquivo")
        euf, duf = _emit_uf(r), _dest_uf(r)

        # -------- AUDITORIA --------
        for it in _achados_itens(r):
            if isinstance(it, dict) and isinstance(it.get("achados"), list):
                xprod = it.get("xProd",""); nitem = it.get("nItem")
                for h in it.get("achados") or []:
                    tipo = (h.get("tipo") or "").strip()
                    msg  = (h.get("msg") or h.get("mensagem") or "").strip()
                    if not tipo and not msg:
                        continue
                    rows.append({
                        "arquivo": arq, "emit_UF": euf, "dest_UF": duf,
                        "nivel": "item", "nItem": nitem, "xProd": xprod,
                        "tipo": tipo, "imposto": (h.get("imposto") or "").strip(), "msg": msg,
                    })
            else:
                if isinstance(it, dict):
                    tipo = (it.get("tipo") or "").strip()
                    msg  = (it.get("msg") or "").strip()
                    if tipo or msg:
                        rows.append({
                            "arquivo": arq, "emit_UF": euf, "dest_UF": duf,
                            "nivel": "item", "nItem": it.get("nItem",""),
                            "xProd": it.get("xProd",""), "tipo": tipo,
                            "imposto": (it.get("imposto") or "").strip(), "msg": msg,
                        })

        for t in _achados_totais(r):
            tipo = (t.get("tipo") or "total_incoerente").strip()
            msg  = (t.get("msg") or "").strip()
            if not tipo and not msg:
                continue
            rows.append({
                "arquivo": arq, "emit_UF": euf, "dest_UF": duf,
                "nivel": "totais", "nItem": "", "xProd": "",
                "tipo": tipo, "imposto": "", "msg": msg,
            })

        for d in _achados_pedido(r):
            tipo = (d.get("tipo") or "").strip()
            msg  = (d.get("msg") or "").strip()
            if not tipo and not msg:
                continue
            rows.append({
                "arquivo": arq, "emit_UF": euf, "dest_UF": duf,
                "nivel": "pedido", "nItem": "", "xProd": (d.get("xml") or {}).get("xProd",""),
                "tipo": tipo, "imposto": "", "msg": msg,
            })

        # -------- AGENTE CFOP --------
        ag = r.get("agente") or {}
        ag_itens = ag.get("itens") or ag.get("resultados") or []
        for ai in ag_itens:
            xprod = ai.get("xProd") or ai.get("produto") or ""
            nitem = ai.get("nItem", "")
            for h in ai.get("achados") or []:
                regra = (h.get("regra") or "").strip().upper()
                tipo  = RULE_MAP.get(regra, regra.lower())
                msg   = (h.get("msg") or "").strip()
                if not tipo and not msg:
                    continue
                rows.append({
                    "arquivo": arq, "emit_UF": euf, "dest_UF": duf,
                    "nivel": "agente", "nItem": nitem, "xProd": xprod,
                    "tipo": tipo, "imposto": "", "msg": msg,
                })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for col in ["arquivo","emit_UF","dest_UF","nivel","nItem","xProd","tipo","imposto","msg"]:
        if col not in df.columns:
            df[col] = ""
    df = df[(df["tipo"].astype(str).str.len() > 0) | (df["msg"].astype(str).str.len() > 0)]
    df = df.drop_duplicates().reset_index(drop=True)
    return df

# -------------- UI Utils --------------
def _download(df: pd.DataFrame, name: str):
    if df is not None and not df.empty:
        st.download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8"),
                           file_name=name, mime="text/csv", use_container_width=True)

def _pct_series(counts: pd.Series) -> pd.Series:
    total = counts.sum()
    return (counts / max(total, 1) * 100.0).round(1)

def _bar(df: pd.DataFrame, x: str, y: str, title: str, top_n: int | None = None):
    if df.empty:
        st.info("Sem dados.")
        return
    data = df.copy()
    if top_n:
        data = data.sort_values(y, ascending=False).head(top_n)
    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X(f"{y}:Q", title="Quantidade"),
            y=alt.Y(f"{x}:N", sort="-x", title=""),
            tooltip=[x, y]
        )
        .properties(height=max(240, 26 * len(data)), title=title)
    )
    st.altair_chart(chart, use_container_width=True)

def _bar_pct(df: pd.DataFrame, x: str, ncol: str, title: str, top_n: int | None = None):
    if df.empty:
        st.info("Sem dados.")
        return
    d = df.copy()
    d["%"] = _pct_series(d[ncol])
    if top_n:
        d = d.sort_values(ncol, ascending=False).head(top_n)
    chart = (
        alt.Chart(d)
        .mark_bar()
        .encode(
            x=alt.X(f"{ncol}:Q", title="Quantidade"),
            y=alt.Y(f"{x}:N", sort="-x", title=""),
            tooltip=[x, alt.Tooltip(ncol, title="Qtd"), alt.Tooltip("%", title="%")]
        )
        .properties(height=max(240, 26 * len(d)), title=title)
    )
    st.altair_chart(chart, use_container_width=True)

def _heatmap(df: pd.DataFrame, x: str, y: str, v: str, title: str):
    if df.empty:
        st.info("Sem dados.")
        return
    chart = (
        alt.Chart(df)
        .mark_rect()
        .encode(
            x=alt.X(f"{x}:N", title="Destino (UF)"),
            y=alt.Y(f"{y}:N", title="Origem (UF)"),
            color=alt.Color(f"{v}:Q", title="Quantidade"),
            tooltip=[y, x, v]
        )
        .properties(height=320, title=title)
    )
    st.altair_chart(chart, use_container_width=True)

def _pie(df: pd.DataFrame, label: str, value: str, title: str):
    if df.empty:
        st.info("Sem dados.")
        return
    chart = (
        alt.Chart(df)
        .mark_arc(innerRadius=60)
        .encode(
            theta=alt.Theta(f"{value}:Q"),
            color=alt.Color(f"{label}:N", legend=alt.Legend(title=label)),
            tooltip=[label, alt.Tooltip(value, title="Qtd")]
        )
        .properties(height=300, title=title)
    )
    st.altair_chart(chart, use_container_width=True)

# -------------- Páginas --------------
def _overview(df_notas: pd.DataFrame, df_ach: pd.DataFrame):
    st.markdown("### 📊 Visão Geral (Executivo)")
    total = int(len(df_notas)) if not df_notas.empty else 0
    aprov = int(df_notas["ok"].sum()) if not df_notas.empty else 0
    bloq  = total - aprov
    media = float(df_notas["score_av"].mean()) if not df_notas.empty else 0.0

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Notas carregadas", total, help="Quantidade total de XML processados na sessão.")
    c2.metric("Aprovadas (AV)", aprov, help="Passaram no Mini-AV.")
    c3.metric("Bloqueadas (AV)", bloq, help="Barradas pelo Mini-AV.")
    c4.metric("Score AV médio", f"{media:.1f}")

    colA, colB = st.columns(2)
    with colA:
        if not df_notas.empty:
            em = (df_notas["emit_UF"].fillna("").replace("", "—")
                  .value_counts().rename_axis("UF").reset_index(name="Quantidade"))
            _bar_pct(em, "UF", "Quantidade", "Notas por UF do emitente (com %)")
            _download(em, "notas_por_emitente_uf.csv")
        else:
            st.info("Sem dados de emitente.")

    with colB:
        if not df_notas.empty:
            de = (df_notas["dest_UF"].fillna("").replace("", "—")
                  .value_counts().rename_axis("UF").reset_index(name="Quantidade"))
            _bar_pct(de, "UF", "Quantidade", "Notas por UF do destinatário (com %)")
            _download(de, "notas_por_destinatario_uf.csv")
        else:
            st.info("Sem dados de destinatário.")

    if not df_notas.empty:
        fluxo = (df_notas.assign(
                    emit_UF=df_notas["emit_UF"].fillna("").replace("", "—"),
                    dest_UF=df_notas["dest_UF"].fillna("").replace("", "—"))
                 .groupby(["emit_UF","dest_UF"]).size().reset_index(name="Quantidade"))
        st.markdown("#### Fluxos UF → UF")
        _heatmap(fluxo, "dest_UF", "emit_UF", "Quantidade", "Origem × Destino")
        _download(fluxo, "fluxos_uf_uf.csv")

    # --- Pizzas (executivo) ---
    st.markdown("#### Distribuição por UF (pizza)")
    colP1, colP2, colP3 = st.columns(3)

    with colP1:
        if not df_notas.empty:
            em_pie = (df_notas["emit_UF"].fillna("").replace("", "—")
                      .value_counts().rename_axis("UF").reset_index(name="Quantidade"))
            _pie(em_pie, "UF", "Quantidade", "Notas por UF (Emitente)")
        else:
            st.info("Sem dados de emitente.")

    with colP2:
        if not df_notas.empty:
            de_pie = (df_notas["dest_UF"].fillna("").replace("", "—")
                      .value_counts().rename_axis("UF").reset_index(name="Quantidade"))
            _pie(de_pie, "UF", "Quantidade", "Notas por UF (Destinatário)")
        else:
            st.info("Sem dados de destinatário.")

    with colP3:
        if df_ach is not None and not df_ach.empty:
            ach_pie = (df_ach.assign(emit_UF=df_ach["emit_UF"].fillna("").replace("", "—"))
                              .groupby("emit_UF").size().reset_index(name="Achados")
                              .rename(columns={"emit_UF":"UF"}))
            _pie(ach_pie, "UF", "Achados", "Achados por UF (Emitente)")
        else:
            st.info("Sem achados para pizza.")

def _erros(df_ach: pd.DataFrame, filtros: dict):
    st.markdown("### 🧯 Erros & Alertas")
    if df_ach.empty:
        st.success("Nenhum achado até o momento. ✅")
        return

    df = df_ach.copy()
    if filtros["emit"]:
        df = df[df["emit_UF"].isin(filtros["emit"])]
    if filtros["dest"]:
        df = df[df["dest_UF"].isin(filtros["dest"])]
    if filtros["tipo"]:
        df = df[df["tipo"].isin(filtros["tipo"])]

    if df.empty:
        st.success("Nenhum achado para os filtros selecionados. ✅")
        return

    cont_tipo = (df.groupby("tipo").size().reset_index(name="Quantidade")
                   .sort_values("Quantidade", ascending=False))
    _bar(cont_tipo, "tipo", "Quantidade", "Tipos de achado (Top 20)", top_n=20)
    _download(cont_tipo, "achados_por_tipo.csv")

    # Destaque CFOP incoerente
    if "cfop_incoerente" in cont_tipo["tipo"].values:
        st.warning("Há ocorrências de **CFOP incoerente**. Revise a coerência UF×CFOP nos itens impactados.")

    st.markdown("#### Detalhamento")
    st.dataframe(df[["arquivo","emit_UF","dest_UF","nivel","nItem","xProd","tipo","imposto","msg"]],
                 use_container_width=True, hide_index=True)
    _download(df, "achados_detalhados.csv")

def _cfop_cst(df_items: pd.DataFrame, filtros: dict):
    st.markdown("### 🧾 CFOP & CST/CSOSN")
    if df_items.empty:
        st.info("Sem itens.")
        return
    df = df_items.copy()
    if filtros["emit"]:
        df = df[df["emit_UF"].isin(filtros["emit"])]
    if filtros["dest"]:
        df = df[df["dest_UF"].isin(filtros["dest"])]

    por_cfop = (df.assign(CFOP=df["CFOP"].fillna("").replace("", "—"))
                  .groupby("CFOP").size().reset_index(name="Quantidade")
                  .sort_values("Quantidade", ascending=False))
    _bar(por_cfop, "CFOP", "Quantidade", "Itens por CFOP (Top 25)", top_n=25)
    _download(por_cfop, "itens_por_cfop.csv")

    por_cst = (df.assign(CST_CSOSN=df["CST_CSOSN"].fillna("").replace("", "—"))
                 .groupby("CST_CSOSN").size().reset_index(name="Quantidade")
                 .sort_values("Quantidade", ascending=False))
    _bar(por_cst, "CST_CSOSN", "Quantidade", "Itens por CST/CSOSN (Top 25)", top_n=25)
    _download(por_cst, "itens_por_cst_csosn.csv")

def _produtos_hot(df_ach: pd.DataFrame, filtros: dict):
    st.markdown("### 📦 Itens/Produtos com mais achados")
    if df_ach.empty:
        st.info("Sem achados.")
        return
    df = df_ach.copy()
    df = df[df["xProd"].astype(str).str.len() > 0]
    if filtros["emit"]:
        df = df[df["emit_UF"].isin(filtros["emit"])]
    if filtros["dest"]:
        df = df[df["dest_UF"].isin(filtros["dest"])]
    if filtros["tipo"]:
        df = df[df["tipo"].isin(filtros["tipo"])]

    if df.empty:
        st.info("Sem achados para os filtros aplicados.")
        return

    top = (df.groupby("xProd").size().reset_index(name="Achados")
             .sort_values("Achados", ascending=False).head(30))
    _bar(top, "xProd", "Achados", "Top 30 produtos com achados", top_n=30)
    _download(top, "top_produtos_achados.csv")

def _notas(df_notas: pd.DataFrame, df_ach: pd.DataFrame, filtros: dict):
    st.markdown("### 🗂️ Notas (Gerencial)")
    if df_notas.empty:
        st.info("Sem notas.")
        return

    cont = df_ach.groupby("arquivo").size().reset_index(name="achados") if not df_ach.empty else pd.DataFrame(columns=["arquivo","achados"])
    df = df_notas.merge(cont, on="arquivo", how="left").fillna({"achados":0})
    if filtros["emit"]:
        df = df[df["emit_UF"].isin(filtros["emit"])]
    if filtros["dest"]:
        df = df[df["dest_UF"].isin(filtros["dest"])]

    df = df.rename(columns={"ok":"aprovada"})
    df["aprovada"] = df["aprovada"].map({True:"Aprovada", False:"Bloqueada"})
    st.dataframe(df[["arquivo","aprovada","score_av","emit_UF","dest_UF","vNF","vProd","achados"]],
                 use_container_width=True, hide_index=True)
    _download(df, "notas_gerencial.csv")

# -------------- Função pública --------------
def render_dashboards(results: List[dict]):
    """
    Dashboard gerencial consolidado para TODAS as notas da sessão.
    """
    st.header("📊 Dashboards")

    if not results:
        st.info("Carregue notas para ver os dashboards.")
        return

    # DataFrames base
    df_notas = _df_notas(results)
    df_items = _df_items(results)
    df_ach   = _df_achados(results)

    # --- Filtros globais (afetam todas as abas) ---
    with st.expander("🎛️ Filtros globais", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            f_emit = st.multiselect("UF do emitente", sorted([u for u in df_notas["emit_UF"].dropna().unique() if u]))
        with c2:
            f_dest = st.multiselect("UF do destinatário", sorted([u for u in df_notas["dest_UF"].dropna().unique() if u]))
        with c3:
            tipos_unique = sorted(df_ach["tipo"].dropna().unique().tolist()) if not df_ach.empty else []
            f_tipo = st.multiselect("Tipo de achado (auditoria/agente)", tipos_unique)
        filtros = {"emit": f_emit, "dest": f_dest, "tipo": f_tipo}

    # KPIs + visão macro (inclui pizzas)
    _overview(df_notas, df_ach)

    st.markdown("---")
    tabs = st.tabs(["🧯 Erros & Alertas", "🧾 CFOP & CST/CSOSN", "📦 Produtos/Itens", "🗂️ Notas"])

    with tabs[0]:
        _erros(df_ach, filtros)
    with tabs[1]:
        _cfop_cst(df_items, filtros)
    with tabs[2]:
        _produtos_hot(df_ach, filtros)
    with tabs[3]:
        _notas(df_notas, df_ach, filtros)
