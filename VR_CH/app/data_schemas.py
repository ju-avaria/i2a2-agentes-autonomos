import pandas as pd


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore").str.decode("ascii")
    )
    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if ("data" in c) or c.endswith(("_inicio", "_fim")):
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df
