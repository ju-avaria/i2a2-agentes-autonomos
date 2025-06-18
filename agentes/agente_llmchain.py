from langchain_community.llms import LlamaCpp
from langchain.prompts import PromptTemplate
import os

def criar_agente_simples():
    modelo_path = os.path.abspath("modelos/tinyllama.gguf")

    llm = LlamaCpp(
        model_path=modelo_path,
        temperature=0.1,
        max_tokens=512,
        model_kwargs={"n_ctx": 2048},
        verbose=False
    )

    prompt = PromptTemplate(
        input_variables=["contexto", "pergunta"],
        template="""
Você é um agente inteligente treinado para responder perguntas sobre dados fiscais.

Aqui está uma amostra dos dados:

{contexto}

Com base nesses dados, responda à seguinte pergunta:

{pergunta}
"""
    )


    chain = prompt | llm
    return chain

