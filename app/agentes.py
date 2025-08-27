"""Definição dos agentes com LangGraph: cada agente usa ferramentas determinísticas.
O LLM (Ollama) apenas coordena/consulta contexto (RAG)."""

from typing import TypedDict, Any

from langgraph.graph import StateGraph, END
from langchain_community.chat_models import ChatOllama

from vectorstore_setup import get_chroma_collection
from tools import (
    load_bases,
    run_prevalidations,
    apply_exclusions,
    compute_days_and_values,
    export_to_layout,
)


class PipelineState(TypedDict):
    settings: Any
    docs_ctx: str
    dfs: dict
    erros: Any
    avisos: Any
    df_final: Any
    export_path: str


def make_llm(base_url: str, model: str):
    return ChatOllama(base_url=base_url, model=model, temperature=0)


def retrieval_node(state: PipelineState) -> PipelineState:
    coll = get_chroma_collection(state["settings"].chroma_host, state["settings"].chroma_port)
    results = coll.query(query_texts=["regras sindicato, validações e layout VR"], n_results=3)
    docs_lists = results.get("documents") or []
    docs = docs_lists[0] if docs_lists else []
    state["docs_ctx"] = "\n\n".join(docs)
    return state


def ingestion_node(state: PipelineState) -> PipelineState:
    dfs = load_bases(state["settings"])
    state["dfs"] = dfs
    return state


def validation_node(state: PipelineState) -> PipelineState:
    erros, avisos = run_prevalidations(state["dfs"], state["settings"])
    state["erros"] = erros
    state["avisos"] = avisos
    return state


def exclusion_node(state: PipelineState) -> PipelineState:
    df_consol, df_excl = apply_exclusions(state["dfs"], state["settings"])
    state["dfs"]["consolidada"] = df_consol
    state["dfs"]["excluidos"] = df_excl
    return state


def compute_node(state: PipelineState) -> PipelineState:
    df_final = compute_days_and_values(state["dfs"], state["settings"])
    state["df_final"] = df_final
    return state


def export_node(state: PipelineState) -> PipelineState:
    path = export_to_layout(state["df_final"], state.get("erros"), state.get("avisos"), state["settings"])
    state["export_path"] = path
    return state


def build_graph(llm) -> Any:
    g = StateGraph(PipelineState)
    g.add_node("retrieval", retrieval_node)
    g.add_node("ingestion", ingestion_node)
    g.add_node("validation", validation_node)
    g.add_node("exclusion", exclusion_node)
    g.add_node("compute", compute_node)
    g.add_node("export", export_node)

    g.set_entry_point("retrieval")
    g.add_edge("retrieval", "ingestion")
    g.add_edge("ingestion", "validation")
    g.add_edge("validation", "exclusion")
    g.add_edge("exclusion", "compute")
    g.add_edge("compute", "export")
    g.add_edge("export", END)
    return g.compile()
