# validadores/ie_centro_oeste.py
# Inscrição Estadual – Regras (Sintegra) para a Região Centro-Oeste
# MT, MS, GO  (DF será adicionado quando a regra oficial for enviada)

from typing import Dict, Callable, Tuple, Any

# ========= Helpers comuns =========
def _digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())

def _to_int_list(s: str) -> list[int]:
    return [int(c) for c in s]

def _weighted_sum(nums: list[int], weights: list[int]) -> int:
    return sum(n * w for n, w in zip(nums, weights))

def _dv_mod11(total: int, zero_if: Tuple[int, ...] = (0, 1)) -> int:
    r = total % 11
    return 0 if r in zero_if else 11 - r

def _result(uf: str, ie_in: str, dv_calc: Any, dv_real: Any, motivo: str, valida: bool | None = None) -> dict:
    dv_calc_s = "" if dv_calc is None else str(dv_calc)
    dv_real_s = "" if dv_real is None else str(dv_real)
    if valida is None:
        valida = dv_calc_s == dv_real_s and dv_calc_s != ""
    return {
        "uf": uf,
        "valida": valida,
        "dv_calculado": dv_calc_s,
        "dv_real": dv_real_s,
        "motivo": motivo,
        "ie": ie_in,
    }

# ========= MT – Mato Grosso =========
# Formato: 10 dígitos + 1 DV (NNNNNNNNNN-D)
# Pesos: 3,2,9,8,7,6,5,4,3,2  sobre os 10 primeiros; Mod 11 (0/1 -> 0)
def valida_ie_mt(ie: str) -> dict:
    uf = "MT"
    ie_num = _digits(ie)
    if len(ie_num) != 11:
        # alguns materiais mostram "NNNNNNNNNN-D" (10+1) → total 11 caracteres numéricos
        return _result(uf, ie_num, None, ie_num[-1] if ie_num else None, f"Tamanho inválido ({len(ie_num)} dígitos)", False)

    base10 = _to_int_list(ie_num[:-1])
    dv_in = ie_num[-1]
    pesos = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = _weighted_sum(base10, pesos)
    dv = _dv_mod11(soma, zero_if=(0, 1))
    return _result(uf, ie_num, dv, dv_in, "Módulo 11 (pesos 3,2,9..2)")

# ========= MS – Mato Grosso do Sul =========
# Formato: 8 + 1 (total 9). Prefixo deve ser 28 ou 50.
# Pesos 9..2; DV = 0 se resto ∈ {0,1}, senão 11-resto (equivalente ao mod11 com zero_if (0,1))
def valida_ie_ms(ie: str) -> dict:
    uf = "MS"
    ie_num = _digits(ie)
    if len(ie_num) != 9:
        return _result(uf, ie_num, None, ie_num[-1] if ie_num else None, f"Tamanho inválido ({len(ie_num)} dígitos)", False)
    if not (ie_num.startswith("28") or ie_num.startswith("50")):
        return _result(uf, ie_num, None, ie_num[-1], "Prefixo inválido (deve iniciar por 28 ou 50)", False)

    base8 = _to_int_list(ie_num[:-1])
    dv_in = ie_num[-1]
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = _weighted_sum(base8, pesos)
    dv = _dv_mod11(soma, zero_if=(0, 1))
    return _result(uf, ie_num, dv, dv_in, "Módulo 11 (pesos 9-2), regra MS")

# ========= GO – Goiás =========
# Formato: 8 + 1 (AB.CDE.FGH-I). AB ∈ {10, 11} ∪ [20..29].
# Pesos 9..2; Mod 11 (0/1 -> 0)
def valida_ie_go(ie: str) -> dict:
    uf = "GO"
    ie_num = _digits(ie)
    if len(ie_num) != 9:
        return _result(uf, ie_num, None, ie_num[-1] if ie_num else None, f"Tamanho inválido ({len(ie_num)} dígitos)", False)

    ab = int(ie_num[:2])
    if not (ab in (10, 11) or 20 <= ab <= 29):
        return _result(uf, ie_num, None, ie_num[-1], "Prefixo inválido (AB deve ser 10,11 ou 20..29)", False)

    base8 = _to_int_list(ie_num[:-1])
    dv_in = ie_num[-1]
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = _weighted_sum(base8, pesos)
    dv = _dv_mod11(soma, zero_if=(0, 1))
    return _result(uf, ie_num, dv, dv_in, "Módulo 11 (pesos 9-2), regra GO")

# ========= Dispatcher Centro-Oeste =========
VALIDADORES_CO: Dict[str, Callable[[str], dict]] = {
    "MT": valida_ie_mt,
    "MS": valida_ie_ms,
    "GO": valida_ie_go,
    # "DF": valida_ie_df,  # ← adicionaremos quando você enviar a regra oficial do DF
}

def valida_ie_centro_oeste(uf: str, ie: str) -> dict:
    uf = (uf or "").upper().strip()
    f = VALIDADORES_CO.get(uf)
    if not f:
        return _result(uf, _digits(ie), None, None, f"UF {uf} sem regra implementada", False)
    return f(ie)
