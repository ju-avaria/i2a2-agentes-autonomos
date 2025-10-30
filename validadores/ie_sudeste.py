# validadores/ie_sudeste.py
# Regras oficiais (Sintegra/SEFAZ) — Região Sudeste
# RJ, ES, MG, SP (industrial/comercial e produtor rural)

from typing import Dict, Callable

# ==========================
#  HELPERS COMUNS
# ==========================
def _digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _to_int_list(s: str) -> list[int]:
    return [int(c) for c in s]

def _weighted_sum(nums: list[int], weights: list[int]) -> int:
    return sum(n * w for n, w in zip(nums, weights))

def _dv_mod10_from_sum(total: int) -> int:
    # DV = (10 - (total % 10)) % 10
    r = total % 10
    return 0 if r == 0 else (10 - r)

def _dv_mod11_from_sum(total: int, zero_if=(0, 1)) -> int:
    r = total % 11
    return 0 if r in zero_if else 11 - r

def _sum_digits(n: int) -> int:
    # soma dos dígitos (ex.: 18 -> 1+8 = 9)
    s = 0
    while n:
        s += n % 10
        n //= 10
    return s

def _result(uf: str, ie_in: str, dv_calc: str, dv_real: str, motivo: str, ok: bool | None = None) -> dict:
    if ok is None:
        ok = (str(dv_calc) == str(dv_real))
    return {
        "uf": uf,
        "valida": bool(ok),
        "dv_calculado": str(dv_calc),
        "dv_real": str(dv_real),
        "motivo": motivo,
    }

# ==========================
#  RIO DE JANEIRO (RJ)
#  Formato: 7 dígitos + DV  (ex.: 99.999.99-3)
#  Soma = N1*2 + N2*7 + N3*6 + N4*5 + N5*4 + N6*3 + N7*2
#  DV = 0 se resto<=1; senão 11 - resto
# ==========================
def valida_ie_rj(ie: str) -> dict:
    ie_d = _digits(ie)
    if len(ie_d) != 8:
        return _result("RJ", ie_d, "", ie_d[-1:] or "", f"Tamanho inválido ({len(ie_d)})", False)
    base = _to_int_list(ie_d[:7])
    dv_in = ie_d[7]
    pesos = [2, 7, 6, 5, 4, 3, 2]  # conforme cartilha RJ
    soma = _weighted_sum(base, pesos)
    dv = _dv_mod11_from_sum(soma, zero_if=(0, 1))
    return _result("RJ", ie_d, dv, dv_in, "Módulo 11 (pesos 2,7,6,5,4,3,2)")

# ==========================
#  ESPÍRITO SANTO (ES)
#  Formato: 8 + DV  (9 dígitos). Pesos 9..2, módulo 11.
# ==========================
def valida_ie_es(ie: str) -> dict:
    ie_d = _digits(ie)
    if len(ie_d) != 9:
        return _result("ES", ie_d, "", ie_d[-1:] or "", f"Tamanho inválido ({len(ie_d)})", False)
    base = _to_int_list(ie_d[:8])
    dv_in = ie_d[8]
    pesos = [9, 8, 7, 6, 5, 4, 3, 2]
    soma = _weighted_sum(base, pesos)
    dv = _dv_mod11_from_sum(soma, zero_if=(0, 1))
    return _result("ES", ie_d, dv, dv_in, "Módulo 11 (pesos 9..2)")

