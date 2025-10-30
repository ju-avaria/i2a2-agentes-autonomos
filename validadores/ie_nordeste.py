# validadores/ie_nordeste.py
# Inscrição Estadual – Regras oficiais (Sintegra) para a Região Nordeste
# MA, PI, CE, RN (9/10), PE (2 dígitos), PB, SE, AL, BA (8/9, mod10 ou mod11)

from typing import Dict, Callable, Tuple, Any

# ==========================
#  FUNÇÕES AUXILIARES
# ==========================
def _digits(s: str) -> str:
    """Extrai apenas dígitos de uma string."""
    return "".join(ch for ch in s if ch.isdigit())

def _to_int_list(s: str) -> list[int]:
    """Converte string de dígitos para lista de inteiros."""
    return [int(c) for c in s]

def _weighted_sum(nums: list[int], weights: list[int]) -> int:
    """Calcula a soma ponderada dos números e pesos (da esquerda para a direita)."""
    return sum(n * w for n, w in zip(nums, weights))

def _dv_mod10(total: int) -> int:
    """Calcula DV pelo Módulo 10. Se resto 0, DV é 0. Senão, 10 - resto."""
    resto = total % 10
    return 0 if resto == 0 else 10 - resto

def _dv_mod11(total: int, zero_if: Tuple[int, ...] = (0, 1)) -> int:
    """
    Calcula DV pelo Módulo 11. 
    Se resto em `zero_if`, DV é 0. Senão, 11 - resto.
    """
    resto = total % 11
    return 0 if resto in zero_if else 11 - resto

# --- Saída Padronizada ---
def _result(uf: str, ie_in: str, dv_calc: Any, dv_real: Any, motivo: str, valida: bool = None) -> dict:
    """Função auxiliar para padronizar o dicionário de saída."""
    dv_calc_str = str(dv_calc)
    dv_real_str = str(dv_real)
    
    if valida is None:
        valida = dv_calc_str == dv_real_str
        
    return {
        "uf": uf,
        "valida": valida,
        "dv_calculado": dv_calc_str,
        "dv_real": dv_real_str,
        "motivo": motivo,
    }


# ==========================
#  VALIDADORES POR ESTADO
# ==========================

# -------------------- MA (Maranhão), PI (Piauí), CE (Ceará), PB (Paraíba), SE (Sergipe) --------------------
# Todos usam Módulo 11 (pesos 9-2). Se 10 ou 11 -> 0.
def _valida_ie_padrao_mod11_9digitos(uf: str, ie: str) -> dict:
    ie = _digits(ie)
    if len(ie) != 9:
        return _result(uf, ie, "", ie[-1] if len(ie) > 0 else "", f"Tamanho inválido ({len(ie)} dígitos)", False)

    base = _to_int_list(ie[:-1])  # 8 dígitos
    dv_in = ie[-1]
    
    # Roteiro: MA: Deve começar com '12'
    if uf == "MA" and not ie.startswith("12"):
        return _result(uf, ie, "", dv_in, "Prefixo inválido (MA deve começar com 12)", False)
    
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = _weighted_sum(base, pesos)
    dv = _dv_mod11(soma, zero_if=(0, 1))

    return _result(uf, ie, dv, dv_in, "Módulo 11 (pesos 9-2) aplicado")

def valida_ie_ma(ie: str) -> dict:
    return _valida_ie_padrao_mod11_9digitos("MA", ie)

def valida_ie_pi(ie: str) -> dict:
    return _valida_ie_padrao_mod11_9digitos("PI", ie)

def valida_ie_ce(ie: str) -> dict:
    return _valida_ie_padrao_mod11_9digitos("CE", ie)

def valida_ie_pb(ie: str) -> dict:
    return _valida_ie_padrao_mod11_9digitos("PB", ie)

def valida_ie_se(ie: str) -> dict:
    return _valida_ie_padrao_mod11_9digitos("SE", ie)


