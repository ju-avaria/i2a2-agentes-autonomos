# core/ncm_taxonomy.py
from typing import Optional, Tuple, List

# Faixas de capítulos → setor macro
_CAP_TO_SETOR = [
    ((1, 5),   "agronegocio_animal"),
    ((6, 14),  "agronegocio_vegetal"),
    ((15, 15), "oleos_gorduras"),
    ((16, 24), "alimentos_bebidas_tabaco"),
    ((25, 27), "minerais_energia"),
    ((28, 38), "quimicos_farmacos"),
    ((39, 40), "plasticos_borracha"),
    ((41, 43), "couro_moda"),
    ((44, 46), "madeira_cortica"),
    ((47, 49), "papel_grafica"),
    ((50, 63), "têxtil_vestuário"),
    ((64, 67), "calcados_acessorios"),
    ((68, 70), "construcao_ceramica_vidro"),
    ((71, 71), "joias_pedras_preciosas"),
    ((72, 83), "metais_fabricacao"),
    ((84, 85), "maquinas_eletronicos"),
    ((86, 89), "transporte"),
    ((90, 92), "instrumentos_medicao_saude"),
    ((93, 93), "armas_municoes"),            # pode virar alerta de compliance
    ((94, 96), "diversos_moveis_brinq"),
    ((97, 97), "arte_antiguidades"),
]

# Sugestões simples de Centros de Custo por setor macro
_SETOR_TO_CC = {
    "maquinas_eletronicos": ["TI", "Engenharia"],
    "plasticos_borracha":   ["Produção"],
    "metais_fabricacao":    ["Manutenção", "Produção"],
    "construcao_ceramica_vidro": ["Obras", "Manutenção"],
    "agronegocio_animal":   ["Agro"],
    "agronegocio_vegetal":  ["Agro"],
    "alimentos_bebidas_tabaco": ["Alimentos"],
    "minerais_energia":     ["Energia"],
    "quimicos_farmacos":    ["P&D", "Qualidade"],
    "papel_grafica":        ["Gráfica"],
    "têxtil_vestuário":     ["Moda"],
    "calcados_acessorios":  ["Moda"],
    "couro_moda":           ["Moda"],
    "transporte":           ["Logística"],
    "instrumentos_medicao_saude": ["P&D", "Saúde"],
    "oleos_gorduras":       ["Alimentos"],
    "diversos_moveis_brinq":["Administração"],
    "joias_pedras_preciosas":["Patrimônio"],
    "arte_antiguidades":    ["Patrimônio"],
    "armas_municoes":       ["Compliance"],  # marcar atenção
}

def _capitulo(ncm: str) -> Optional[int]:
    if not ncm: return None
    s = "".join(ch for ch in str(ncm) if ch.isdigit())
    if len(s) < 2: return None
    return int(s[:2])

def setor_por_capitulo(cap: Optional[int]) -> Optional[str]:
    if cap is None: return None
    for (ini, fim), setor in _CAP_TO_SETOR:
        if ini <= cap <= fim:
            return setor
    return None

def centros_custo_por_setor(setor: Optional[str]) -> List[str]:
    if not setor: return []
    return _SETOR_TO_CC.get(setor, [])

def inferir_tipo_basico(cap: Optional[int]) -> str:
    # Heurística leve: capítulos “serviço-like” quase não existem na NCM.
    # Se vier NCM válida, assuma mercadoria; sem NCM e descrição com “serviço”, trate como serviço.
    if cap is None: return "indefinido"
    return "compra/venda"

def inferir_setor_e_cc_por_ncm(ncm: str) -> Tuple[Optional[str], List[str]]:
    cap = _capitulo(ncm)
    setor = setor_por_capitulo(cap)
    ccs = centros_custo_por_setor(setor)
    return setor, ccs