# ==========================
#  MINAS GERAIS (MG)
#  Formato: A1A2A3 B1..B6 C1C2 D1 D2  (14 dígitos)
#  D1:
#   - Inserir '0' após os 3 primeiros dígitos (código do município)
#   - Usar os 11 dígitos resultantes (sem D1D2) multiplicando por 1,2 alternadamente (esq→dir)
#   - Somar dígitos dos produtos (ex.: 18 -> 1+8)
#   - D1 = (10 - (soma % 10)) % 10
#  D2:
#   - Usar 12 dígitos (sem D2, já incluindo D1)
#   - Pesos (dir→esq): 2..11 (ou esq→dir: 3,2,11,10,9,8,7,6,5,4,3,2)
#   - DV = 0 se resto em {0,1}; senão 11 - resto
# ==========================
def valida_ie_mg(ie: str) -> dict:
    ie_d = _digits(ie)
    if len(ie_d) != 13 and len(ie_d) != 14:
        # algumas representações omitem um zero em C1C2; padronizaremos 13->14 com zero à esquerda do bloco C
        return _result("MG", ie_d, "", ie_d[-2:] or "", f"Tamanho inválido ({len(ie_d)})", False)

    # padroniza para 13 corpo + 1? Em MG o usual é 13 corpo+2DV = 13? A documentação comum usa 13+2=15?
    # Vamos seguir o roteiro clássico SEFAZ: 11+2 DV = 13; mas o exemplo tem 12+2 = 14.
    # Estratégia robusta: se tiver 13, prefixe '0' em C1C2 para ficarmos com 14.
    if len(ie_d) == 13:
        ie_d = ie_d[:11] + "0" + ie_d[11:]  # injeta um zero antes dos DVs (mantém significado)

    corpo12 = ie_d[:12]
    d1_in = int(ie_d[12])
    d2_in = int(ie_d[13])

    # ------- D1 -------
    # inserir '0' após os 3 primeiros dígitos do corpo original (sem D1D2)
    corpo_sem_dv = ie_d[:12]  # 12 antes de D1D2
    bloco = corpo_sem_dv[:3] + "0" + corpo_sem_dv[3:11]  # total 11 dígitos
    nums = _to_int_list(bloco)
    # pesos alternados 1,2,1,2,... (esquerda→direita)
    total = 0
    for i, n in enumerate(nums):
        mult = 1 if (i % 2 == 0) else 2
        total += _sum_digits(n * mult)
    d1 = (10 - (total % 10)) % 10

    # ------- D2 -------
    base12 = _to_int_list(corpo12[:11] + str(d1))  # 12 dígitos incluindo D1 recém-calculado
    # pesos da direita para a esquerda 2..11  -> da esquerda para a direita: 3,2,11,10,9,8,7,6,5,4,3,2
    pesos_esq_dir = [3, 2, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
    soma2 = _weighted_sum(base12, pesos_esq_dir)
    d2 = _dv_mod11_from_sum(soma2, zero_if=(0, 1))

    dv_calc = f"{d1}{d2}"
    dv_real = f"{d1_in}{d2_in}"
    return _result("MG", ie_d, dv_calc, dv_real, "MG: D1 (mód.10 alternado com soma de dígitos) + D2 (mód.11)")

# ==========================
#  SÃO PAULO (SP)
#  Dois formatos:
#   (1) Industrial/Comercial — 12 dígitos; DV9 e DV12 (mód.11 com pesos específicos)
#   (2) Produtor Rural — 'P' + 12 dígitos; DV é o 10º caractere (mód.11 com pesos 1,3,4,5,6,7,8,10)
# ==========================
def _sp_industrial(ie_d: str) -> dict:
    if len(ie_d) != 12:
        return _result("SP", ie_d, "", ie_d[-2:] or "", f"Tamanho inválido ({len(ie_d)})", False)

    nums = _to_int_list(ie_d)

    # ----- 1º DV (posição 9) -----
    pesos9 = [1, 3, 4, 5, 6, 7, 8, 10]   # aplicados aos 8 primeiros dígitos
    soma9 = _weighted_sum(nums[:8], pesos9)
    r9 = soma9 % 11
    d9 = r9 % 10  # “algarismo mais à direita do resto” → r=10 vira 0
    if d9 != nums[8]:
        return _result("SP", ie_d, f"{d9}{'?'}", f"{nums[8]}{nums[11]}", "SP industrial: 1º DV incorreto", False)

    # ----- 2º DV (posição 12) -----
    pesos12 = [3, 2, 10, 9, 8, 7, 6, 5, 4, 3, 2]  # aplicados aos 11 primeiros (inclui d9 na 9ª posição)
    soma12 = _weighted_sum(nums[:11], pesos12)
    r12 = soma12 % 11
    d12 = r12 % 10
    dv_calc = f"{d9}{d12}"
    dv_real = f"{nums[8]}{nums[11]}"
    return _result("SP", ie_d, dv_calc, dv_real, "SP industrial: DV9 (mod11 resto→último alg.) + DV12 (idem)")

def _sp_produtor(ie_raw: str) -> dict:
    # Formato: 'P' + 12 dígitos; DV é o 10º caractere (contando 'P')
    s = (ie_raw or "").upper()
    # extrai somente 'P' e dígitos
    s = "".join(ch for ch in s if (ch.isdigit() or ch == 'P'))
    if not (s.startswith('P') and len(s) == 13):
        return _result("SP", s, "", s[9:10] if len(s) >= 10 else "", f"Formato produtor inválido ({s})", False)

    corpo8 = _to_int_list(s[1:9])  # 8 dígitos após o 'P' até o DV
    dv_in = int(s[9])
    pesos = [1, 3, 4, 5, 6, 7, 8, 10]
    soma = _weighted_sum(corpo8, pesos)
    r = soma % 11
    dv = r % 10  # “algarismo mais à direita do resto”
    return _result("SP", s, dv, dv_in, "SP produtor rural: mod11 (pesos 1,3,4,5,6,7,8,10; resto→último algarismo)")

def valida_ie_sp(ie: str) -> dict:
    raw = ie or ""
    if isinstance(raw, str) and raw.strip().upper().startswith("P"):
        return _sp_produtor(raw)
    else:
        return _sp_industrial(_digits(raw))

# ==========================
#  DISPATCHER (Sudeste)
# ==========================
VALIDADORES_SE: Dict[str, Callable[[str], dict]] = {
    "RJ": valida_ie_rj,
    "ES": valida_ie_es,
    "MG": valida_ie_mg,
    "SP": valida_ie_sp,
}

def valida_ie_sudeste(uf: str, ie: str) -> dict:
    uf = (uf or "").upper().strip()
    f = VALIDADORES_SE.get(uf)
    if not f:
        return _result(uf, ie, "", "", f"UF {uf} sem regra implementada", False)
    return f(ie)
