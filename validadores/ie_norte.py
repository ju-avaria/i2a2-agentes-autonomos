# validadores/ie_norte.py
"""
Validador de Inscrição Estadual (IE) - Região Norte
Baseado nas fórmulas oficiais publicadas pelo SINTEGRA.
Cada função retorna:
{
  "uf": "AM",
  "valida": True/False,
  "dv_calculado": "x",
  "dv_real": "y",
  "motivo": "descrição"
}
"""

import re

# ==========================
#  FUNÇÃO PRINCIPAL
# ==========================
def valida_ie(uf: str, ie: str) -> dict:
    ie = ''.join(filter(str.isdigit, ie or ""))
    uf = uf.upper()
    fn = VALIDADORES.get(uf)
    if not fn:
        return {"uf": uf, "valida": False, "motivo": "UF sem regra implementada"}
    return fn(ie)

# ================================================================
# AMAZONAS — Módulo 11 (pesos 9→2), soma < 11 → dígito = 11 - soma
# ================================================================
def valida_ie_am(ie: str) -> dict:
    if len(ie) != 9:
        return {"uf": "AM", "valida": False, "motivo": "Tamanho inválido"}
    numeros = list(map(int, ie[:-1]))
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(n * p for n, p in zip(numeros, pesos))
    resto = soma % 11
    # Lógica funcionalmente equivalente à regra: se 10 ou 11, DV é 0.
    dv = 11 - resto if resto >= 2 else 0 
    return {
        "uf": "AM",
        "valida": str(dv) == ie[-1],
        "dv_calculado": str(dv),
        "dv_real": ie[-1],
        "motivo": "Módulo 11 aplicado (pesos 9–2)",
    }

# ================================================================
# RORAIMA — Módulo 9 (posição * número)
# ================================================================
def valida_ie_rr(ie: str) -> dict:
    if len(ie) != 9 or not ie.startswith("24"):
        return {"uf": "RR", "valida": False, "motivo": "Formato inválido"}
    soma = sum((i + 1) * int(ie[i]) for i in range(8))
    dv = soma % 9
    return {
        "uf": "RR",
        "valida": str(dv) == ie[-1],
        "dv_calculado": str(dv),
        "dv_real": ie[-1],
        "motivo": "Módulo 9 aplicado (posição * número)",
    }

# ================================================================
# AMAPÁ — Faixas + Módulo 11
# ================================================================
def valida_ie_ap(ie: str) -> dict:
    if len(ie) != 9 or not ie.startswith("03"):
        return {"uf": "AP", "valida": False, "motivo": "Formato inválido"}
    
    # Faixas e valores p e d
    num = int(ie[:8])
    if 3000001 <= num <= 3017000:
        p, d = 5, 0
    elif 3017001 <= num <= 3019022:
        p, d = 9, 1
    else:
        p, d = 0, 0
        
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = p + sum(int(ie[i]) * pesos[i] for i in range(8))
    resto = soma % 11
    dig = 11 - resto
    
    # Tratamento de 10 e 11
    if dig == 10: dig = 0
    elif dig == 11: dig = d
    
    return {
        "uf": "AP",
        "valida": str(dig) == ie[-1],
        "dv_calculado": str(dig),
        "dv_real": ie[-1],
        "motivo": "Faixas + Módulo 11 aplicado",
    }

# ================================================================
# PARÁ — Módulo 11 (pesos 2–9, direita→esquerda)
# ================================================================
def valida_ie_pa(ie: str) -> dict:
    if len(ie) != 9 or ie[:2] not in {"15", "75", "76", "77", "78", "79"}:
        return {"uf": "PA", "valida": False, "motivo": "Prefixo inválido"}
        
    numeros = list(map(int, ie[:-1]))
    pesos = list(range(2, 10)) # Pesos: [2, 3, 4, 5, 6, 7, 8, 9]
    
    # Aplica os pesos da direita para a esquerda (zip(reversed(numeros), pesos))
    soma = sum(n * p for n, p in zip(reversed(numeros), pesos))
    resto = soma % 11
    
    # Se resto for 0 ou 1, DV é 0. Senão, 11 - resto.
    dv = 0 if resto in (0, 1) else 11 - resto
    
    return {
        "uf": "PA",
        "valida": str(dv) == ie[-1],
        "dv_calculado": str(dv),
        "dv_real": ie[-1],
        "motivo": "Módulo 11 aplicado (pesos 2–9)",
    }

