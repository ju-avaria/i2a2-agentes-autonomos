<img width="1570" height="826" alt="image" src="https://github.com/user-attachments/assets/7572e69b-fb55-453f-b4c3-580a15b78577" />

# IA-NF — Agente de Validação de NF-e
https://n97sxfqlvafvrvni5z3ykb.streamlit.app/

O **IA-NF** é um agente que ajuda você a **analisar notas fiscais eletrônicas (NF-e em XML)** de forma rápida e clara.  
Ele lê a nota, confere informações importantes (como CNPJ, chave e IE por UF), sugere **CFOP** e aponta **alertas de inconsistência** com explicações simples.

---

## O que ele faz

- **Lê arquivos XML de NF-e** e organiza as informações de um jeito fácil de entender.
- **Verifica dados-chave** (ex.: CNPJ, chave de acesso, IE por estado).
- **Sugere CFOP** com base nas regras e no contexto da nota.
- **Apresenta alertas e dicas** quando encontra algo estranho.
- **Mostra resultados claros**, prontos para revisão ou conferência.

---

## Para quem é?

- Pessoas e equipes que **precisam conferir NF-e** com rapidez.
- **Auditoria e conferência** de documentos, com foco em clareza e explicações.
- Quem quer **reduzir erros** e padronizar a checagem.

---

## Como usar (visão geral)

1. **Abra o aplicativo** (interface simples em páginas).
2. **Envie o arquivo XML** da NF-e.
3. **Veja o painel de resultados** com os dados organizados.
4. Confira **alertas, explicações e sugestões de CFOP**.
5. **Baixe o PDF** com o relatório sobre suas notas.

> Dica: mantenha seus arquivos XML bem nomeados (ex.: `NF-12345.xml`) para achar tudo rápido.


## Privacidade & Segurança

- Os arquivos são usados apenas para a análise no próprio ambiente.
- Há uma **triagem inicial** para evitar arquivos suspeitos.
- Recomendamos manter suas notas em **pastas organizadas** e fazer backup seguro.

> Importante: este agente **não substitui** uma orientação fiscal/contábil oficial. Use os resultados como apoio à decisão.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
MIT License

Copyright (c) 2025 Nadianne

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the “Software”), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
