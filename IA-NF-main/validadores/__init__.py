# validadores/__init__.py
from importlib import import_module

# Mapa UF -> Região
_UF_TO_REGION = {
    # Norte
    "AC":"N", "AM":"N", "AP":"N", "PA":"N", "RO":"N", "RR":"N", "TO":"N",
    # Nordeste
    "AL":"NE","BA":"NE","CE":"NE","MA":"NE","PB":"NE","PE":"NE","PI":"NE","RN":"NE","SE":"NE",
    # Centro-Oeste
    "DF":"CO","GO":"CO","MT":"CO","MS":"CO",
    # Sudeste
    "ES":"SE","MG":"SE","RJ":"SE","SP":"SE",
    # Sul
    "PR":"S", "RS":"S", "SC":"S",
}

# Região -> módulo Python
_REGION_TO_MODULE = {
    "N":  "validadores.ie_norte",
    "NE": "validadores.ie_nordeste",
    "CO": "validadores.ie_centro_oeste",
    "SE": "validadores.ie_sudeste",
    "S":  "validadores.ie_sul",
}

# Candidatos de funções exportadas por cada módulo regional (tentamos na ordem)
# Preferimos a assinatura padronizada: def valida_ie_<regiao>(uf: str, ie: str) -> dict
_FN_CANDIDATES = [
    "valida_ie_norte",
    "valida_ie_nordeste",
    "valida_ie_centro_oeste",
    "valida_ie_sudeste",
    "valida_ie_sul",
    "valida_ie_regional",   # opção genérica se você usou esse nome
    "valida_ie",            # fallback se o módulo expõe um nome genérico
]


def _err(uf: str, ie: str, motivo: str) -> dict:
    return {
        "uf": (uf or "").upper().strip(),
        "valida": False,
        "dv_calculado": "",
        "dv_real": (ie or "")[-1:] if ie else "",
        "motivo": motivo,
    }


def valida_ie(uf: str, ie: str) -> dict:
    """
    Ponto de entrada único para validar IE por UF.
    Redireciona para o módulo da região correspondente e chama a função disponível.
    """
    uf = (uf or "").upper().strip()
    ie = (ie or "").strip()

    if not uf:
        return _err(uf, ie, "UF vazia ou não informada")
    region = _UF_TO_REGION.get(uf)
    if not region:
        return _err(uf, ie, f"UF {uf} desconhecida")

    mod_name = _REGION_TO_MODULE[region]
    try:
        mod = import_module(mod_name)
    except Exception as e:
        return _err(uf, ie, f"Falha ao carregar módulo {mod_name}: {e}")

    # 1) Tenta funções padronizadas com assinatura (uf, ie)
    for fn_name in _FN_CANDIDATES:
        fn = getattr(mod, fn_name, None)
        if callable(fn):
            try:
                return fn(uf, ie)  # assinatura preferida
            except TypeError:
                # 2) Se a função regional aceita só (ie), tente despachar por UF internamente
                try:
                    return fn(ie)   # alguns módulos podem ter sido escritos assim
                except Exception as e:
                    return _err(uf, ie, f"Validador {mod_name}.{fn_name} falhou: {e}")
            except Exception as e:
                return _err(uf, ie, f"Validador {mod_name}.{fn_name} falhou: {e}")

    # 3) Fallback: se o módulo expõe um dicionário de validadores por UF (ex.: VALIDADORES_NORTE, VALIDADORES_NE, etc.)
    for map_name in ("VALIDADORES_NORTE", "VALIDADORES_NE", "VALIDADORES_CO", "VALIDADORES_SE", "VALIDADORES_SUL"):
        mapa = getattr(mod, map_name, None)
        if isinstance(mapa, dict):
            f = mapa.get(uf)
            if callable(f):
                try:
                    # muitos desses validadores aceitam apenas (ie)
                    return f(ie)
                except TypeError:
                    return f(uf, ie)
                except Exception as e:
                    return _err(uf, ie, f"Validador {map_name}[{uf}] falhou: {e}")

    return _err(uf, ie, f"O módulo {mod_name} não expõe função/dicionário de validação compatível")