# -------------------- RN (Rio Grande do Norte) - CORRIGIDA ---------------------
def _valida_rn(ie: str, uf: str, pesos: list[int], motivo_len: str) -> dict:
    base = _to_int_list(ie[:-1])
    dv_in = ie[-1]
    
    soma = _weighted_sum(base, pesos)
    
    # Regra peculiar do RN: (Soma * 10) % 11. Se resto 10, DV é 0. Senão, o DV é o resto.
    dv_calc_bruto = (soma * 10) % 11
    dv = 0 if dv_calc_bruto == 10 else dv_calc_bruto
    
    return _result(uf, ie, dv, dv_in, f"Módulo 11 (Soma*10)/11. {motivo_len}")

def valida_ie_rn(ie: str) -> dict:
    ie = _digits(ie)
    
    if not ie.startswith("20"):
        return _result("RN", ie, "", "", "Prefixo inválido (RN deve começar com 20)", False)
        
    if len(ie) == 9:
        pesos = [9, 8, 7, 6, 5, 4, 3, 2]
        return _valida_rn(ie, "RN", pesos, "9 dígitos")
    elif len(ie) == 10:
        pesos = [10, 9, 8, 7, 6, 5, 4, 3, 2]
        return _valida_rn(ie, "RN", pesos, "10 dígitos")
    else:
        return _result("RN", ie, "", ie[-1] if len(ie) > 0 else "", f"Tamanho inválido ({len(ie)} dígitos)", False)


# -------------------- PE (Pernambuco) -------------------
def valida_ie_pe(ie: str) -> dict:
    ie = _digits(ie)
    if len(ie) != 9:
        return _result("PE", ie, "", "", f"Tamanho inválido ({len(ie)} dígitos)", False)
        
    nums = _to_int_list(ie)
    corpo7 = nums[:7]
    dv1_in, dv2_in = nums[7], nums[8]

    # 1º DV (d1): pesos 8..2 sobre 7 dígitos
    pesos1 = [8, 7, 6, 5, 4, 3, 2]
    soma1 = _weighted_sum(corpo7, pesos1)
    dv1 = _dv_mod11(soma1, zero_if=(0, 1))

    # 2º DV (d2): pesos 9..3 sobre 7 dígitos, e peso 2 para DV1
    # O roteiro oficial do e-Fisco (Java) usa 9..2 sobre 7 dígitos + d1. Isso é o mesmo que:
    # 9..3 sobre os 7 dígitos, e peso 2 sobre o d1.
    
    soma2 = dv1 * 2 # Peso 2 para o d1
    pesos2 = [9, 8, 7, 6, 5, 4, 3]
    soma2 += _weighted_sum(corpo7, pesos2)
    
    dv2 = _dv_mod11(soma2, zero_if=(0, 1))

    dv_calc = f"{dv1}{dv2}"
    dv_real = f"{dv1_in}{dv2_in}"
    
    return _result("PE", ie, dv_calc, dv_real, "Dois DVs (d1: pesos 8-2, d2: pesos 9-3 + d1*2)")


# -------------------- AL (Alagoas) ----------------------
def valida_ie_al(ie: str) -> dict:
    ie = _digits(ie)
    if len(ie) != 9 or not ie.startswith("24"):
        return _result("AL", ie, "", "", f"Tamanho/prefixo inválido (IE: {ie})", False)
        
    x = ie[2]
    if x not in "03578":
        return _result("AL", ie, "", "", f"Código de atividade inválido ({x})", False)
        
    base = _to_int_list(ie[:-1])  # 8 dígitos
    dv_in = ie[-1]
    
    # Pesos do roteiro: 9, 8, 7, 6, 5, 4, 3, 2 (aplicados da esquerda para a direita)
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = _weighted_sum(base, pesos)
    
    # Regra de cálculo: (soma * 10) % 11. Se 10 -> 0. Senão, o resto.
    dv_calc_bruto = (soma * 10) % 11
    dv = 0 if dv_calc_bruto == 10 else dv_calc_bruto
    
    return _result("AL", ie, dv, dv_in, "Módulo 11 (Soma*10)/11, prefixo 24X")


