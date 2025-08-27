import pandas as pd
from typing import Tuple, Dict


def prevalidate(dfs: Dict[str, pd.DataFrame], settings) -> Tuple[pd.DataFrame, pd.DataFrame]:
    erros, avisos = [], []

    if "sindicato_valor" in dfs and "valor_vr" in dfs["sindicato_valor"].columns:
        if dfs["sindicato_valor"]["valor_vr"].isna().any():
            faltantes = dfs["sindicato_valor"][dfs["sindicato_valor"]["valor_vr"].isna()]["sindicato_codigo"].unique()
            for s in faltantes:
                erros.append({"codigo": "VIG001", "descricao": f"Sindicato {s} sem valor vigente."})

    # Datas quebradas em férias
    f = dfs.get("ferias", pd.DataFrame())
    if not f.empty and {"ferias_inicio", "ferias_fim"}.issubset(f.columns):
        mask_bad = pd.to_datetime(f["ferias_fim"]) < pd.to_datetime(f["ferias_inicio"])
        for _, row in f.loc[mask_bad].iterrows():
            avisos.append({"codigo": "DAT001", "descricao": f"Matr {row.get('matricula')}: ferias_fim < ferias_inicio"})

    return pd.DataFrame(erros), pd.DataFrame(avisos)
