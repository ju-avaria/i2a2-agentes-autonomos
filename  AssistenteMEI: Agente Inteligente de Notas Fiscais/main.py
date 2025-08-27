import streamlit as st
import zipfile
import os
import pandas as pd
import csv
from agentes.agente_llmchain import criar_agente_simples
from PIL import Image
import base64

# Logo centralizada
logo_path = "imgs/LOGO.png"
if os.path.exists(logo_path):
    with open(logo_path, "rb") as img_file:
        encoded_image = base64.b64encode(img_file.read()).decode()
        st.markdown(
            f"""
            <div style="text-align: center;">
                <img src="data:image/png;base64,{encoded_image}" width="180"/>
            </div>
            """,
            unsafe_allow_html=True
        )

st.title("AssistenteMei (LangChain + Llama)")

def detectar_delimitador(caminho_csv):
    with open(caminho_csv, 'r', encoding='utf-8') as f:
        amostra = f.read(1024)
        try:
            return csv.Sniffer().sniff(amostra).delimiter
        except Exception:
            return ";"

uploaded_zip = st.file_uploader("Envie o seu arquivo ZIP contendo os CSVs:", type="zip")

if uploaded_zip:
    extract_path = "/tmp/dados_extracao"
    os.makedirs(extract_path, exist_ok=True)
    for f in os.listdir(extract_path):
        os.remove(os.path.join(extract_path, f))

    with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

    csv_files = [f for f in os.listdir(extract_path) if f.endswith('.csv')]
    file_choice = st.selectbox("Selecione um arquivo CSV:", csv_files)

    if file_choice:
        csv_path = os.path.join(extract_path, file_choice)

        try:
            sep = detectar_delimitador(csv_path)
            df = pd.read_csv(csv_path, sep=sep, on_bad_lines="skip", encoding='utf-8')
            st.subheader("Visualização dos dados")
            st.dataframe(df.head(10), use_container_width=True)

            max_linhas = st.slider("Quantas linhas dos dados devem ser usadas para responder à pergunta:",
                                   min_value=5, max_value=len(df), value=min(100, len(df)), step=5)
            df_reduzido = df.head(max_linhas)

            colunas_disponiveis = list(df.columns)
            colunas_selecionadas = st.multiselect("Selecione as colunas que o agente deve considerar:",
                                                  options=colunas_disponiveis,
                                                  default=["VALOR NOTA FISCAL"] if "VALOR NOTA FISCAL" in df.columns else colunas_disponiveis[:3])

            contexto_csv = df_reduzido[colunas_selecionadas].to_string(index=False)
            pergunta = st.text_input("Digite sua pergunta sobre os dados:")

            if pergunta:
                try:
                    pergunta_lower = pergunta.lower()

                    col_valor = 'VALOR NOTA FISCAL'
                    col_cliente = 'CNPJ DESTINATÁRIO'
                    col_uf = 'UF DESTINATÁRIO'
                    col_municipio = 'MUNICÍPIO DESTINATÁRIO'
                    col_data = 'DATA EMISSÃO'

                    if "valor total" in pergunta_lower and "venda" in pergunta_lower:
                        resposta = f"R$ {df_reduzido[col_valor].sum():,.2f}" if col_valor in df_reduzido.columns else "Coluna de valor não encontrada."

                    elif "maior valor" in pergunta_lower:
                        resposta = f"R$ {df_reduzido[col_valor].max():,.2f}" if col_valor in df_reduzido.columns else "Coluna de valor não encontrada."

                    elif "menor valor" in pergunta_lower:
                        resposta = f"R$ {df_reduzido[col_valor].min():,.2f}" if col_valor in df_reduzido.columns else "Coluna de valor não encontrada."

                    elif "quantas notas" in pergunta_lower:
                        resposta = f"{len(df_reduzido)} notas fiscais"

                    elif "média" in pergunta_lower and "valor" in pergunta_lower:
                        resposta = f"R$ {df_reduzido[col_valor].mean():,.2f}" if col_valor in df_reduzido.columns else "Coluna de valor não encontrada."

                    elif "cliente que mais comprou" in pergunta_lower:
                        if col_cliente in df_reduzido.columns:
                            top_cliente = df_reduzido.groupby(col_cliente)[col_valor].sum().idxmax()
                            resposta = f"{top_cliente}"
                        else:
                            resposta = "Coluna de cliente não encontrada."

                    elif "clientes únicos" in pergunta_lower:
                        resposta = f"{df_reduzido[col_cliente].nunique()} clientes únicos" if col_cliente in df_reduzido.columns else "Coluna de cliente não encontrada."

                    elif "top 5 clientes" in pergunta_lower:
                        if col_cliente in df_reduzido.columns:
                            top5 = df_reduzido.groupby(col_cliente)[col_valor].sum().nlargest(5)
                            resposta = top5.to_string()
                        else:
                            resposta = "Coluna de cliente não encontrada."

                    elif "estado com maior valor" in pergunta_lower:
                        if col_uf in df_reduzido.columns and col_valor in df_reduzido.columns:
                            estado = df_reduzido.groupby(col_uf)[col_valor].sum().idxmax()
                            total = df_reduzido.groupby(col_uf)[col_valor].sum().max()
                            resposta = f"{estado} recebeu o maior valor em notas fiscais: R$ {total:,.2f}"
                        else:
                            resposta = "Colunas de UF ou valor não encontradas."

                    elif "estado que mais recebeu" in pergunta_lower:
                        if col_uf in df_reduzido.columns:
                            estado = df_reduzido[col_uf].value_counts().idxmax()
                            resposta = f"{estado} foi o estado com mais notas fiscais."
                        else:
                            resposta = "Coluna de UF não encontrada."

                    elif "dentro do estado" in pergunta_lower or "fora do estado" in pergunta_lower:
                        if col_uf in df_reduzido.columns:
                            dentro = df_reduzido[df_reduzido[col_uf] == "SE"].shape[0]
                            fora = df_reduzido[df_reduzido[col_uf] != "SE"].shape[0]
                            resposta = f"{dentro} notas dentro de Sergipe e {fora} fora do estado."
                        else:
                            resposta = "Coluna de UF não encontrada."

                    elif "pessoa física" in pergunta_lower or "pessoa jurídica" in pergunta_lower:
                        if col_cliente in df_reduzido.columns:
                            juridicas = df_reduzido[df_reduzido[col_cliente].str.len() == 14].shape[0]
                            fisicas = df_reduzido[df_reduzido[col_cliente].str.len() == 11].shape[0]
                            resposta = f"{juridicas} para pessoas jurídicas e {fisicas} para pessoas físicas."
                        else:
                            resposta = "Coluna de CNPJ/CPF não encontrada."

                    elif "quantas cidades" in pergunta_lower:
                        resposta = f"Foram atendidas {df_reduzido[col_municipio].nunique()} cidades." if col_municipio in df_reduzido.columns else "Coluna de município não encontrada."

                    elif "dia com mais notas" in pergunta_lower:
                        if col_data in df_reduzido.columns:
                            df_reduzido[col_data] = pd.to_datetime(df_reduzido[col_data], errors='coerce')
                            dia = df_reduzido[col_data].dt.date.value_counts().idxmax()
                            resposta = f"O dia com mais notas foi {dia}"
                        else:
                            resposta = "Coluna de data não encontrada."

                    elif "média de notas por cliente" in pergunta_lower:
                        if col_cliente in df_reduzido.columns:
                            media = df_reduzido.groupby(col_cliente).size().mean()
                            resposta = f"A média é de {media:.2f} notas por cliente."
                        else:
                            resposta = "Coluna de cliente não encontrada."

                    else:
                        agente = criar_agente_simples()
                        resposta = agente.invoke({"contexto": contexto_csv, "pergunta": pergunta}).strip()

                    st.success(resposta)

                except Exception as e:
                    st.error(f"Erro ao processar a pergunta: {e}")

        except Exception as e:
            st.error(f"Erro ao ler o CSV: {e}")

