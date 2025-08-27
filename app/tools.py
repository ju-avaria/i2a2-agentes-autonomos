
from __future__ import annotations
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

import pandas as pd

from data_schemas import normalize_headers, parse_dates
from calendars import business_days_set
from export_layout import write_xlsx
from validations import prevalidate




BR_UF_BY_NOME = {
    "acre":"AC","alagoas":"AL","amapa":"AP","amazonas":"AM","bahia":"BA","ceara":"CE","distrito federal":"DF",
    "espirito santo":"ES","goias":"GO","maranhao":"MA","mato grosso":"MT","mato grosso do sul":"MS","minas gerais":"MG",
    "para":"PA","paraiba":"PB","parana":"PR","pernambuco":"PE","piaui":"PI","rio de janeiro":"RJ","rio grande do norte":"RN",
    "rio grande do sul":"RS","rondonia":"RO","roraima":"RR","santa catarina":"SC","sao paulo":"SP","sergipe":"SE","tocantins":"TO",
}
UF_SET = set(BR_UF_BY_NOME.values())

def _norm_txt(s: Any) -> str:
    return (
        str(s)
        .strip()
        .lower()
        .encode("ascii","ignore")
        .decode("ascii")
    )

def _infer_uf_from_text(*texts: Any) -> Optional[str]:
    """Tenta achar uma UF (sigla) ou nome de estado nos textos fornecidos."""
    for t in texts:
        if pd.isna(t): 
            continue
        raw = str(t)
        txt = _norm_txt(raw)

        m = re.search(r'[^a-zA-Z]([A-Za-z]{2})[^a-zA-Z]?$', raw.strip())
        if m:
            cand = m.group(1).upper()
            if cand in UF_SET:
                return cand

        for nome, uf in BR_UF_BY_NOME.items():
            if nome in txt:
                return uf

        for uf in UF_SET:
            if f" {uf.lower()} " in f" {raw.lower()} ":
                return uf
    return None

def _parse_ptbr_money(x) -> Optional[float]:

    if x is None:
        return None
    if isinstance(x, (int, float)):
        try:
            # cuidado com NaN
            return float(x) if not pd.isna(x) else None
        except Exception:
            return None

    s = str(x).strip()
    if "," in s:
        s = re.sub(r"[^\d,.\-]", "", s)  
        s = s.replace(".", "").replace(",", ".")
    else:

        s = re.sub(r"[^\d.\-]", "", s)

    try:
        return float(s)
    except Exception:
        return None



def _auto_unzip_and_discover(data_dir: Path) -> Dict[str, Path | None]:
    unpack_dir = data_dir / "UNPACKED"
    unpack_dir.mkdir(parents=True, exist_ok=True)


    for z in data_dir.glob("*.zip"):
        try:
            print(f"[tools] ZIP encontrado: {z.name} → extraindo em {unpack_dir} ...")
            with zipfile.ZipFile(z, "r") as zf:
                zf.extractall(unpack_dir)
        except zipfile.BadZipFile:
            print(f"[tools][WARN] Arquivo ZIP inválido: {z}")

    candidates = [p for p in data_dir.glob("*")] + [p for p in unpack_dir.rglob("*")]

    def pick(patterns: list[str]) -> Path | None:
        for p in candidates:
            if not p.is_file():
                continue
            name = p.name.lower()

            if name.startswith("vr mensal "):
                continue
            for pat in patterns:
                if re.search(pat, name):
                    return p
        return None

    discovered = {
        "ativos":           pick([r"ativo", r"colaborador", r"funcion"]),
        "ferias":           pick([r"ferias", r"férias"]),
        "desligados":       pick([r"deslig", r"rescis"]),
        "cadastral":        pick([r"cadastral", r"admitid", r"admiss"]),
        "sindicato_valor":  pick([r"sindicato", r"acordo.*valor", r"valor[_-]?vr", r"base sindicato x valor"]),

        "afastamentos":     pick([r"afast"]),
        "aprendiz":         pick([r"aprendiz"]),
        "estagio":          pick([r"estagio", r"estágio"]),
        "exterior":         pick([r"exterior"]),
        "calendario":       pick([r"calend", r"feriado"]),
    }

    print("[tools] Descoberta automática:")
    for k, v in discovered.items():
        print(f"  - {k}: {v if v else 'NÃO encontrado'}")

    return discovered



def _load_any_table(path: Path) -> pd.DataFrame:
    if not path or not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)  # fallback
    df = normalize_headers(df)
    df = parse_dates(df)
    return df

