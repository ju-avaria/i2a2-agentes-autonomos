# export_layout.py
import pandas as pd

def write_xlsx(path, df_final: pd.DataFrame, erros: pd.DataFrame, avisos: pd.DataFrame):

    try:
        writer = pd.ExcelWriter(path, engine="xlsxwriter")  
        use_xlsxwriter = True
    except Exception:
        writer = pd.ExcelWriter(path)  
        use_xlsxwriter = False

    with writer as xw:
        df_final.to_excel(xw, sheet_name="VR Mensal", index=False)

        if use_xlsxwriter:
            wb = xw.book
            ws = xw.sheets["VR Mensal"]

            header_fmt = wb.add_format({"bold": True, "bg_color": "#E6F0FF", "border": 1})
            money_fmt  = wb.add_format({"num_format": 'R$ #,##0.00'})
            int_fmt    = wb.add_format({"num_format": '0'})
            text_fmt   = wb.add_format({"num_format": '@'})

            for col_idx, name in enumerate(df_final.columns):
                ws.write(0, col_idx, name, header_fmt)

            def set_col_fmt(col_name, fmt, width=12):
                if col_name in df_final.columns:
                    i = df_final.columns.get_loc(col_name)
                    ws.set_column(i, i, width, fmt)


            for c in ["matricula","nome","cpf","sindicato","sindicato_codigo",
                      "lotacao_uf","lotacao_municipio","competencia"]:
                set_col_fmt(c, text_fmt, 18)


            set_col_fmt("dias_uteis_mes", int_fmt, 12)


            for c in ["vr_unitario","vr_total","custo_empresa","custo_profissional"]:
                set_col_fmt(c, money_fmt, 14)

        if isinstance(erros, pd.DataFrame) and not erros.empty:
            erros.to_excel(xw, sheet_name="Erros", index=False)
        if isinstance(avisos, pd.DataFrame) and not avisos.empty:
            avisos.to_excel(xw, sheet_name="Avisos", index=False)