# -------------------- BA (Bahia) - CORRIGIDA ------------------------
def _ba_mod_by_first_digit(d: int) -> int:
    """Retorna 10 ou 11 baseado no 1º dígito da IE."""
    return 10 if d in (0, 1, 2, 3, 4, 5, 8) else 11

def _ba_mod_by_second_digit(d: int) -> int:
    """Retorna 10 ou 11 baseado no 2º dígito da IE."""
    return 10 if d in (0, 1, 2, 3, 4, 5, 8) else 11

def _ba_dv(total: int, modulo: int) -> int:
    """Calcula DV final baseado no módulo (10 ou 11)."""
    if modulo == 10:
        return _dv_mod10(total)
    else: # Modulo 11
        # Se for Mod11, zero_if é (0, 1) conforme o roteiro
        return _dv_mod11(total, zero_if=(0, 1))

def _valida_ba_8(ie: str, uf: str) -> dict:
    nums = _to_int_list(ie)
    base6 = nums[:6]
    dv2_in, dv1_in = nums[6], nums[7]               # <- define aqui
    modulo = _ba_mod_by_first_digit(nums[0])

    # calcula D2
    pesos2 = [7, 6, 5, 4, 3, 2]
    soma2 = _weighted_sum(base6, pesos2)
    d2 = _ba_dv(soma2, modulo)
    if d2 != dv2_in:
        # não use d1_in aqui (ainda não calculado)
        return _result(uf, ie, str(d2), str(dv2_in), f"2º dígito (D2) incorreto. Módulo {modulo}", False)

    # calcula D1
    pesos1 = [8, 7, 6, 5, 4, 3, 2]
    soma1 = _weighted_sum(base6 + [d2], pesos1)
    d1 = _ba_dv(soma1, modulo)

    dv_calc = f"{d2}{d1}"
    dv_real = f"{dv2_in}{dv1_in}"
    return _result(uf, ie, dv_calc, dv_real, f"Dois DVs. Módulo {modulo} pelo 1º dígito")

def _valida_ba_9(ie: str, uf: str) -> dict:
    nums = _to_int_list(ie)
    base7 = nums[:7]
    dv2_in, dv1_in = nums[7], nums[8]               # <- define aqui
    modulo = _ba_mod_by_second_digit(nums[1])

    # calcula D2
    pesos2 = [8, 7, 6, 5, 4, 3, 2]
    soma2 = _weighted_sum(base7, pesos2)
    d2 = _ba_dv(soma2, modulo)
    if d2 != dv2_in:
        return _result(uf, ie, str(d2), str(dv2_in), f"2º dígito (D2) incorreto. Módulo {modulo}", False)

    # calcula D1
    pesos1 = [9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = _weighted_sum(base7 + [d2], pesos1)
    d1 = _ba_dv(soma1, modulo)

    dv_calc = f"{d2}{d1}"
    dv_real = f"{dv2_in}{dv1_in}"
    return _result(uf, ie, dv_calc, dv_real, f"Dois DVs. Módulo {modulo} pelo 2º dígito")


def valida_ie_ba(ie: str) -> dict:
    ie = _digits(ie)
    if len(ie) == 8:
        return _valida_ba_8(ie, "BA")
    if len(ie) == 9:
        return _valida_ba_9(ie, "BA")
    return _result("BA", ie, "", "", f"Tamanho inválido ({len(ie)} dígitos)", False)

# ==========================
#  DISPATCHER (Nordeste)
# ==========================
VALIDADORES_NE: Dict[str, Callable[[str], dict]] = {
    "MA": valida_ie_ma,
    "PI": valida_ie_pi,
    "CE": valida_ie_ce,
    "RN": valida_ie_rn,
    "PE": valida_ie_pe,
    "PB": valida_ie_pb,
    "SE": valida_ie_se,
    "AL": valida_ie_al,
    "BA": valida_ie_ba,
}

def valida_ie_nordeste(uf: str, ie: str) -> dict:
    uf = (uf or "").upper().strip()
    ie_limpa = _digits(ie)
    f = VALIDADORES_NE.get(uf)
    
    if not f:
        return _result(uf, ie, "", "", f"UF {uf} sem regra implementada", False)
        
    return f(ie_limpa)