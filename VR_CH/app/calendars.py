import pandas as pd
from datetime import date

def business_days_set(
    df_cal: pd.DataFrame,
    sindicato: str,
    uf: str,
    municipio: str,
    start: date,
    end: date
) -> set:
    dfc = df_cal.copy()

    if not pd.api.types.is_datetime64_any_dtype(dfc["data"]):
        dfc["data"] = pd.to_datetime(dfc["data"], errors="coerce")

    # janela
    mask = (dfc["data"] >= pd.to_datetime(start)) & (dfc["data"] <= pd.to_datetime(end))

    def _has(x):
        return (x is not None) and (str(x).strip() != "") and (str(x).lower() != "nan")

    if "sindicato_codigo" in dfc.columns and _has(sindicato):
        mask &= dfc["sindicato_codigo"].astype(str) == str(sindicato)

    if "uf" in dfc.columns and _has(uf):
        mask &= dfc["uf"].astype(str).str.upper() == str(uf).upper()

    if "municipio" in dfc.columns and _has(municipio):

        left = dfc["municipio"].astype(str).str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii").str.lower()
        right = (
            str(municipio)
            .normalize("NFKD")
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
            if hasattr(str(municipio), "normalize") else str(municipio).lower()
        )
        mask &= left == right

    if "eh_dia_util" in dfc.columns:
        mask &= dfc["eh_dia_util"].astype(bool)

    dias_series = dfc.loc[mask, "data"]

    if dias_series.empty:
        base = dfc[(dfc["data"] >= pd.to_datetime(start)) & (dfc["data"] <= pd.to_datetime(end))]
        if "eh_dia_util" in base.columns:
            base = base[base["eh_dia_util"].astype(bool)]
        dias_series = base["data"]

    return set(dias_series.dt.date.unique().tolist())