# ================================================================
# TOCANTINS — Módulo 11 (ignora dígitos 3 e 4)
# ================================================================
def valida_ie_to(ie: str) -> dict:
    ie = ''.join(filter(str.isdigit, ie))
    if len(ie) != 9:
        return {"uf": "TO", "valida": False, "motivo": "Tamanho inválido"}

    tipo = ie[2:4]
    if tipo not in {"01", "02", "03", "99"}:
        return {"uf": "TO", "valida": False, "motivo": f"Código de atividade inválido ({tipo})"}

    base = [int(c) for i, c in enumerate(ie[:-1]) if i not in (2, 3)]
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(n * p for n, p in zip(base, pesos))
    resto = soma % 11
    dv = 0 if resto < 2 else 11 - resto
    return {
        "uf": "TO",
        "valida": str(dv) == ie[-1],
        "dv_calculado": str(dv),
        "dv_real": ie[-1],
        "motivo": f"Módulo 11 aplicado; tipo={tipo}",
    }

# ================================================================
# RONDÔNIA — duas fórmulas (antiga e nova) - CORRIGIDA
# ================================================================
def valida_ie_ro(ie: str) -> dict:
    ie = ''.join(filter(str.isdigit, ie))
    
    # Pesos completos para o formato novo (13 dígitos), da esquerda para a direita.
    PESOS_RO_COMPLETO = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    
    if len(ie) == 9:  # formato antigo: 3 dígitos (município) + 5 dígitos (empresa) + DV
        base = list(map(int, ie[3:-1])) # Apenas os 5 dígitos da empresa
        pesos_aplicar = [6, 5, 4, 3, 2] # Pesos para os 5 dígitos
    elif len(ie) == 14:  # formato novo: 13 dígitos + DV
        base = list(map(int, ie[:-1])) # Os 13 dígitos
        pesos_aplicar = PESOS_RO_COMPLETO # 13 pesos, um para cada dígito
    else:
        return {"uf": "RO", "valida": False, "motivo": "Tamanho inválido"}
    
    # A regra de RO aplica os pesos da esquerda para a direita
    soma = sum(n * p for n, p in zip(base, pesos_aplicar))
    
    resto = soma % 11
    dv = 11 - resto
    
    # No caso da diferença ser 10 ou 11, subtrai 10
    if dv >= 10: dv -= 10 
    
    return {
        "uf": "RO",
        "valida": str(dv) == ie[-1],
        "dv_calculado": str(dv),
        "dv_real": ie[-1],
        "motivo": "Regra dupla (antiga e nova) com módulo 11",
    }

# ================================================================
# ACRE — 2 dígitos verificadores, ambos módulo 11
# ================================================================
def valida_ie_ac(ie: str) -> dict:
    ie = ''.join(filter(str.isdigit, ie))
    if len(ie) != 13 or not ie.startswith("01"):
        return {"uf": "AC", "valida": False, "motivo": "Formato inválido"}
        
    base = [int(x) for x in ie[:-2]] # 11 dígitos
    
    # 1º DV (d1)
    pesos1 = [4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(x * y for x, y in zip(base, pesos1))
    resto1 = soma1 % 11
    # Se diferença for 10 ou 11 (resto 1 ou 0), d1 é 0.
    d1 = 11 - resto1 if resto1 >= 2 else 0 
    
    # 2º DV (d2)
    base2 = base + [d1] # 12 dígitos (inclui d1)
    pesos2 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma2 = sum(x * y for x, y in zip(base2, pesos2))
    resto2 = soma2 % 11
    # Se diferença for 10 ou 11 (resto 1 ou 0), d2 é 0.
    d2 = 11 - resto2 if resto2 >= 2 else 0
    
    return {
        "uf": "AC",
        "valida": ie[-2:] == f"{d1}{d2}",
        "dv_calculado": f"{d1}{d2}",
        "dv_real": ie[-2:],
        "motivo": "Dois dígitos verificadores (módulo 11)",
    }

# ================================================================
# REGISTRO CENTRAL
# ================================================================
VALIDADORES = {
    "AC": valida_ie_ac,
    "AM": valida_ie_am,
    "AP": valida_ie_ap,
    "PA": valida_ie_pa,
    "RO": valida_ie_ro,
    "RR": valida_ie_rr,
    "TO": valida_ie_to,
}