def _load_calendar(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    if path.suffix.lower() == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)

    df = normalize_headers(df)

    if "data" not in df.columns:
        for cand in ("date", "dt", "dia"):
            if cand in df.columns:
                df = df.rename(columns={cand: "data"})
                break
    if "data" not in df.columns:
        raise ValueError(f"Calendário em {path} sem coluna 'data'.")

    df["data"] = pd.to_datetime(df["data"], errors="coerce")

    if "eh_dia_util" not in df.columns:
        feriado_col = None
        for cand in ("eh_feriado", "feriado", "is_holiday"):
            if cand in df.columns:
                feriado_col = cand
                break
        if feriado_col:
            df["eh_dia_util"] = (~df[feriado_col].astype(bool)) & (df["data"].dt.weekday < 5)
        else:
            df["eh_dia_util"] = df["data"].dt.weekday < 5

    keep = ["data", "eh_dia_util"]
    for extra in ("sindicato_codigo", "uf", "municipio"):
        if extra in df.columns:
            keep.append(extra)
    return df[keep].copy()

def _fallback_calendar_from_weekdays(settings, df_ativos: pd.DataFrame) -> pd.DataFrame:
    from calendar import monthrange
    comp = settings.competencia
    start = comp.replace(day=1)
    end = comp.replace(day=monthrange(comp.year, comp.month)[1])
    base = pd.DataFrame({"data": pd.date_range(start, end, freq="D")})
    base["eh_dia_util"] = base["data"].dt.weekday < 5
    return base[["data","eh_dia_util"]].copy()


def load_bases(settings) -> Dict[str, pd.DataFrame]:
    data_dir = Path("/dados")
    discovered = _auto_unzip_and_discover(data_dir)

    def _pick(name: str, default_path: Path | None) -> Path | None:
        return discovered.get(name) or default_path

    paths = {
        "ativos":           _pick("ativos", settings.base_ativos),
        "ferias":           _pick("ferias", settings.base_ferias),
        "desligados":       _pick("desligados", settings.base_desligados),
        "cadastral":        _pick("cadastral", settings.base_cadastral),
        "sindicato_valor":  _pick("sindicato_valor", settings.base_sindicato_valor),
        "afastamentos":     _pick("afastamentos", None),
        "aprendiz":         _pick("aprendiz", None),
        "estagio":          _pick("estagio", None),
        "exterior":         _pick("exterior", None),
    }

    dfs: Dict[str, pd.DataFrame] = {}
    for k, p in paths.items():
        if p is None:
            continue
        try:
            dfs[k] = _load_any_table(p)
        except FileNotFoundError:
            pass

    cal_path = discovered.get("calendario")
    try:
        if cal_path is not None:
            print(f"[tools] Calendário detectado no ZIP: {cal_path.name}")
            dfs["calendario"] = _load_calendar(cal_path)
        else:
            print(f"[tools] Calendário via settings: {settings.calendario_path}")
            dfs["calendario"] = _load_calendar(settings.calendario_path)
    except FileNotFoundError:
        print("[tools][WARN] Calendário não encontrado. Usando fallback (seg–sex) apenas.")
        dfs["calendario"] = _fallback_calendar_from_weekdays(settings, dfs.get("ativos", pd.DataFrame()))

    return dfs


def run_prevalidations(dfs: Dict[str, pd.DataFrame], settings) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return prevalidate(dfs, settings)

