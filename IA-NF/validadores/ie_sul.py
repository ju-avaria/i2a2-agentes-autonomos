# validadores/ie_sul.py
# Regras oficiais (Sintegra/SEFAZ) — Região Sul
# RS, SC (implementados) + PR (stub aguardando regra)

from typing import Dict, Callable

# ==========================
#  HELPERS
# ==========================
def _digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _to_int_list(s: str) -> list[int]:
    return [int(c) for c in s]

def _weighted_sum(nums: list[int], weights: list[int]) -> int:
    return sum(n * w for n, w in zip(nums, weights))

def _dv_mod11_from_sum(total: int, zero_if=(0, 1)) -> int:
    r = total % 11
    return 0 if r in zero_if else 11 - r

def _result(uf: str, ie_in: str, dv_calc, dv_real, motivo: str, ok: bool | None = None) -> dict:
    if ok is None:
        ok = str(dv_calc) == str(dv_real)
    return {
        "uf": uf,
        "valida": bool(ok),
        "dv_calculado": str(dv_calc),
        "dv_real": str(dv_real),
        "motivo": motivo,
    }

# ==========================
#  RIO GRANDE DO SUL (RS)
#  Formato: 3 (município) + 6 (empresa) + 1 DV  => 10 dígitos
#  Pesos (esq→dir) sobre os 9 primeiros: [2,9,8,7,6,5,4,3,2]
#  DV = 0 se resto em {0,1}; senão 11 - resto
# ==========================
def valida_ie_rs(ie: str) -> dict:
    ie_d = _digits(ie)
    if len(ie_d) != 10:
        return _result("RS", ie_d, "", ie_d[-1:] or "", f"Tamanho inválido ({len(ie_d)})", False)
    base = _to_int_list(ie_d[:9])
    dv_in = ie_d[9]
    pesos = [2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = _weighted_sum(base, pesos)
    dv = _dv_mod11_from_sum(soma, zero_if=(0, 1))
    return _result("RS", ie_d, dv, dv_in, "Módulo 11 (pesos 2,9,8,7,6,5,4,3,2)")

# ==========================
#  SANTA CATARINA (SC)
#  Formato: 8 + DV  => 9 dígitos
#  Pesos (esq→dir) sobre os 8 primeiros: [9,8,7,6,5,4,3,2]
#  DV = 0 se resto em {0,1}; senão 11 - resto
# ==========================
def valida_ie_sc(ie: str) -> dict:
    ie_d = _digits(ie)
    if len(ie_d) != 9:
        return _result("SC", ie_d, "", ie_d[-1:] or "", f"Tamanho inválido ({len(ie_d)})", False)
    base = _to_int_list(ie_d[:8])
    dv_in = ie_d[8]
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = _weighted_sum(base, pesos)
    dv = _dv_mod11_from_sum(soma, zero_if=(0, 1))
    return _result("SC", ie_d, dv, dv_in, "Módulo 11 (pesos 9..2)")

# ==========================
#  PARANÁ (PR) — STUB
#  Me envie o roteiro oficial (formato/pesos/regra) e implemento na hora.
# ==========================
def valida_ie_pr(ie: str) -> dict:
    ie_d = _digits(ie)
    return _result("PR", ie_d, "", "", "Regra do PR não implementada ainda — envie o roteiro oficial", False)

# ==========================
#  DISPATCHER (Sul)
# ==========================
VALIDADORES_SUL: Dict[str, Callable[[str], dict]] = {
    "RS": valida_ie_rs,
    "SC": valida_ie_sc,
    "PR": valida_ie_pr,
}

def valida_ie_sul(uf: str, ie: str) -> dict:
    uf = (uf or "").upper().strip()
    f = VALIDADORES_SUL.get(uf)
    if not f:
        return _result(uf, ie, "", "", f"UF {uf} sem regra implementada (Sul)", False)
    return f(ie)
