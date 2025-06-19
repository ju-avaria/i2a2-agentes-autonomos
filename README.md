<h1 align="center"> AssistenteMEI: Agente Inteligente de Notas Fiscais</h1>

<p align="center">
  <img src="imgs/logo_i2a2.png" alt="i2a2 Logo" width="180"/>
  &nbsp;&nbsp;&nbsp;&nbsp;
  <img src="imgs/LOGO.png" alt="AssistenteMEI Logo" width="110"/>
</p>


<p align="center">
  Projeto desenvolvido no curso:. Utiliza LLM local para responder perguntas sobre dados fiscais com interface acessível via navegador.
</p>

![Docker](https://img.shields.io/badge/docker-ready-blue)
![LLM](https://img.shields.io/badge/LLM-local-lightgrey)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Acesse online: https://testeia-production.up.railway.app/


![image](https://github.com/user-attachments/assets/971dd4c8-2136-4643-a8fc-138baa80506c)

## Tecnologias Utilizadas: 

[![LangChain](https://img.shields.io/badge/LangChain-4B8BBE?style=for-the-badge&logo=python&logoColor=white)](https://www.langchain.com/)
[![llama-cpp-python](https://img.shields.io/badge/llama--cpp--python-FFB000?style=for-the-badge)](https://github.com/abetlen/llama-cpp-python)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Git LFS](https://img.shields.io/badge/Git_LFS-F1502F?style=for-the-badge&logo=git&logoColor=white)](https://git-lfs.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

## Como funciona? 


<table>
  <tr>
    <td><strong>📁 Upload do ZIP</strong></td>
    <td>O usuário envia um arquivo <code>.zip</code> contendo planilhas de notas fiscais (arquivos CSV).</td>
  </tr>
  <tr>
    <td><strong>📂 Extração dos Arquivos</strong></td>
    <td>A aplicação extrai automaticamente os arquivos CSV para leitura.</td>
  </tr>
  <tr>
    <td><strong>👁️ Visualização</strong></td>
    <td>É possível visualizar os dados e selecionar colunas relevantes.</td>
  </tr>
  <tr>
    <td><strong>🧠 Perguntas</strong></td>
    <td>O usuário pode fazer perguntas em linguagem natural sobre os dados carregados.</td>
  </tr>
  <tr>
    <td><strong>💬 Respostas Inteligentes</strong></td>
    <td>As respostas são geradas por um agente local baseado em <code>LangChain</code> e <code>LLM (.gguf)</code> executado com <code>llama-cpp-python</code>.</td>
  </tr>
</table>

⚠️ Limitações do Modelo

Este agente utiliza um modelo de linguagem leve (tinyllama.gguf) executado localmente. Apesar de ser eficiente e funcional para perguntas simples, ele pode apresentar:

    Respostas incoerentes ou genéricas;

    Dificuldade com perguntas complexas ou ambíguas;

    Alucinação de valores ou inferências que não estão nos dados.
    
Abaixo estão algumas perguntas em **linguagem natural** que você pode fazer ao agente após carregar um arquivo CSV de notas fiscais:

- 📊 **Qual o valor total das notas fiscais?**
- 🔍 **Quantas notas foram emitidas no mês?**
- 🏷️ **Quais são os CNPJs únicos presentes no arquivo?**
- 📅 **Qual a data da primeira nota fiscal emitida?**
- 💵 **Qual a nota com maior valor?**
- 
![Captura de tela de 2025-06-18 13-11-28](https://github.com/user-attachments/assets/14bbbd0e-4ad8-4dbd-85fd-78beb2813805)


<h2>Rodando Localmente com Docker</h2>

<ol>
  <li><strong>Instale o Docker</strong><br>
    <ul>
      <li><a href="https://docs.docker.com/engine/install/">Linux/macOS</a></li>
      <li><a href="https://docs.docker.com/desktop/install/windows-install/">Windows</a></li>
    </ul>
  </li>

  <li><strong>Clone o repositório</strong><br>
    <pre><code>git clone https://github.com/ju-avaria/i2a2-agentes-autonomos.git
cd i2a2-agentes-autonomos</code></pre>
  </li>

  <li><strong>Construa a imagem Docker</strong><br>
    <pre><code>docker build -t assistentemei .</code></pre>
  </li>

  <li><strong>Rode o contêiner</strong><br>
    <pre><code>docker run -p 8501:8501 assistentemei</code></pre>
  </li>

  <li><strong>Acesse no navegador</strong><br>
    <pre><code>http://localhost:8501</code></pre>
  </li>
</ol>

PS: Este projeto está em constante desenvolvimento como parte do curso de Agentes Autônomos.

Agradecemos por visitar este repositório!  
Estamos continuamente aprimorando a solução à medida que avançamos no conteúdo da disciplina.

<strong>Com ❤️ por Juan Avaria e Nadianne Galvão  💻</strong>