def apply_exclusions(dfs: Dict[str, pd.DataFrame], settings) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = dfs["ativos"].copy()
    cad = dfs.get("cadastral", pd.DataFrame()).copy()
    excluidos = []


    for d in (df, cad):
        if "matricula" in d.columns:
            d["matricula"] = d["matricula"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

    cargo_col = "titulo_do_cargo" if "titulo_do_cargo" in df.columns else ("cargo" if "cargo" in df.columns else None)
    if cargo_col:
        mask_cargo = df[cargo_col].astype(str).str.lower().str.contains("diretor|estagi|aprendiz", regex=True, na=False)
        excluidos.append(df.loc[mask_cargo].assign(motivo_exclusao="cargo_nao_elegivel"))
        df = df.loc[~mask_cargo]

    def _exclude_by(df_base: pd.DataFrame, col_hint: list[str], motivo: str):
        if df_base is None or df_base.empty:
            return set()
        cols = set(df_base.columns)
        # tenta achar coluna tipo 'matricula' ou 'cadastro'
        key = "matricula" if "matricula" in cols else ("cadastro" if "cadastro" in cols else None)
        if key is None:
            return set()
        mats = set(df_base[key].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().dropna().unique())
        return mats

    mats_excluir = set()
    mats_excluir |= _exclude_by(dfs.get("aprendiz"), ["matricula"], "aprendiz")
    mats_excluir |= _exclude_by(dfs.get("estagio"),  ["matricula"], "estagio")
    mats_excluir |= _exclude_by(dfs.get("exterior"), ["cadastro","matricula"], "exterior")

    afast = dfs.get("afastamentos")
    if afast is not None and not afast.empty:
        col_nc = None
        for cand in afast.columns:
            if "na_compra" in cand:
                col_nc = cand
                break
        key = "matricula" if "matricula" in afast.columns else None
        if key:
            if col_nc:
                mask = afast[col_nc].astype(str).str.lower().isin({"nao","não","n","false","0"})
                mats_excluir |= set(afast.loc[mask, key].astype(str).str.replace(r"\.0$","",regex=True).str.strip())
            else:
                mats_excluir |= set(afast[key].astype(str).str.replace(r"\.0$","",regex=True).str.strip())
    if mats_excluir:
        excluidos.append(df.loc[df["matricula"].astype(str).isin(mats_excluir)].assign(motivo_exclusao="planilhas_aux"))
        df = df.loc[~df["matricula"].astype(str).isin(mats_excluir)]


    if not cad.empty and "matricula" in cad.columns:
        rename_map = {}
        if "admissao" in cad.columns:
            rename_map["admissao"] = "data_admissao"
        for k, v in rename_map.items():
            if k in cad.columns:
                cad = cad.rename(columns={k: v})
        df = df.merge(cad[["matricula"] + [c for c in ["data_admissao"] if c in cad.columns]],
                      on="matricula", how="left")

    if "lotacao_uf" not in df.columns:
        df["lotacao_uf"] = df.apply(
            lambda r: _infer_uf_from_text(r.get("sindicato"), r.get("empresa")), axis=1
        )

    sv = dfs["sindicato_valor"].copy()
    sv.columns = (
        sv.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.normalize("NFKD").str.encode("ascii","ignore").str.decode("ascii")
    )
    est_col = "estado" if "estado" in sv.columns else ("uf" if "uf" in sv.columns else None)
    val_col = "valor" if "valor" in sv.columns else (
        "valor_vr" if "valor_vr" in sv.columns else None
    )

    if est_col is None or val_col is None:
        df["valor_vr"] = 0.0
    else:
        sv["_estado_norm"] = sv[est_col].astype(str)
        sv["_estado_norm2"] = (
            sv["_estado_norm"].str.lower().str.normalize("NFKD").str.encode("ascii","ignore").str.decode("ascii")
        )
        sv["uf"] = sv["_estado_norm2"].map(BR_UF_BY_NOME).fillna(sv["_estado_norm"].str.upper())
        sv["valor_vr"] = sv[val_col].apply(_parse_ptbr_money).fillna(0.0)
        sv_f = sv[["uf","valor_vr"]].dropna(subset=["uf"]).copy()

        df["lotacao_uf_norm"] = df["lotacao_uf"].apply(lambda x: str(x).upper() if pd.notna(x) and str(x) else None)
        df = df.merge(sv_f, left_on="lotacao_uf_norm", right_on="uf", how="left")
        df["valor_vr"] = pd.to_numeric(df["valor_vr"], errors="coerce").fillna(0.0)
        df.drop(columns=["uf","lotacao_uf_norm"], inplace=True, errors="ignore")

    excl = (
        pd.concat(excluidos, ignore_index=True)
        if excluidos else pd.DataFrame(columns=df.columns.tolist() + ["motivo_exclusao"])
    )

    if "lotacao_uf" in df.columns:
        inferidos = int(df["lotacao_uf"].notna().sum())
        total = len(df)
        print(f"[merge] lotacao_uf preenchido/inferido: {inferidos}/{total}")
    print(f"[merge] colaboradores com valor_vr=0: {int((df['valor_vr']==0).sum())}")

    return df, excl




def _effective_window(row: pd.Series, competencia: date) -> Tuple[date, date]:
    from calendar import monthrange
    adm = pd.to_datetime(row.get("data_admissao"), errors="coerce")
    start = competencia.replace(day=1) if pd.isna(adm) else max(adm.date(), competencia.replace(day=1))
    comp_end = competencia.replace(day=monthrange(competencia.year, competencia.month)[1])
    data_desl = pd.to_datetime(row.get("data_desligamento"), errors="coerce")
    end = min(data_desl.date(), comp_end) if pd.notna(data_desl) else comp_end
    return start, end

def _apply_termination_rule(row: pd.Series, desligados_row: dict | None, competencia: date) -> bool:
    """Se comunicado_de_desligamento for 'OK/Sim/Yes' → zera."""
    if not desligados_row:
        return False
    flag = str(desligados_row.get("comunicado_de_desligamento", "")).strip().lower()
    return flag in {"ok","sim","yes","y"}



def compute_days_and_values(dfs: Dict[str, pd.DataFrame], settings) -> pd.DataFrame:
    if "consolidada" not in dfs:
        raise RuntimeError("Base 'consolidada' não encontrada. Rode apply_exclusions antes.")

    ativos = dfs["consolidada"].copy()
    ferias = dfs.get("ferias", pd.DataFrame())
    deslig = dfs.get("desligados", pd.DataFrame())
    cal = dfs["calendario"]

    if not deslig.empty:
        if "data_demissao" in deslig.columns and "data_desligamento" not in deslig.columns:
            deslig = deslig.rename(columns={"data_demissao":"data_desligamento"})
        if "matricula" in deslig.columns:
            deslig["matricula"] = deslig["matricula"].astype(str).str.replace(r"\.0$","",regex=True).str.strip()

    ferias_contagem = None
    if not ferias.empty and "dias_de_ferias" in ferias.columns:
        ff = ferias.copy()
        if "matricula" in ff.columns:
            ff["matricula"] = ff["matricula"].astype(str).str.replace(r"\.0$","",regex=True).str.strip()
            ferias_contagem = ff.groupby("matricula")["dias_de_ferias"].sum().to_dict()

    out_rows = []

    for _, row in ativos.iterrows():
        mat = str(row.get("matricula"))
        des_row_df = deslig.loc[deslig.get("matricula") == mat] if "matricula" in deslig.columns else pd.DataFrame()
        des_row = des_row_df.iloc[0].to_dict() if not des_row_df.empty else None

        if _apply_termination_rule(row, des_row, settings.competencia):
            dias_liq = 0
        else:
            start, end = _effective_window(row, settings.competencia)
            dias = business_days_set(
                cal,
                row.get("sindicato_codigo"),
                row.get("lotacao_uf"),
                row.get("lotacao_municipio"),
                start,
                end,
            )
            dias_liq = len(dias)


            if ferias_contagem:
                dias_liq = max(0, dias_liq - int(ferias_contagem.get(mat, 0) or 0))

        vr_unit = float(row.get("valor_vr", 0) or 0)
        vr_total = dias_liq * vr_unit

        out_rows.append(
            {
                "matricula": mat,
                "nome": row.get("nome"),
                "cpf": row.get("cpf"),
                "sindicato": row.get("sindicato"),
                "lotacao_uf": row.get("lotacao_uf"),
                "competencia": settings.competencia.strftime("%Y-%m"),
                "dias_uteis_mes": dias_liq,
                "vr_unitario": vr_unit,
                "vr_total": vr_total,
                "custo_empresa": vr_total * 0.80,
                "custo_profissional": vr_total * 0.20,
            }
        )

    df_out = pd.DataFrame(out_rows)


    try:
        total = len(df_out)
        z_dias = int((df_out["dias_uteis_mes"] == 0).sum())
        z_valor = int((df_out["vr_unitario"] == 0).sum())
        ambos = int(((df_out["dias_uteis_mes"] == 0) & (df_out["vr_unitario"] == 0)).sum())
        print(f"[diag] linhas: {total} | dias_0: {z_dias} | vr_0: {z_valor} | ambos_0: {ambos}")
        if z_valor:
            am = df_out.loc[df_out["vr_unitario"] == 0, ["matricula","sindicato","lotacao_uf"]].head(8)
            print("[diag] exemplos vr_unitario=0:", am.to_dict(orient="records"))
    except Exception:
        pass

    return df_out




def export_to_layout(df_final: pd.DataFrame, erros: pd.DataFrame, avisos: pd.DataFrame, settings) -> str:
    settings.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.out_dir / f"VR Mensal {settings.competencia.strftime('%m.%Y')}.xlsx"
    write_xlsx(out_path, df_final, erros, avisos)
    print(f"[tools] Arquivo gerado em: {out_path}")
    return str(out_path)
